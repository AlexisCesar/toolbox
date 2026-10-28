from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import ContentSwitcher, Footer, Label, ListItem, ListView, RichLog
from src.views.home import Home
from src.views.markdown_view import MarkdownPreview
from src.views.scripts import Scripts
from src.views.notes import Notes
from src.views.my_projects import MyProjects
from src.views.logs import Logs
from src.views.health_checks import HealthChecks
from src.views.bash import Bash
from src.views.todos import Todos
from src.utils.logger import Logger
from src.utils.config import config
from src.utils.todo_store import TodoStore
import platform

from src.views.settings import Settings

class ToolboxTUI(App):
    """A Textual-based TUI for the Toolbox application."""

    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "tui.tcss"
    BINDINGS = [
        ("h", "select_view(0)", "Home"),
        ("b", "select_view(1)", "Bash"),
        ("d", "select_view(2)", "TODO list"),
        ("c", "select_view(3)", "Scripts"),
        ("l", "select_view(4)", "Logs"),
        ("t", "select_view(5)", "Health Checkers"),
        ("n", "select_view(6)", "Notes"),
        ("m", "select_view(7)", "Markdown Viewer"),
        ("p", "select_view(8)", "My Projects"),
        ("e", "select_view(9)", "Settings"),
        ("q", "quit", "Quit")
    ]

    def __init__(self):
        super().__init__()
        self.logger = Logger(self)
        self.todo_store = TodoStore()

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
            "🐚 Bash",
            "✅ TODO list",
            "📜 Scripts",
            "📝 Logs",
            "🏥 Health Checkers",
            "📓 Notes",
            "📖 Markdown Preview",
            "📂 My Projects",
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
                Scripts(logger=self.logger, id="scripts-view"),
                Logs(logger=self.logger, id="logs-view"),
                HealthChecks(logger=self.logger, id="health-checkers-view"),
                Settings(logger=self.logger, id="settings-view"),
                Notes(logger=self.logger, id="notes-view"),
                MarkdownPreview(logger=self.logger, id="markdow-preview-view"),
                MyProjects(logger=self.logger, id="my-projects-view"),
                Bash(logger=self.logger, id="bash-view"),
                Todos(logger=self.logger, store=self.todo_store, id="todos-view"),
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

    def show_markdown_preview(self, path: Path | None = None) -> None:
        """Switch the main content to the markdown viewer and load the selected file."""
        self.query_one("#sidebar-list", ListView).index = 7

        switcher = self.query_one("#main-content-switcher", ContentSwitcher)
        switcher.current = "markdow-preview-view"
        self.query_one("#markdow-preview-view", MarkdownPreview).load_markdown(path)
    

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection changes in the sidebar list view."""
        if event.list_view.id != "sidebar-list":
            return

        switcher = self.query_one("#main-content-switcher", ContentSwitcher)

        match event.list_view.index:
            case 0:
                switcher.current = "home-view"
            case 1:
                switcher.current = "bash-view"
            case 2:
                switcher.current = "todos-view"
            case 3:
                switcher.current = "scripts-view"
            case 4:
                switcher.current = "logs-view"
            case 5:
                switcher.current = "health-checkers-view"
            case 6:
                switcher.current = "notes-view"
            case 7:
                switcher.current = "markdow-preview-view"
            case 8:
                switcher.current = "my-projects-view"
            case 9:
                switcher.current = "settings-view"
            case 10:
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
