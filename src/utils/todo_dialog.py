"""Modal editor for TODO item details."""

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static, TextArea

from src.utils.logger import Logger
from src.utils.todo_store import Priority, TodoItem


@dataclass(frozen=True)
class TodoDraft:
    title: str
    description: str
    priority: Priority


class TodoEditorDialog(ModalScreen[TodoDraft | None]):
    """Collect a title, description, and priority for a TODO item."""

    def __init__(self, logger: Logger, initial: TodoItem | None = None) -> None:
        super().__init__()
        self.logger = logger
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="todo-editor-dialog"):
            yield Static(
                "Edit TODO item" if self.initial else "New TODO item",
                id="todo-editor-title",
            )
            yield Static("Title", classes="todo-editor-label")
            yield Input(
                value=self.initial.title if self.initial else "",
                placeholder="What needs to get done?",
                id="todo-editor-name",
            )
            yield Static("Description", classes="todo-editor-label")
            yield TextArea(
                self.initial.description if self.initial else "",
                id="todo-editor-description",
                soft_wrap=True,
            )
            yield Static("Priority", classes="todo-editor-label")
            yield Select(
                (("🟢 Low", "low"), ("🟡 Medium", "medium"), ("🔴 High", "high")),
                value=self.initial.priority if self.initial else "medium",
                allow_blank=False,
                id="todo-editor-priority",
            )
            yield Static("", id="todo-editor-error")
            with Horizontal(id="todo-editor-buttons"):
                yield Button("Save", variant="success", id="todo-editor-save")
                yield Button("Cancel", id="todo-editor-cancel")

    def on_mount(self) -> None:
        self.query_one("#todo-editor-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "todo-editor-cancel":
            self.dismiss(None)
        elif event.button.id == "todo-editor-save":
            self.save_item()

    def save_item(self) -> None:
        title = self.query_one("#todo-editor-name", Input).value.strip()
        description = self.query_one("#todo-editor-description", TextArea).text.strip()
        priority = self.query_one("#todo-editor-priority", Select).value
        error = self.query_one("#todo-editor-error", Static)
        if not title:
            self.logger.warn("A TODO title is required.")
            error.update("Enter a title for this TODO item.")
            return
        if priority not in {"low", "medium", "high"}:
            self.logger.error("The TODO priority selection is invalid.")
            error.update("Choose a valid priority.")
            return
        self.dismiss(TodoDraft(title, description, priority))
