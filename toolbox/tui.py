from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import ContentSwitcher, Footer, Label, ListItem, ListView, Log, Placeholder
from toolbox.views.home import Home

class ToolboxTUI(App):
    """A Textual-based TUI for the Toolbox application."""

    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "tui.css"
    BINDINGS = [
        ("h", "select_view(0)", "Home"),
        ("s", "select_view(1)", "Search"),
        ("c", "select_view(2)", "Scripts"),
        ("l", "select_view(3)", "Logs"),
        ("t", "select_view(4)", "Health Checkers"),
        ("e", "select_view(5)", "Settings"),
        ("q", "quit", "Quit")
    ]

    def compose(self) -> ComposeResult:
        """Create the main layout for the TUI."""
        with Vertical(id="main-container"):
            with Horizontal(id="title-bar"):
                yield Label("Toolbox TUI")
                yield Label(" - v0.1.0", id="version")
            with Horizontal(id="app-shell"):
                with Vertical(id="sidebar"):
                    yield self._build_sidebar(id="sidebar-list")
                with Vertical(id="main-panel"):
                    yield self._build_main_content()
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

    
    def _build_main_content(self) -> Container:
        """Create the main content area."""
        log = Log(id="log")
        container = Container(
            ContentSwitcher(
                Home(id="home-view"),
                Placeholder(label="Search view", id="search-view"),
                Placeholder(label="Scripts view", id="scripts-view"),
                Placeholder(label="Logs view", id="logs-view"),
                Placeholder(label="Health Checkers view", id="health-checkers-view"),
                Placeholder(label="Settings view", id="settings-view"),
                initial="home-view",
                id="main-content-switcher"
            ),
            log
        )
        return container


    def on_mount(self) -> None:
        """Set focus to the sidebar on mount."""
        self.query_one("#sidebar-list").focus()
        self.theme = "tokyo-night"

        self.log_message("Toolbox TUI started.")

    
    def log_message(self, message: str, level: str = "info") -> None:
        """Log a message to the log panel."""
        log = self.query_one("#log", Log)
        log.write(f"[{level.upper()}] {message}\n")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection changes in the sidebar list view."""
        switcher = self.query_one("#main-content-switcher", ContentSwitcher)

        match event.list_view.index:
            case 0:
                switcher.current = "home-view"
            case 1:
                switcher.current = "search-view"
            case 2:
                switcher.current = "scripts-view"
            case 3:
                switcher.current = "logs-view"
            case 4:
                switcher.current = "health-checkers-view"
            case 5:
                switcher.current = "settings-view"
            case 6:
                App.exit()

    def action_select_view(self, view_id: int) -> None:
        list_view = self.query_one("#sidebar-list")
        list_view.index = view_id
        list_view.focus()

        selected_item = list_view.highlighted_child
        if selected_item is not None:
            list_view.post_message(
                ListView.Selected(list_view, item=selected_item, index=view_id)
            )