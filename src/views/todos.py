"""TODO list view for creating and organizing persistent tasks."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Callable

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, ProgressBar, Select, Static

from src.utils.confirm_dialog import ConfirmDialog
from src.utils.config import config
from src.utils.logger import Logger
from src.utils.seasonal_theme import HALLOWEEN_THEME
from src.utils.todo_dialog import TodoDraft, TodoEditorDialog
from src.utils.todo_store import (
    TodoItem,
    TodoStore,
    flatten_todos,
    move_todo,
    remove_todo,
    set_completed,
)


class Todos(Static):
    """Create, edit, and track TODO items with local persistent storage."""

    def __init__(
        self,
        logger: Logger,
        store: TodoStore | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.logger = logger
        self.store = store or TodoStore()
        self.items: list[TodoItem] = []
        self.visible_items: list[TodoItem] = []
        self.sort_mode = "manual"
        self.load_failed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="todos-content"):
            yield Label("TODO list", id="todos-title")
            yield Static("", id="todos-summary")
            yield ProgressBar(total=1, show_eta=False, id="todos-progress")
            yield DataTable(id="todos-table", zebra_stripes=True, cursor_type="row")
            with Horizontal(id="todos-controls"):
                yield Button("\u2795 New task", id="todos-add", flat=True, classes="icon-button")
                yield Button("\u21B3 Sub-item", id="todos-add-child", flat=True, classes="icon-button")
                yield Button("\u270F\uFE0F Edit", id="todos-edit", flat=True, classes="icon-button")
                yield Button("\u2705 Done", id="todos-toggle", flat=True, classes="icon-button")
                yield Button(
                    "\u23F8 Pause",
                    tooltip="Pause or resume the selected item",
                    id="todos-pause",
                    flat=True,
                    classes="icon-button",
                )
                yield Button(
                    "\u274C Delete",
                    variant="error",
                    id="todos-delete",
                    flat=True,
                    classes="icon-button",
                )
                yield Button(
                    "\u2B06 Move up",
                    tooltip="Move the selected item up",
                    id="todos-up",
                    flat=True,
                    classes="icon-button",
                )
                yield Button(
                    "\u2B07 Move down",
                    tooltip="Move the selected item down",
                    id="todos-down",
                    flat=True,
                    classes="icon-button",
                )
                yield Select(
                    (("Manual order", "manual"), ("Created time", "created"), ("Priority", "priority")),
                    value="manual",
                    allow_blank=False,
                    id="todos-sort",
                )

    def on_mount(self) -> None:
        self.load_items()
        if self.load_failed or not config.todo_startup_notification:
            return
        pending_count = sum(not item.completed for item in self.items)
        if pending_count:
            self.logger.info(f"There are {pending_count} pending TODO item(s).")
            self.app.notify(
                f"You have {pending_count} pending TODO item(s).",
                title="TODO list",
                severity="warning",
            )

    def on_show(self) -> None:
        """Refresh seasonal priority markers when returning to the TODO list."""
        self.refresh_table()

    def load_items(self) -> None:
        """Read persisted tasks once the view is attached to the app."""
        try:
            self.items = self.store.load()
        except (OSError, ValueError) as error:
            self.items = []
            self.load_failed = True
            self.logger.error(f"Could not load TODO items from {self.store.path}: {error}")
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one("#todos-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Task", "Status", "Priority", "Created")
        self.visible_items = flatten_todos(self.items, self.sort_mode)

        for item in self.visible_items:
            is_sub_item = item.parent_id is not None
            title = f"  \u21B3 {item.title}" if is_sub_item else item.title
            task_label = f"{title}\n{item.description}" if item.description else title
            if item.completed:
                status = "\u2713 Done"
            elif item.paused:
                status = "\u2161 Paused"
            else:
                status = "\u25CB Pending"
            priority_emoji = "\U0001F480" if (
                item.priority == "high"
                and getattr(self.app, "theme", None) == HALLOWEEN_THEME
            ) else "\U0001F534"
            priority_text = {
                "low": Text("\U0001F7E2 Low", style="green"),
                "medium": Text("\U0001F7E1 Medium", style="yellow"),
                "high": Text(f"{priority_emoji} High", style="red"),
            }[item.priority]
            try:
                created = datetime.fromisoformat(item.created_at).astimezone().strftime("%Y-%m-%d %H:%M")
            except ValueError:
                created = item.created_at
            table.add_row(
                task_label,
                status,
                priority_text,
                created,
                height=2 if item.description else 1,
                key=item.id,
            )

        completed_count = sum(item.completed for item in self.items)
        pending_count = len(self.items) - completed_count
        paused_count = sum(item.paused and not item.completed for item in self.items)
        self.query_one("#todos-summary", Static).update(
            f"{pending_count} pending · {completed_count} of {len(self.items)} completed · {paused_count} paused"
            + (" · Could not load the saved list; changes are disabled." if self.load_failed else "")
        )
        progress = self.query_one("#todos-progress", ProgressBar)
        progress.update(total=max(len(self.items), 1), progress=completed_count)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "todos-add": self.action_add,
            "todos-add-child": self.action_add_sub_item,
            "todos-edit": self.action_edit,
            "todos-toggle": self.action_toggle_completed,
            "todos-pause": self.action_toggle_paused,
            "todos-delete": self.action_delete,
            "todos-up": lambda: self.action_move(-1),
            "todos-down": lambda: self.action_move(1),
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            action()

    @on(Select.Changed, "#todos-sort")
    def on_sort_changed(self, event: Select.Changed) -> None:
        if event.value in {"manual", "created", "priority"}:
            self.sort_mode = event.value
            self.refresh_table()

    def action_add(self) -> None:
        if self.load_failed:
            return
        self.app.push_screen(
            TodoEditorDialog(logger=self.logger),
            callback=lambda draft: self.save_new_item(draft, parent_id=None),
        )

    def action_add_sub_item(self) -> None:
        item = self.selected_item()
        if item is None:
            return
        if item.parent_id is not None:
            self.logger.warn("Sub-items can only be added to a top-level TODO item.")
            return
        if self.load_failed:
            return
        self.app.push_screen(
            TodoEditorDialog(logger=self.logger),
            callback=lambda draft: self.save_new_item(draft, parent_id=item.id),
        )

    def save_new_item(self, draft: TodoDraft | None, parent_id: str | None) -> None:
        if draft is None or self.load_failed:
            return
        parent = self.find_item(parent_id) if parent_id else None
        item = TodoItem(
            title=draft.title,
            description=draft.description,
            priority=draft.priority,
            parent_id=parent_id,
            completed=parent.completed if parent else False,
            order=max((task.order for task in self.items if task.parent_id == parent_id), default=-1) + 1,
        )
        kind = "sub-item" if parent_id else "task"
        self.commit_change(
            f"Added TODO {kind} '{item.title}'.",
            lambda: self.items.append(item),
        )

    def action_edit(self) -> None:
        item = self.selected_item()
        if item is None or self.load_failed:
            return
        self.app.push_screen(
            TodoEditorDialog(logger=self.logger, initial=item),
            callback=lambda draft: self.save_edited_item(item.id, draft),
        )

    def save_edited_item(self, item_id: str, draft: TodoDraft | None) -> None:
        if draft is None or self.load_failed:
            return
        item = self.find_item(item_id)
        if item is None:
            self.logger.warn("The selected TODO item no longer exists.")
            return

        def update() -> bool:
            item.title = draft.title
            item.description = draft.description
            item.priority = draft.priority
            return True

        self.commit_change(f"Updated TODO item '{draft.title}'.", update)

    def action_toggle_completed(self) -> None:
        item = self.selected_item()
        if item is None or self.load_failed:
            return
        completed = not item.completed

        def toggle() -> bool:
            return set_completed(self.items, item.id)

        detail = " (including its sub-items)" if item.parent_id is None else ""
        state = "completed" if completed else "reopened"
        self.commit_change(f"TODO item '{item.title}' {state}{detail}.", toggle)

    def action_toggle_paused(self) -> None:
        item = self.selected_item()
        if item is None or self.load_failed:
            return
        if item.completed:
            self.logger.warn("Reopen a completed TODO item before pausing it.")
            return
        paused = not item.paused

        def toggle() -> bool:
            item.paused = paused
            return True

        state = "paused" if paused else "resumed"
        self.commit_change(f"TODO item '{item.title}' {state}.", toggle)

    def action_delete(self) -> None:
        item = self.selected_item()
        if item is None or self.load_failed:
            return
        child_count = sum(task.parent_id == item.id for task in self.items)
        message = f"Delete '{item.title}'?"
        if child_count:
            message += f"\nThis will also delete {child_count} sub-item(s)."
        self.app.push_screen(
            ConfirmDialog(message, confirmButtonText="Delete", cancelButtonText="Cancel"),
            callback=lambda result: self.confirm_delete(result.confirmed, item.id),
        )

    def confirm_delete(self, confirmed: bool, item_id: str) -> None:
        if not confirmed or self.load_failed:
            return
        item = self.find_item(item_id)
        if item is None:
            self.logger.warn("The selected TODO item no longer exists.")
            return
        title = item.title

        def delete() -> bool:
            return bool(remove_todo(self.items, item_id))

        self.commit_change(f"Deleted TODO item '{title}' and any sub-items.", delete)

    def action_move(self, direction: int) -> None:
        item = self.selected_item()
        if item is None or self.load_failed:
            return
        if self.sort_mode != "manual":
            self.sort_mode = "manual"
            self.query_one("#todos-sort", Select).value = "manual"

        def move() -> bool:
            return move_todo(self.items, item.id, direction)

        label = "up" if direction < 0 else "down"
        if not self.commit_change(f"Moved TODO item '{item.title}' {label}.", move, log_when_unchanged=False):
            self.logger.warn(f"TODO item '{item.title}' cannot move further {label}.")

    def selected_item(self) -> TodoItem | None:
        table = self.query_one("#todos-table", DataTable)
        row_index = table.cursor_row
        if row_index is None or not 0 <= row_index < len(self.visible_items):
            self.logger.warn("Select a TODO item first.")
            return None
        return self.visible_items[row_index]

    def find_item(self, item_id: str) -> TodoItem | None:
        return next((item for item in self.items if item.id == item_id), None)

    def commit_change(
        self,
        log_message: str,
        change: Callable[[], bool | None],
        *,
        log_when_unchanged: bool = True,
    ) -> bool:
        if self.load_failed:
            return False
        previous_items = deepcopy(self.items)
        changed = change()
        if changed is False:
            self.items = previous_items
            self.refresh_table()
            if log_when_unchanged:
                self.logger.warn("The TODO list was not changed.")
            return False
        try:
            self.store.save(self.items)
        except (OSError, ValueError) as error:
            self.items = previous_items
            self.logger.error(f"Could not save TODO items to {self.store.path}: {error}")
            self.refresh_table()
            return False
        self.logger.info(log_message)
        self.refresh_table()
        return True
