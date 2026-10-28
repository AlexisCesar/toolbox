"""Persistent TODO items and their ordering helpers."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4


Priority = Literal["low", "medium", "high"]
SortMode = Literal["manual", "created", "priority"]
PRIORITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


def default_todo_path() -> Path:
    """Return the platform's per-user data location for TODO items."""
    override = os.environ.get("TOOLBOX_DATA_DIR")
    if override:
        return Path(override).expanduser() / "todos.json"

    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        configured_base = Path(xdg_data_home).expanduser() if xdg_data_home else None
        base = (
            configured_base
            if configured_base is not None and configured_base.is_absolute()
            else Path.home() / ".local" / "share"
        )
    return base / "toolbox" / "todos.json"


@dataclass
class TodoItem:
    """A TODO item, optionally nested under one parent item."""

    title: str
    description: str = ""
    priority: Priority = "medium"
    created_at: str = ""
    id: str = ""
    parent_id: str | None = None
    completed: bool = False
    paused: bool = False
    order: int = 0

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        if not self.id:
            self.id = str(uuid4())
        if not self.created_at:
            self.created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        if not isinstance(self.priority, str) or self.priority not in PRIORITY_ORDER:
            raise ValueError(f"Unsupported TODO priority: {self.priority}")
        if not self.title:
            raise ValueError("A TODO title is required.")

    @classmethod
    def from_dict(cls, data: object) -> TodoItem:
        if not isinstance(data, dict):
            raise ValueError("A TODO entry must be an object.")
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("A TODO entry must have a title.")
        priority = data.get("priority", "medium")
        if not isinstance(priority, str) or priority not in PRIORITY_ORDER:
            raise ValueError(f"Unsupported TODO priority: {priority}")
        created_at = data.get("created_at", "")
        description = data.get("description", "")
        item_id = data.get("id")
        parent_id = data.get("parent_id")
        order = data.get("order", 0)
        if not isinstance(created_at, str) or not isinstance(description, str):
            raise ValueError("TODO dates and descriptions must be text.")
        if item_id is not None and not isinstance(item_id, str):
            raise ValueError("A TODO id must be text.")
        if parent_id is not None and not isinstance(parent_id, str):
            raise ValueError("A TODO parent id must be text.")
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            raise ValueError("A TODO order must be a non-negative integer.")
        completed = data.get("completed", False)
        paused = data.get("paused", False)
        if not isinstance(completed, bool) or not isinstance(paused, bool):
            raise ValueError("TODO completion and pause values must be booleans.")
        return cls(
            id=item_id or "",
            title=title,
            description=description,
            priority=priority,
            created_at=created_at,
            parent_id=parent_id,
            completed=completed,
            paused=paused,
            order=order,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TodoStore:
    """Read and atomically write the user's TODO list as JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_todo_path()

    def load(self) -> list[TodoItem]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"TODO data is not valid JSON: {error}") from error

        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("TODO data has an unsupported format.")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("TODO data must contain an items list.")

        items = [TodoItem.from_dict(raw) for raw in raw_items]
        self._validate_relationships(items)
        return items

    def save(self, items: list[TodoItem]) -> None:
        self._validate_relationships(items)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "items": [item.to_dict() for item in items]}
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_relationships(items: list[TodoItem]) -> None:
        by_id: dict[str, TodoItem] = {}
        for item in items:
            if item.id in by_id:
                raise ValueError("TODO item ids must be unique.")
            by_id[item.id] = item
        for item in items:
            if item.parent_id is None:
                continue
            parent = by_id.get(item.parent_id)
            if parent is None or parent.parent_id is not None:
                raise ValueError("TODO sub-items must reference a top-level item.")


def flatten_todos(items: list[TodoItem], sort_mode: SortMode = "manual") -> list[TodoItem]:
    """Return top-level items and their sub-items in the selected order."""
    grouped: dict[str | None, list[TodoItem]] = {}
    for item in items:
        grouped.setdefault(item.parent_id, []).append(item)

    def sort_key(item: TodoItem) -> tuple[object, ...]:
        if sort_mode == "created":
            return (item.created_at, item.order, item.title.casefold())
        if sort_mode == "priority":
            return (-PRIORITY_ORDER[item.priority], item.order, item.created_at)
        return (item.order, item.created_at)

    flattened: list[TodoItem] = []
    for parent in sorted(grouped.get(None, []), key=sort_key):
        flattened.append(parent)
        flattened.extend(sorted(grouped.get(parent.id, []), key=sort_key))
    return flattened


def set_completed(items: list[TodoItem], item_id: str) -> bool:
    """Toggle completion; completing a parent applies to all its sub-items."""
    selected = next((item for item in items if item.id == item_id), None)
    if selected is None:
        return False
    selected.completed = not selected.completed
    if selected.completed:
        selected.paused = False
    if selected.parent_id is None and selected.completed:
        for child in items:
            if child.parent_id == selected.id:
                child.completed = True
                child.paused = False
    return True


def remove_todo(items: list[TodoItem], item_id: str) -> list[TodoItem]:
    """Remove one item and its sub-items, if any."""
    selected = next((item for item in items if item.id == item_id), None)
    if selected is None:
        return []
    removed_ids = {selected.id}
    if selected.parent_id is None:
        removed_ids.update(item.id for item in items if item.parent_id == selected.id)
    removed_items = [item for item in items if item.id in removed_ids]
    items[:] = [item for item in items if item.id not in removed_ids]
    _renumber(items, selected.parent_id if selected.parent_id else None)
    return removed_items


def move_todo(items: list[TodoItem], item_id: str, direction: int) -> bool:
    """Move an item one position among its siblings for manual ordering."""
    selected = next((item for item in items if item.id == item_id), None)
    if selected is None or direction not in {-1, 1}:
        return False
    siblings = sorted(
        (item for item in items if item.parent_id == selected.parent_id),
        key=lambda item: (item.order, item.created_at),
    )
    current = siblings.index(selected)
    target = current + direction
    if not 0 <= target < len(siblings):
        return False
    siblings[current].order, siblings[target].order = siblings[target].order, siblings[current].order
    return True


def _renumber(items: list[TodoItem], parent_id: str | None) -> None:
    siblings = sorted(
        (item for item in items if item.parent_id == parent_id),
        key=lambda item: (item.order, item.created_at),
    )
    for index, sibling in enumerate(siblings):
        sibling.order = index
