from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Label, Static

from src.utils.config import config
from src.utils.log_dialogs import LogFileDialog, LogFilesDialog
from src.utils.logger import Logger


class Logs(Static):
    """Browse log files from the configured local or network folders."""

    def __init__(self, logger: Logger, **kwargs) -> None:
        super().__init__(**kwargs)
        self.logger = logger

    def compose(self) -> ComposeResult:
        yield Label("Logs", id="logs-title")
        yield Label(
            "Browse configured folders and open a log to view its latest entries.",
            id="logs-subtitle",
        )
        yield VerticalScroll(id="logs-entries")

    async def on_mount(self) -> None:
        await self.refresh_logs()

    async def on_show(self) -> None:
        await self.refresh_logs()

    async def refresh_logs(self) -> None:
        entries_container = self.query_one("#logs-entries", VerticalScroll)
        await entries_container.remove_children()

        entries = config.logs
        if not entries:
            await entries_container.mount(
                Static(
                    "No log folders configured. Add them in Settings.",
                    id="logs-empty-state",
                )
            )
            return

        rows = [
            Horizontal(
                Label(entry["name"], classes="logs-entry-name"),
                Label(entry["location"], classes="logs-entry-location"),
                Button("Open", id=f"logs-open-{index}", variant="primary"),
                classes="logs-entry",
            )
            for index, entry in enumerate(entries)
        ]
        await entries_container.mount(*rows)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if not button_id.startswith("logs-open-"):
            return

        try:
            entry_index = int(button_id.removeprefix("logs-open-"))
            entry = config.logs[entry_index]
        except (ValueError, IndexError):
            self.logger.warn("The selected log folder is no longer configured.")
            return

        self.app.push_screen(
            LogFilesDialog(
                name=entry["name"],
                directory=Path(entry["location"]).expanduser(),
                logger=self.logger,
            ),
            callback=self.open_log_file,
        )

    def open_log_file(self, path: Path | None) -> None:
        if path is None:
            return

        self.app.push_screen(LogFileDialog(path, self.logger))
