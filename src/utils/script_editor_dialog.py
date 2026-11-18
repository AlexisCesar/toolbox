from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Label, Static, TextArea

from src.utils.vim_motions import VimTextArea


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
        self.saved_content = file_content

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Label(f"Editing {self.script_path.name}", id="script-editor-title"),
                Checkbox("Vim motions", id="script-editor-vim-toggle"),
                id="script-editor-header",
            ),
            VimTextArea(
                self.file_content,
                id="script-editor-content",
                show_line_numbers=True,
                soft_wrap=True,
                language=LANGUAGE_BY_EXTENSION.get(self.script_path.suffix.lower()),
                theme="monokai",
                tab_behavior="indent",
                on_mode_changed=self._update_vim_mode,
                on_command_changed=self._update_vim_command,
                on_command_submitted=self._execute_vim_command,
                on_command_result=self._show_vim_result,
            ),
            Horizontal(
                Static("", id="script-editor-status"),
                Static("", id="script-editor-command", markup=False),
                Static("", id="script-editor-vim-mode", markup=False),
                id="script-editor-footer",
            ),
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

    @on(Checkbox.Changed, "#script-editor-vim-toggle")
    def on_vim_toggle_changed(self, event: Checkbox.Changed) -> None:
        editor = self.query_one("#script-editor-content", VimTextArea)
        editor.vim_motions.set_enabled(event.value)
        editor.focus()

    def _update_vim_mode(self, mode: str) -> None:
        mode_label = self.query_one("#script-editor-vim-mode", Static)
        mode_label.update(mode)
        mode_label.display = bool(mode)

    def _update_vim_command(self, command: str) -> None:
        self.query_one("#script-editor-command", Static).update(command)

    def _show_vim_result(self, message: str) -> None:
        self.query_one("#script-editor-status", Static).update(message)

    def _execute_vim_command(self, command: str) -> None:
        editor = self.query_one("#script-editor-content", VimTextArea)
        if command in {"w", "write"}:
            self._write_content(editor.text)
        elif command in {"q", "quit"}:
            if editor.text != self.saved_content:
                self._show_vim_result("E37: No write since last change")
                return
            self.dismiss(False)
        elif command in {"q!", "quit!"}:
            self.dismiss(False)
        elif command in {"wq", "x"}:
            if self._write_content(editor.text):
                self.dismiss(True)
        else:
            self._show_vim_result(f"E492: Not an editor command: {command}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "script-editor-save":
            self.action_save()
        elif event.button.id == "script-editor-cancel":
            self.action_cancel()

    def action_save(self) -> None:
        content = self.query_one("#script-editor-content", TextArea).text
        if self._write_content(content):
            self.dismiss(True)

    def _write_content(self, content: str) -> bool:
        try:
            self.script_path.write_bytes(content.encode("utf-8"))
        except OSError as error:
            self._show_vim_result(f"Could not save the file: {error}")
            return False

        self.saved_content = content
        self._show_vim_result("Written")
        return True

    def action_cancel(self) -> None:
        self.dismiss(False)
