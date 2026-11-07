import asyncio

from textual.widgets import Static

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.themes import NETRUNNER_THEME
from src.views.settings import theme_options


def test_netrunner_theme_is_static_and_available_in_settings(monkeypatch) -> None:
    monkeypatch.setitem(config._data["ui"], "theme", NETRUNNER_THEME)

    async def check_theme() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=(160, 45)):
            assert app.theme == NETRUNNER_THEME
            assert app.has_class("netrunner-theme")
            assert app._seasonal_timer is None
            assert NETRUNNER_THEME in theme_options()
            assert "#ff1744" in str(app.query_one("#ascii-art", Static).content)

    asyncio.run(check_theme())
