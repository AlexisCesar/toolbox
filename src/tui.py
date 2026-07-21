from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import ContentSwitcher, Footer, Label, ListItem, ListView, Log, Placeholder, RichLog
from src.views.home import Home
from src.views.search import Search
from src.views.scripts import Scripts
from src.utils.logger import Logger
from src.utils.config import config
import platform

from src.views.settings import Settings

class ToolboxTUI(App):
    """A Textual-based TUI for the Toolbox application."""

    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "tui.tcss"
    BINDINGS = [
        ("h", "select_view(0)", "Home"),
        ("s", "select_view(1)", "Search"),
        ("c", "select_view(2)", "Scripts"),
        ("l", "select_view(3)", "Logs"),
        ("t", "select_view(4)", "Health Checkers"),
        ("e", "select_view(5)", "Settings"),
        ("q", "quit", "Quit")
    ]

    def __init__(self):
        super().__init__()
        self.logger = Logger(self)

    def compose(self) -> ComposeResult:
        """Create the main layout for the TUI."""
        os_icon = {
            "Linux": "🐧 ",
            "Darwin": "🍎 ",
            "Windows": "🪟 "
        }.get(platform.system(), " ❓ ")

        with Vertical(id="main-container"):
            with Horizontal(id="title-bar"):
                yield Label("Toolbox TUI")
                yield Label(" - v0.1.0", id="version")
                yield Label(" - " + os_icon + platform.system(), id="os-info")
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
        log = RichLog(id="log", highlight=True, markup=True, wrap=True)
        container = Container(
            ContentSwitcher(
                Home(id="home-view"),
                Search(id="search-view"),
                Scripts(logger=self.logger, id="scripts-view"),
                Placeholder(label="Logs view", id="logs-view"),
                Placeholder(label="Health Checkers view", id="health-checkers-view"),
                Settings(logger=self.logger, id="settings-view"),
                initial="home-view",
                id="main-content-switcher"
            ),
            log
        )
        return container


    def on_mount(self) -> None:
        self.query_one("#sidebar-list").focus()
        self.theme = config.theme
        self.logger.info("Toolbox TUI started.")
    

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
                App.exit(self)

    def action_select_view(self, view_id: int) -> None:
        list_view = self.query_one("#sidebar-list")
        list_view.index = view_id
        list_view.focus()

        selected_item = list_view.highlighted_child
        if selected_item is not None:
            list_view.post_message(
                ListView.Selected(list_view, item=selected_item, index=view_id)
            )