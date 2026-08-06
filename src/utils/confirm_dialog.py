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
    def __init__(self, message: str = "Are you sure?", askParameters: bool = False, confirmButtonText: str = "Yes", cancelButtonText: str = "No", parametersPlaceholder: str = "Enter parameters...", initialValue: str = "") -> None:
        super().__init__()
        self.message = message
        self.askParameters = askParameters
        self.confirmButtonText = confirmButtonText
        self.cancelButtonText = cancelButtonText
        self.parametersPlaceholder = parametersPlaceholder
        self.initialValue = initialValue

    def compose(self) -> ComposeResult:
        parameters = Input(placeholder=self.parametersPlaceholder, id="dialog-parameters")
        yield Vertical(
            Static(self.message, id="dialog-message"),
            parameters,
            Horizontal(
                Button(self.confirmButtonText, variant="success", id="dialog-confirm-yes"),
                Button(self.cancelButtonText, variant="error", id="dialog-confirm-no"),
                id="dialog-buttons"
            ),
            id="dialog"
        )
        
        if not self.askParameters:
            parameters.styles.display = "none"
        
        if self.initialValue:
            parameters.value = self.initialValue

    def on_button_pressed(self, event: Button.Pressed) -> None:
        parameters = self.query_one("#dialog-parameters", Input).value
        
        self.dismiss(
            ConfirmResult(
                confirmed=event.button.id == "dialog-confirm-yes",
                parameters=parameters,
            )
        )