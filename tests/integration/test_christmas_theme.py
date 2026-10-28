import asyncio

from textual.widgets import Label, ListView, Static

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.seasonal_theme import CHRISTMAS_THEME


def test_christmas_theme_works_with_manual_seasonal_override(monkeypatch) -> None:
    monkeypatch.setitem(config._data["ui"], "theme", CHRISTMAS_THEME)
    monkeypatch.setitem(config._data["ui"], "enable_all_seasonal_themes", True)

    async def check_theme() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause()
            assert app.theme == CHRISTMAS_THEME
            assert str(app.query_one("#app-title", Label).content) == "\U0001F36A Toolbox TUI \u2603 "

            sidebar = app.query_one("#sidebar-list", ListView)
            labels = [str(item.query_one(Label).content) for item in sidebar.children]
            assert labels[0].startswith("\U0001F384 Home")
            assert labels[10].startswith("\U0001F98C Quit")

            art = str(app.query_one("#ascii-art", Static).content)
            assert "\U0001F381 Wishing you a Merry Christmas!" in art

            if app._seasonal_timer is not None:
                app._seasonal_timer.stop()
                app._seasonal_timer = None
            app._animate_seasonal_decoration()
            assert any(
                "\u2744" in str(item.query_one(Label).content)
                for item in sidebar.children
            )

    asyncio.run(check_theme())
