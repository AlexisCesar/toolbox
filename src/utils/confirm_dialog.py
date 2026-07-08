from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label

class ConfirmDialog(ModalScreen[bool]):
    """A reusable modal confirmation dialog."""
    def __init__(self, message: str = "Are you sure?") -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self.message, id="message"),
            Button("Yes", variant="success", id="confirm-yes"),
            Button("No", variant="error", id="confirm-no"),
            id="dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")
