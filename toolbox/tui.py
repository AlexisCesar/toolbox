from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Placeholder

class ToolboxTUI(App):
    """A Textual-based TUI for the Toolbox application."""

    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "tui.css"
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        """Create the main layout for the TUI."""
        with Vertical():
            yield Placeholder(label="Title bar", id="title-bar")
            with Horizontal():
                yield Placeholder(label="Sidebar", id="sidebar")
                yield Placeholder(label="Main content", id="main-content")
        yield Footer()
