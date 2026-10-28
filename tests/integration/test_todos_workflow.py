import asyncio
from pathlib import Path

from textual.widgets import ContentSwitcher, DataTable, Input, Select, TextArea

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.todo_store import TodoStore


def test_todo_screen_creates_sub_item_and_completes_it_with_parent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setitem(config._data["ui"], "todo_startup_notification", False)
    app = ToolboxTUI()
    store = TodoStore(tmp_path / "todos.json")
    app.todo_store = store

    async def exercise_workflow() -> None:
        async with app.run_test(size=(160, 45)) as pilot:
            app.action_select_view(2)
            await pilot.pause()
            assert app.query_one("#main-content-switcher", ContentSwitcher).current == "todos-view"

            await pilot.click("#todos-add")
            await pilot.pause()
            app.screen.query_one("#todo-editor-name", Input).value = "Prepare release"
            app.screen.query_one("#todo-editor-description", TextArea).load_text("Check the release plan")
            await pilot.click("#todo-editor-save")
            await pilot.pause()

            table = app.query_one("#todos-table", DataTable)
            table.move_cursor(row=0)
            await pilot.click("#todos-add-child")
            await pilot.pause()
            app.screen.query_one("#todo-editor-name", Input).value = "Write release notes"
            await pilot.click("#todo-editor-save")
            await pilot.pause()

            table.move_cursor(row=0)
            await pilot.click("#todos-edit")
            await pilot.pause()
            app.screen.query_one("#todo-editor-name", Input).value = "Prepare public release"
            app.screen.query_one("#todo-editor-priority", Select).value = "high"
            await pilot.click("#todo-editor-save")
            await pilot.pause()

            table.move_cursor(row=0)
            await pilot.click("#todos-pause")
            await pilot.pause()
            assert store.load()[0].paused is True

            table.move_cursor(row=0)
            await pilot.click("#todos-toggle")
            await pilot.pause()
            tasks = store.load()
            assert all(task.completed for task in tasks)
            assert all(not task.paused for task in tasks)
            assert tasks[0].title == "Prepare public release"
            assert tasks[0].priority == "high"

            table.move_cursor(row=0)
            await pilot.click("#todos-add-child")
            await pilot.pause()
            app.screen.query_one("#todo-editor-name", Input).value = "Post-release follow-up"
            await pilot.click("#todo-editor-save")
            await pilot.pause()

            table.move_cursor(row=0)
            await pilot.click("#todos-toggle")
            await pilot.pause()
            tasks = store.load()
            assert tasks[0].completed is False
            assert all(task.completed for task in tasks[1:])

            table.move_cursor(row=0)
            await pilot.click("#todos-delete")
            await pilot.pause()
            await pilot.click("#dialog-confirm-yes")
            await pilot.pause()
            assert store.load() == []

    asyncio.run(exercise_workflow())
