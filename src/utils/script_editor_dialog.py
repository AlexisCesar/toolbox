from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, Static, TextArea


LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".sh": "bash",
    ".sql": "sql",
    ".ps1": "pwsh",
}


class ScriptEditorDialog(ModalScreen[bool]):
    """Modal editor for a script file."""

    BINDINGS = [
        ("ctrl+s", "save", "Save"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, script_path: Path, file_content: str) -> None:
        super().__init__()
        self.script_path = script_path
        self.file_content = file_content

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Editing {self.script_path.name}", id="script-editor-title"),
            TextArea.code_editor(
                self.file_content,
                id="script-editor-content",
                show_line_numbers=True,
                soft_wrap=True,
                language=LANGUAGE_BY_EXTENSION.get(self.script_path.suffix.lower()),
            ),
            Static("", id="script-editor-status"),
            Horizontal(
                Button("\U0001F4BE Save", variant="success", id="script-editor-save"),
                Button("Cancel", variant="error", id="script-editor-cancel"),
                id="script-editor-buttons",
            ),
            id="script-editor-dialog",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#script-editor-content", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "script-editor-save":
            self.action_save()
        elif event.button.id == "script-editor-cancel":
            self.action_cancel()

    def action_save(self) -> None:
        content = self.query_one("#script-editor-content", TextArea).text
        try:
            self.script_path.write_bytes(content.encode("utf-8"))
        except OSError as error:
            self.query_one("#script-editor-status", Static).update(
                f"Could not save the file: {error}"
            )
            return

        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
