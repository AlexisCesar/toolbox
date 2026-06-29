from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, ListItem, ListView, Placeholder, Static

class ToolboxTUI(App):
    """A Textual-based TUI for the Toolbox application."""

    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "tui.css"
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        """Create the main layout for the TUI."""
        with Vertical(id="main-container"):
            with Horizontal(id="title-bar"):
                yield Label("Toolbox TUI")
                yield Label(" - v0.1.0", id="version")
            with Horizontal(id="app-shell"):
                with Vertical(id="sidebar"):
                    yield self._build_sidebar(id="sidebar-list")
                yield Placeholder(label="Main content", id="main-content")
        yield Footer()


    def _build_sidebar(self, id) -> ListView:
        list_items = [
            "🏡 Home",
            "🔍 Search",
            "📜 Scripts",
            "📝 Logs",
            "🏥 Health Checkers",
            "🔧 Settings",
            "🚪 Quit"
        ]
        list_view = ListView(*[ListItem(Label(item), classes="sidebar-item") for item in list_items], id=id)
        list_view.index = 0
        return list_view

    def on_mount(self) -> None:
        """Set focus to the sidebar on mount."""
        self.query_one("#sidebar-list").focus()
        self.theme = "tokyo-night"