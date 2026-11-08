"""Dialog for editing a script's catalog description."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, Static, TextArea


class ScriptDescriptionDialog(ModalScreen[str | None]):
    """Edit and return a script description, or dismiss without saving."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, script_name: str, description: str) -> None:
        super().__init__()
        self.script_name = script_name
        self.description = description

    def compose(self) -> ComposeResult:
        with Vertical(id="script-description-dialog"):
            yield Label("Update Description", id="script-description-title")
            yield Static(self.script_name, id="script-description-script-name")
            yield TextArea(self.description, id="script-description-input", soft_wrap=True)
            with Horizontal(id="script-description-buttons"):
                yield Button("Save", variant="primary", id="script-description-save")
                yield Button("Cancel", id="script-description-cancel")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#script-description-input", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "script-description-save":
            description = self.query_one("#script-description-input", TextArea).text
            self.dismiss(description)
        elif event.button.id == "script-description-cancel":
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)
