import json
from pathlib import Path

import pytest

from src.utils.todo_store import (
    TodoItem,
    TodoStore,
    flatten_todos,
    move_todo,
    remove_todo,
    set_completed,
)


def test_store_round_trip_preserves_tasks_and_sub_items(tmp_path: Path) -> None:
    store = TodoStore(tmp_path / "todos.json")
    parent = TodoItem("Planejar viagem", priority="high", order=0)
    child = TodoItem("Reservar hotel", parent_id=parent.id, priority="low", order=0)
    child.description = "Perto do centro"
    child.paused = True

    store.save([parent, child])
    loaded = store.load()

    assert [(item.title, item.parent_id) for item in loaded] == [
        ("Planejar viagem", None),
        ("Reservar hotel", parent.id),
    ]
    assert loaded[1].description == "Perto do centro"
    assert loaded[1].paused is True
    assert loaded[0].priority == "high"


def test_store_creates_parent_directory_and_starts_empty(tmp_path: Path) -> None:
    store = TodoStore(tmp_path / "nested" / "data" / "todos.json")

    assert store.load() == []
    store.save([TodoItem("First task")])

    assert store.path.is_file()
    assert len(store.load()) == 1


def test_store_rejects_invalid_json_and_orphan_sub_items(tmp_path: Path) -> None:
    path = tmp_path / "todos.json"
    path.write_text("{bad json", encoding="utf-8")
    with pytest.raises(ValueError, match="valid JSON"):
        TodoStore(path).load()

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "items": [{"id": "child", "parent_id": "missing", "title": "Child"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="top-level item"):
        TodoStore(path).load()


def test_flatten_sorts_by_priority_and_keeps_sub_items_under_parent() -> None:
    regular = TodoItem("Regular", priority="low", order=0)
    urgent = TodoItem("Urgent", priority="high", order=1)
    sub_item = TodoItem("Urgent detail", parent_id=urgent.id, priority="medium", order=0)

    assert [item.title for item in flatten_todos([regular, sub_item, urgent], "priority")] == [
        "Urgent",
        "Urgent detail",
        "Regular",
    ]


def test_completing_parent_completes_sub_items_but_reopening_keeps_them_done() -> None:
    parent = TodoItem("Prepare release")
    child = TodoItem("Write release notes", parent_id=parent.id)
    other = TodoItem("Review notes")
    items = [parent, child, other]

    assert set_completed(items, parent.id) is True
    assert parent.completed is True
    assert child.completed is True
    assert other.completed is False

    assert set_completed(items, parent.id) is True
    assert parent.completed is False
    assert child.completed is True


def test_sub_item_completion_is_independent_and_manual_move_is_sibling_scoped() -> None:
    parent = TodoItem("Parent", order=0)
    first = TodoItem("First", parent_id=parent.id, order=0)
    second = TodoItem("Second", parent_id=parent.id, order=1)
    other = TodoItem("Other", order=1)
    items = [parent, first, second, other]

    assert set_completed(items, second.id) is True
    assert second.completed is True
    assert parent.completed is False
    assert move_todo(items, second.id, -1) is True
    assert [item.title for item in flatten_todos(items)] == ["Parent", "Second", "First", "Other"]
    assert move_todo(items, parent.id, -1) is False


def test_deleting_parent_removes_its_sub_items_and_preserves_other_tasks() -> None:
    parent = TodoItem("Remove me")
    child = TodoItem("Remove child", parent_id=parent.id)
    other = TodoItem("Keep me")
    items = [parent, child, other]

    removed = remove_todo(items, parent.id)

    assert {item.id for item in removed} == {parent.id, child.id}
    assert items == [other]
