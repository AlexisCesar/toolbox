from pathlib import Path

from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.theme import Theme
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
from src.utils.seasonal_theme import (
    CHRISTMAS_THEME,
    DEFAULT_THEME,
    HALLOWEEN_THEME,
    SEASONAL_THEMES,
    is_theme_available,
)
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
        self._seasonal_timer = None
        self._decoration_row = 0
        self.register_theme(
            Theme(
                name=HALLOWEEN_THEME,
                primary="#ff7a1a",
                secondary="#a855f7",
                accent="#c084fc",
                foreground="#f7eaff",
                background="#120d1a",
                surface="#21152c",
                panel="#1a1124",
                boost="#321b3d",
                warning="#ff9f43",
                error="#ff5a3d",
                success="#ff7a1a",
                dark=True,
            )
        )
        self.register_theme(
            Theme(
                name=CHRISTMAS_THEME,
                primary="#dc2626",
                secondary="#16a34a",
                accent="#f8fafc",
                foreground="#f0fdf4",
                background="#0c1711",
                surface="#14251a",
                panel="#101d16",
                boost="#244330",
                warning="#facc15",
                error="#fb7185",
                success="#22c55e",
                dark=True,
            )
        )

    def compose(self) -> ComposeResult:
        """Create the main layout for the TUI."""
        os_icon = {
            "Linux": "\U0001F427 ",
            "Darwin": "\U0001F34E ",
            "Windows": "\U0001FA9F ",
        }.get(platform.system(), " \u2753 ")

        with Vertical(id="main-container"):
            with Horizontal(id="title-bar"):
                yield Label("Toolbox TUI", id="app-title")
                yield Label(" - v0.1.0", id="version")
                yield Label(" - " + os_icon + platform.system(), id="os-info")
            with Horizontal(id="app-shell"):
                with Vertical(id="sidebar"):
                    yield self._build_sidebar(id="sidebar-list")
                with Vertical(id="main-panel"):
                    yield self._build_main_content()
        yield Footer()


    def _build_sidebar(self, id) -> ListView:
        halloween_active = config.theme == HALLOWEEN_THEME and is_theme_available(config.theme)
        christmas_active = config.theme == CHRISTMAS_THEME and is_theme_available(config.theme)
        home_icon = (
            "\U0001F47B"
            if halloween_active
            else "\U0001F384"
            if christmas_active
            else "\U0001F3E1"
        )
        settings_icon = "\U0001F578\uFE0F" if halloween_active else "\U0001F527"
        quit_icon = (
            "\U0001FAA6"
            if halloween_active
            else "\U0001F98C"
            if christmas_active
            else "\U0001F6AA"
        )
        list_items = [
            f"{home_icon} Home",
            "\U0001F41A Bash",
            "\u2705 TODO list",
            "\U0001F4DC Scripts",
            "\U0001F4DD Logs",
            "\U0001F3E5 Health Checkers",
            "\U0001F4D3 Notes",
            "\U0001F4D6 Markdown Preview",
            "\U0001F4C2 My Projects",
            f"{settings_icon} Settings",
            f"{quit_icon} Quit",
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
        theme_name = config.theme
        if theme_name in SEASONAL_THEMES and not is_theme_available(theme_name):
            theme_name = DEFAULT_THEME
        self.apply_theme(theme_name)
        self.logger.info(f"User configuration loaded from {config.config_path}.")
        self.logger.info("Toolbox TUI started.")

    def apply_theme(self, theme_name: str) -> None:
        """Apply a theme and update seasonal navigation decorations."""
        if theme_name in SEASONAL_THEMES and not is_theme_available(theme_name):
            theme_name = DEFAULT_THEME
        halloween_active = theme_name == HALLOWEEN_THEME and is_theme_available(theme_name)
        christmas_active = theme_name == CHRISTMAS_THEME
        self.theme = theme_name
        if not self.is_mounted:
            return

        if halloween_active or christmas_active:
            if halloween_active:
                self.add_class("halloween-theme")
            else:
                self.remove_class("halloween-theme")
            if christmas_active:
                self.add_class("christmas-theme")
            else:
                self.remove_class("christmas-theme")
            if self._seasonal_timer is None:
                self._seasonal_timer = self.set_interval(0.55, self._animate_seasonal_decoration)
        else:
            self.remove_class("halloween-theme")
            self.remove_class("christmas-theme")
            if self._seasonal_timer is not None:
                self._seasonal_timer.stop()
                self._seasonal_timer = None

        title = "Toolbox TUI"
        if halloween_active:
            title = "\U0001F987 Toolbox TUI \U0001F383"
        elif christmas_active:
            title = "\U0001F36A Toolbox TUI \U00002603 "
        self.query_one("#app-title", Label).update(title)
        self._render_sidebar_labels(theme_name)

    def _render_sidebar_labels(self, theme_name: str) -> None:
        halloween_active = theme_name == HALLOWEEN_THEME
        christmas_active = theme_name == CHRISTMAS_THEME
        sidebar = self.query_one("#sidebar-list", ListView)
        labels = [child.query_one(Label) for child in sidebar.children]
        home_icon = (
            "\U0001F47B"
            if halloween_active
            else "\U0001F384"
            if christmas_active
            else "\U0001F3E1"
        )
        settings_icon = "\U0001F578 " if halloween_active else "\U0001F527"
        quit_icon = (
            "\U0001FAA6"
            if halloween_active
            else "\U0001F98C"
            if christmas_active
            else "\U0001F6AA"
        )
        decoration = (
            "\U0001F577"
            if halloween_active
            else "\U00002744"
            if christmas_active
            else ""
        )
        captions = [
            f"{home_icon} Home",
            "\U0001F41A Bash",
            "\u2705 TODO list",
            "\U0001F4DC Scripts",
            "\U0001F4DD Logs",
            "\U0001F3E5 Health Checkers",
            "\U0001F4D3 Notes",
            "\U0001F4D6 Markdown Preview",
            "\U0001F4C2 My Projects",
            f"{settings_icon} Settings",
            f"{quit_icon} Quit",
        ]
        for index, (label, caption) in enumerate(zip(labels, captions)):
            marker = f" {decoration}" if decoration and index == self._decoration_row else ""
            label.update(caption + marker)

    def _animate_seasonal_decoration(self) -> None:
        """Move the seasonal spider or snowflake down the sidebar menu."""
        if self.theme not in SEASONAL_THEMES:
            return
        if self.screen.id != "_default":
            return
        self._decoration_row = (self._decoration_row + 1) % 11
        try:
            self._render_sidebar_labels(self.theme)
        except NoMatches:
            if self._seasonal_timer is not None:
                self._seasonal_timer.stop()
                self._seasonal_timer = None

    def on_unmount(self) -> None:
        """Stop the seasonal animation when the app is closing."""
        if self._seasonal_timer is not None:
            self._seasonal_timer.stop()
            self._seasonal_timer = None

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
