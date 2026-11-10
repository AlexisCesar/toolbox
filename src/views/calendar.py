"""Today's read-only calendar agenda."""

import asyncio
from datetime import date, datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Input, Label, Static

from src.utils.calendar_feed import CalendarEvent, load_today, validate_feed_url
from src.utils.config import config
from src.utils.logger import Logger


class CalendarView(Static):
    """Manage one private subscription and show today's events."""

    def __init__(self, logger: Logger, **kwargs) -> None:
        super().__init__(**kwargs)
        self.logger = logger
        self.events: list[CalendarEvent] = []
        self._worker = None
        self._day = date.today()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="calendar-container"):
            yield Label("Calendar - Today", id="calendar-title")
            yield Static(
                "In your calendar provider's settings, find the option to copy or export a private iCal subscription link.\n"
                "Paste the private link below. It is stored locally in config.override.toml; keep it secret.",
                id="calendar-help", markup=False,
            )
            yield Input(value=config.calendar_url, password=True, placeholder="HTTPS iCal subscription URL", id="calendar-url")
            with Horizontal(id="calendar-actions"):
                yield Button("Subscribe", id="calendar-subscribe", variant="primary")
                yield Button("Refresh", id="calendar-refresh")
                yield Button("Unsubscribe", id="calendar-remove")
            yield Static("No calendar subscribed. Paste an iCal link to get started.", id="calendar-status", markup=False)
            yield DataTable(id="calendar-table", cursor_type="row", zebra_stripes=True)
            yield Static("Select an event to view its location and meeting link.", id="calendar-details", markup=False)

    def on_mount(self) -> None:
        self.query_one("#calendar-table", DataTable).add_columns("Time", "Event")
        self.set_interval(30, self._check_day)

    def on_show(self) -> None:
        self.query_one("#calendar-url", Input).value = config.calendar_url
        self.refresh_events()

    def on_hide(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _check_day(self) -> None:
        if self.display and self._day != date.today():
            self.refresh_events()

    def refresh_events(self) -> None:
        self._day = date.today()
        self.query_one("#calendar-title", Label).update(f"Calendar - {self._day:%A, %d %B %Y}")
        if self._worker is not None:
            self._worker.cancel()
        self.events = []
        self.query_one("#calendar-table", DataTable).clear()
        self.query_one("#calendar-details", Static).update("")
        if not config.calendar_url:
            self.query_one("#calendar-status", Static).update("No calendar subscribed. Paste an iCal link to get started.")
            return
        self.query_one("#calendar-status", Static).update("Loading today's events.")
        self._worker = self.run_worker(self._load_events(config.calendar_url), group="calendar", exclusive=True)

    async def _load_events(self, url: str) -> None:
        try:
            events = await asyncio.to_thread(load_today, url)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Network and parser exceptions may contain the private URL or event data.
            self.logger.error("Calendar refresh failed. Check the subscription link and network connection.")
            self.query_one("#calendar-status", Static).update("Could not load calendar. Check the iCal link and connection, then Refresh.")
            return
        self.events = events
        table = self.query_one("#calendar-table", DataTable)
        table.clear()
        for index, event in enumerate(events):
            label = "All day" if event.all_day else f"{event.start:%H:%M} - {event.end:%H:%M}"
            table.add_row(Text(label), Text(event.title), key=str(index))
        self.query_one("#calendar-status", Static).update(
            f"{len(events)} event(s) today � Updated {datetime.now():%H:%M} � Local timezone"
            if events else "No events today. Your day is clear!"
        )
        self.logger.info(f"Calendar refreshed: {len(events)} event(s) today.")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "calendar-table" or event.row_key.value is None:
            return
        index = int(event.row_key.value)
        if index >= len(self.events):
            return
        item = self.events[index]
        details = [item.title, "All day" if item.all_day else f"{item.start:%d %b %H:%M} - {item.end:%d %b %H:%M}"]
        if item.location:
            details.append(f"Location: {item.location}")
        if item.link:
            details.append(f"Meeting: {item.link}")
        self.query_one("#calendar-details", Static).update(Text("\n".join(details)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id not in {"calendar-subscribe", "calendar-remove", "calendar-refresh"}:
            return
        event.stop()
        if button_id == "calendar-refresh":
            self.refresh_events()
            return
        try:
            value = validate_feed_url(self.query_one("#calendar-url", Input).value) if button_id == "calendar-subscribe" else ""
            config.update("calendar", "url", value)
        except ValueError:
            self.query_one("#calendar-status", Static).update("Enter a valid HTTPS iCal subscription URL.")
            return
        except OSError:
            self.logger.error("Could not save the calendar subscription configuration.")
            self.query_one("#calendar-status", Static).update("Could not save subscription. Check configuration file permissions.")
            return
        self.query_one("#calendar-url", Input).value = value
        self.logger.info("Calendar subscription saved." if value else "Calendar subscription removed.")
        self.refresh_events()
