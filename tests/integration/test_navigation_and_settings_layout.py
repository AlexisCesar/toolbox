import asyncio

from textual.widgets import Button, Label, ListView

from src.tui import ToolboxTUI
from src.utils.addon_manager import AddonManager
from src.views.bash import Bash


def test_sidebar_order_and_settings_layout(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    monkeypatch.setattr(
        "src.tui.AddonManager",
        lambda: AddonManager(tmp_path / "addons"),
    )
    app = ToolboxTUI()

    async def check_layout() -> None:
        async with app.run_test(size=(160, 45)) as pilot:
            sidebar = app.query_one("#sidebar-list", ListView)
            assert len(sidebar.children) == 14
            assert str(sidebar.children[11].query_one(Label).content).endswith("Addons")
            assert str(sidebar.children[12].query_one(Label).content).endswith("Settings")
            assert str(sidebar.children[2].query_one(Label).content).endswith("TODO list")
            assert str(sidebar.children[3].query_one(Label).content).endswith("Calendar")
            app.action_select_view(1)
            await pilot.pause()
            assert app.query_one("#main-content-switcher").current == "bash-view"
            app.action_select_view(2)
            await pilot.pause()
            assert app.query_one("#main-content-switcher").current == "todos-view"

            app.action_select_view(3)
            await pilot.pause()
            assert app.query_one("#main-content-switcher").current == "calendar-view"
            app.query_one("#calendar-url")

            app.action_select_settings()
            await pilot.pause()
            left = app.query_one("#settings-left-column").region
            right = app.query_one("#settings-right-column").region
            assert abs(left.width - right.width) <= 1
            app.query_one("#settings-other-title", Label)
            app.query_one("#settings-theme-select")

            logs_add = app.query_one("#settings-logs-add", Button)
            logs_edit = app.query_one("#settings-logs-edit", Button)
            services_add = app.query_one("#settings-services-add", Button)
            services_edit = app.query_one("#settings-services-edit", Button)
            assert all(button.variant == "primary" for button in (logs_add, logs_edit, services_add, services_edit))
            assert logs_edit.region.x > logs_add.region.x + logs_add.region.width
            assert services_edit.region.x > services_add.region.x + services_add.region.width

            app.action_select_view(11)
            await pilot.pause()
            assert app.query_one("#main-content-switcher").current == "addons-view"
            app.query_one("#addons-table")
            app.query_one("#addons-help")

    asyncio.run(check_layout())
