import asyncio
from pathlib import Path
from unittest.mock import Mock

from rich.console import Console
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import ContentSwitcher, DataTable, Input, Select, TextArea

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.todo_store import TodoItem, TodoStore
from src.views.todos import Todos


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


def test_completed_rows_dim_and_status_sort_updates_after_toggling(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setitem(config._data["ui"], "todo_startup_notification", False)
    store = TodoStore(tmp_path / "todos.json")
    done = TodoItem("Done", description="Finished details", completed=True, order=0)
    paused = TodoItem("Paused", paused=True, order=1)
    pending = TodoItem("Pending", description="Still to do", order=2)
    store.save([done, paused, pending])

    class TodoApp(App):
        def compose(self) -> ComposeResult:
            yield Todos(Mock(), store=store)

    async def exercise() -> None:
        async with TodoApp().run_test(size=(160, 45)) as pilot:
            view = pilot.app.query_one(Todos)
            table = view.query_one(DataTable)
            console = Console()

            def assert_dimmed(item: TodoItem, expected: bool) -> None:
                for cell in table.get_row(item.id):
                    assert isinstance(cell, Text)
                    for offset in range(len(cell.plain)):
                        assert bool(cell.get_style_at_offset(console, offset).dim) is expected

            assert_dimmed(done, True)
            assert_dimmed(paused, False)
            assert_dimmed(pending, False)
            assert table.get_row(done.id)[0].plain == "Done\nFinished details"
            view.query_one("#todos-sort", Select).value = "status"
            await pilot.pause()
            assert [item.id for item in view.visible_items] == [pending.id, paused.id, done.id]

            table.move_cursor(row=2)
            view.action_toggle_completed()
            await pilot.pause()
            assert [item.id for item in view.visible_items] == [done.id, pending.id, paused.id]
            assert_dimmed(done, False)

            table.move_cursor(row=0)
            view.action_toggle_completed()
            await pilot.pause()
            assert [item.id for item in view.visible_items] == [pending.id, paused.id, done.id]
            assert_dimmed(done, True)

    asyncio.run(exercise())
