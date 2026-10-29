import asyncio

from textual.widgets import Button, Input, OptionList, TextArea

from src.tui import ToolboxTUI
from src.utils.offline_utilities import UTILITIES
from src.views.utilities import UtilityDialog


def test_utilities_search_open_and_run() -> None:
    app = ToolboxTUI()

    async def check_workflow() -> None:
        async with app.run_test(size=(140, 45)) as pilot:
            app.action_select_view(9)
            await pilot.pause()
            search = app.query_one("#utility-search", Input)
            search.value = "regular expression"
            await pilot.pause()

            utility_list = app.query_one("#utility-list", OptionList)
            option_index = utility_list.get_option_index("test-regex")
            assert utility_list.option_count == 2  # Category heading and matching utility.
            utility_list.focus()
            utility_list.highlighted = option_index
            await pilot.press("enter")
            await pilot.pause()
            assert not app.query_one("#utility-open", Button).disabled

            await pilot.click("#utility-open")
            await pilot.pause()
            assert isinstance(app.screen, UtilityDialog)
            dialog = app.screen
            dialog.query_one("#utility-input", TextArea).text = "(cat)"
            dialog.query_one("#utility-second-input", TextArea).text = "catapult and cat"
            await pilot.click("#utility-run")
            await pilot.pause()
            assert "2 match(es)" in dialog.query_one("#utility-output", TextArea).text

            names = {utility.name for utility in UTILITIES}
            assert "Decode JWT" in names
            assert "Cron next runs" in names

    asyncio.run(check_workflow())
