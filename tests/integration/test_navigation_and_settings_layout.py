import asyncio

from textual.widgets import Button, Label, ListView

from src.tui import ToolboxTUI


def test_sidebar_order_and_settings_layout() -> None:
    app = ToolboxTUI()

    async def check_layout() -> None:
        async with app.run_test(size=(160, 45)) as pilot:
            sidebar = app.query_one("#sidebar-list", ListView)
            assert len(sidebar.children) == 11
            app.action_select_view(1)
            await pilot.pause()
            assert app.query_one("#main-content-switcher").current == "bash-view"
            app.action_select_view(2)
            await pilot.pause()
            assert app.query_one("#main-content-switcher").current == "todos-view"

            app.action_select_view(9)
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

    asyncio.run(check_layout())
