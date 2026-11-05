from unittest.mock import Mock

import pytest
from rich.console import Console
from rich.text import Text

from src.utils.todo_store import TodoItem, TodoStore, set_completed
from src.views.todos import Todos


@pytest.mark.parametrize("paused", [False, True])
def test_completed_row_is_dimmed_and_reopening_restores_text(monkeypatch, paused: bool) -> None:
    view = Todos(Mock(), store=Mock(spec=TodoStore))
    item = TodoItem("Task [literal]", description="Task details", priority="low", paused=paused)
    view.items = [item]
    table = Mock()
    summary = Mock()
    progress = Mock()
    widgets = {"#todos-table": table, "#todos-summary": summary, "#todos-progress": progress}
    monkeypatch.setattr(view, "query_one", lambda selector, widget_type: widgets[selector])
    console = Console()

    for completed in (False, True, False):
        if item.completed != completed:
            set_completed(view.items, item.id)
        view.refresh_table()
        cells = table.add_row.call_args.args
        assert cells[0].plain == "Task [literal]\nTask details"
        assert cells[1].plain == ("\u2713 Done" if completed else "\u2161 Paused" if item.paused else "\u25CB Pending")
        for cell in cells:
            assert isinstance(cell, Text)
            for offset in range(len(cell.plain)):
                assert bool(cell.get_style_at_offset(console, offset).dim) is completed
