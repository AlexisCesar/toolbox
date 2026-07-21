from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static
from dataclasses import dataclass

@dataclass
class ConfirmResult:
    confirmed: bool
    parameters: str

class ConfirmDialog(ModalScreen[ConfirmResult]):
    """A reusable modal confirmation dialog."""
    def __init__(self, message: str = "Are you sure?", askParameters: bool = False) -> None:
        super().__init__()
        self.message = message
        self.askParameters = askParameters

    def compose(self) -> ComposeResult:
        parameters = Input(placeholder="Enter parameters...", id="dialog-parameters")
        yield Vertical(
            Static(self.message, id="dialog-message"),
            parameters,
            Horizontal(
                Button("Yes", variant="success", id="dialog-confirm-yes"),
                Button("No", variant="error", id="dialog-confirm-no"),
                id="dialog-buttons"
            ),
            id="dialog"
        )
        
        if not self.askParameters:
            parameters.styles.display = "none"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        parameters = self.query_one("#dialog-parameters", Input).value
        
        self.dismiss(
            ConfirmResult(
                confirmed=event.button.id == "dialog-confirm-yes",
                parameters=parameters,
            )
        )