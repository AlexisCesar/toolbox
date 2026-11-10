import asyncio
from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, DataTable, Input, Static

from src.utils.calendar_feed import CalendarEvent
from src.utils.config import Config
from src.views import calendar


@pytest.mark.parametrize("size", [(120, 35), (80, 24)])
def test_subscription_refresh_details_error_and_remove(tmp_path, monkeypatch, size):
    defaults = tmp_path / "config.toml"
    defaults.write_text('[ui]\ntheme="textual-dark"\n', encoding="utf-8")
    settings = Config(defaults, tmp_path / "override.toml")
    monkeypatch.setattr(calendar, "config", settings)
    zone = ZoneInfo("America/Sao_Paulo")
    event = CalendarEvent("Meeting [literal]", datetime(2026, 11, 10, 9, tzinfo=zone), datetime(2026, 11, 10, 10, tzinfo=zone), False, "Office", "https://meet.google.com/test")
    loader = Mock(return_value=[event])
    monkeypatch.setattr(calendar, "load_today", loader)
    logger = Mock()

    class CalendarApp(App):
        CSS_PATH = "../../src/tui.tcss"

        def compose(self) -> ComposeResult:
            yield calendar.CalendarView(logger, id="calendar-view")

    async def check():
        async with CalendarApp().run_test(size=size) as pilot:
            await pilot.pause()
            view = pilot.app.query_one(calendar.CalendarView)
            help_text = view.query_one("#calendar-help", Static).render().plain
            assert "calendar provider's settings" in help_text
            assert "Google Calendar" not in help_text
            field = view.query_one(Input)
            assert field.password
            field.value = "https://example.com/private.ics"
            view.query_one("#calendar-subscribe", Button).press()
            await pilot.pause()
            await view.workers.wait_for_complete()
            table = view.query_one(DataTable)
            assert table.row_count == 1
            assert table.get_row_at(0)[1].plain == "Meeting [literal]"
            await pilot.pause()
            assert "Office" in str(view.query_one("#calendar-details", Static).render())
            assert table.region.width > 0
            loader.side_effect = ValueError("https://example.com/private.ics secret")
            view.query_one("#calendar-refresh", Button).press()
            await pilot.pause()
            await view.workers.wait_for_complete()
            assert table.row_count == 0
            assert "private.ics" not in str(logger.method_calls)
            assert "Could not load" in str(view.query_one("#calendar-status", Static).render())
            view.query_one("#calendar-remove", Button).press()
            await pilot.pause()
            assert settings.calendar_url == ""
            assert field.value == ""

    asyncio.run(check())
