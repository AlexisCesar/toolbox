from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, RichLog

class ScriptInspectionDialog(ModalScreen[bool]):
    BINDINGS = [
        ("q", "close", "Close")
    ]
    
    def __init__(self, file_content: str, script_name: str) -> None:
        super().__init__()
        self.file_content = file_content
        self.script_name = script_name

    def compose(self) -> ComposeResult:
        log = RichLog(highlight=True, markup=True, id="script-inspection-log", wrap=True)
        log.can_focus = False
        lexer = "python" if self.script_name.endswith(".py") else "powershell" if self.script_name.endswith(".ps1") else "sql" if self.script_name.endswith(".sql") else "text"
        log.write(Syntax(self.file_content, lexer=lexer, line_numbers=True, word_wrap=True, indent_guides=True, theme="monokai"))
        
        yield Label(f"Viewing {self.script_name}", id="script-inspection-title")
        yield log
        yield Footer()
    
    def action_close(self) -> None:
        self.dismiss()