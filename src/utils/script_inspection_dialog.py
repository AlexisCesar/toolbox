from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, TextArea

from src.utils.script_editor_dialog import LANGUAGE_BY_EXTENSION

class ScriptInspectionDialog(ModalScreen[bool]):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
    ]
    
    def __init__(self, file_content: str, script_name: str) -> None:
        super().__init__()
        self.file_content = file_content
        self.script_name = script_name

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Viewing {self.script_name}", id="script-inspection-title"),
            TextArea.code_editor(
                self.file_content,
                id="script-inspection-content",
                read_only=True,
                show_line_numbers=True,
                soft_wrap=True,
                language=LANGUAGE_BY_EXTENSION.get(self._file_extension()),
            ),
            Horizontal(
                Button("Close", variant="primary", id="script-inspection-close"),
                id="script-inspection-buttons",
            ),
            id="script-inspection-dialog",
        )
        yield Footer()

    def _file_extension(self) -> str:
        return f".{self.script_name.rsplit('.', 1)[-1].lower()}" if "." in self.script_name else ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "script-inspection-close":
            self.action_close()

    def action_close(self) -> None:
        self.dismiss()
