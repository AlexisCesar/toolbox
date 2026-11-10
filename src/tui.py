import asyncio
import ctypes
import os
import platform
from datetime import date, datetime
from pathlib import Path

import psutil
from rich.text import Text
from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.theme import Theme
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Footer, Label, ListItem, ListView, RichLog
from src.views.calendar import CalendarView
from src.views.home import Home
from src.views.markdown_view import MarkdownPreview
from src.views.scripts import Scripts
from src.views.notes import Notes
from src.views.my_projects import MyProjects
from src.views.logs import Logs
from src.views.health_checks import HealthChecks
from src.views.bash import Bash
from src.views.todos import Todos
from src.views.utilities import Utilities
from src.utils.logger import Logger
from src.utils.config import config
from src.utils.gamification import (
    DAILY_LOGIN_BASE_EXP,
    FIRST_THEME_CHANGE_EXP,
    TITLES,
    available_titles,
    calculate_streak,
    level_for_experience,
    render_title_label,
    title_for_code,
)
from src.utils.title_selection_dialog import TitleSelectionDialog
from src.utils.todo_store import TodoStore
from src.utils.seasonal_theme import (
    CHRISTMAS_THEME,
    DEFAULT_THEME,
    HALLOWEEN_THEME,
    SEASONAL_THEMES,
    is_theme_available,
)
from src.utils.themes import NETRUNNER_THEME
from src.utils.addon_manager import AddonError, AddonManager, InstalledAddon
from src.utils.update_checker import check_for_update

from src.views.settings import Settings
from src.views.addons import Addons
from src.views.addon_view import AddonView
from src.version import APP_VERSION

class ToolboxTUI(App):
    """A Textual-based TUI for the Toolbox application."""

    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "tui.tcss"
    VIEW_IDS = {
        0: "home-view",
        1: "bash-view",
        2: "todos-view",
        3: "calendar-view",
        4: "scripts-view",
        5: "logs-view",
        6: "health-checkers-view",
        7: "notes-view",
        8: "markdow-preview-view",
        9: "my-projects-view",
        10: "utilities-view",
        11: "addons-view",
    }
    BINDINGS = [
        ("h", "select_view(0)", "Home"),
        ("b", "select_view(1)", "Bash"),
        ("d", "select_view(2)", "TODO list"),
        ("a", "select_view(3)", "Calendar"),
        ("c", "select_view(4)", "Scripts"),
        ("l", "select_view(5)", "Logs"),
        ("t", "select_view(6)", "Health Checkers"),
        ("n", "select_view(7)", "Notes"),
        ("m", "select_view(8)", "Markdown Viewer"),
        ("p", "select_view(9)", "My Projects"),
        ("u", "select_view(10)", "Utilities"),
        ("e", "select_settings", "Settings"),
        ("g", "select_view(11)", "Addons"),
        ("q", "quit", "Quit")
    ]

    def __init__(self):
        super().__init__()
        self.logger = Logger(self)
        self.todo_store = TodoStore()
        self.addon_manager = AddonManager()
        self._addon_entries: list[InstalledAddon] = []
        self._seasonal_timer = None
        self._runtime_timer = None
        self._runtime_status_label: Label | None = None
        self._profile_status_button: Button | None = None
        self._process = psutil.Process()
        self._runtime_metrics_warning_logged = False
        self._battery_status_warning_logged = False
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
        self.register_theme(
            Theme(
                name=NETRUNNER_THEME,
                primary="#ff1744",
                secondary="#b00020",
                accent="#ff3b5c",
                foreground="#ffe8ec",
                background="#080608",
                surface="#160b0e",
                panel="#10080a",
                boost="#2b0d14",
                warning="#ff6b35",
                error="#ff1744",
                success="#ff4d6d",
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
                with Horizontal(id="profile-slot"):
                    self._profile_status_button = Button(
                        self._profile_status_text(),
                        id="profile-status",
                        flat=True,
                        tooltip=self._profile_tooltip(),
                    )
                    self._profile_status_button.styles.line_pad = 0
                    yield self._profile_status_button
                with Horizontal(id="title-content"):
                    yield Label("Toolbox TUI", id="app-title")
                    yield Label(f" - v{APP_VERSION}", id="version")
                    admin_label = " (Admin)" if self._is_running_as_admin() else ""
                    yield Label(
                        " - " + os_icon + platform.system() + admin_label,
                        id="os-info",
                    )
                self._runtime_status_label = Label(
                    f"{datetime.now():%H:%M:%S  %b %d, %Y}  CPU --  RAM --",
                    id="runtime-status",
                )
                yield self._runtime_status_label
            with Horizontal(id="app-shell"):
                with Vertical(id="sidebar"):
                    yield self._build_sidebar(id="sidebar-list")
                with Vertical(id="main-panel"):
                    yield self._build_main_content()
        yield Footer()

    def _is_running_as_admin(self) -> bool:
        """Return whether this process has administrator or root privileges."""
        try:
            if os.name == "nt":
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            if hasattr(os, "geteuid"):
                return os.geteuid() == 0
        except (AttributeError, OSError) as error:
            self.logger.warn(f"Could not determine administrator privileges: {error}")
        return False

    def _build_sidebar(self, id) -> ListView:
        try:
            self._addon_entries = self.addon_manager.list_installed()
        except AddonError as error:
            self.logger.error(f"Could not load installed Addons: {error}")
            self._addon_entries = []
        captions = self._sidebar_captions(config.theme)
        list_view = ListView(
            *[
                ListItem(Label(Text(item)), classes="sidebar-item")
                for item in captions
            ],
            id=id,
        )
        list_view.index = 0
        return list_view

    def _sidebar_captions(self, theme_name: str | None) -> list[str]:
        halloween_active = theme_name == HALLOWEEN_THEME
        christmas_active = theme_name == CHRISTMAS_THEME
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
            "\U0001F4C5 Calendar",
            "\U0001F4DC Scripts",
            "\U0001F4DD Logs",
            "\U0001F3E5 Health Checkers",
            "\U0001F4D3 Notes",
            "\U0001F4D6 Markdown Preview",
            "\U0001F4C2 My Projects",
            f"\U0001F9F0 Utilities",
        ]
        list_items.append("🧩 Addons")
        list_items.extend(
            f"{addon.icon} {addon.name}"
            if addon.available
            else f"⚠️ {addon.name}"
            for addon in self._addon_entries
        )
        list_items.append(f"{settings_icon} Settings")
        list_items.append(f"{quit_icon} Quit")
        return list_items

    
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
                Utilities(logger=self.logger, id="utilities-view"),
                CalendarView(logger=self.logger, id="calendar-view"),
                Addons(
                    manager=self.addon_manager,
                    logger=self.logger,
                    on_change=self.refresh_addon_navigation,
                    id="addons-view",
                ),
                AddonView(
                    manager=self.addon_manager,
                    logger=self.logger,
                    id="addon-view",
                ),
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
        self._process.cpu_percent()
        self._runtime_timer = self.set_interval(1.0, self._update_runtime_status)
        self.logger.info(f"User configuration loaded from {config.config_path}.")
        if config.gamification_defaults_added:
            self.logger.info("Added missing gamification defaults to the user configuration.")
        if config.gamification_migration_error:
            self.logger.warn(
                "Could not save gamification defaults to the user configuration: "
                f"{config.gamification_migration_error}"
            )
        if not config.experience_is_valid:
            self.logger.warn("Configured gamification experience is invalid; using 0 XP.")
        if not config.selected_title_is_valid:
            self.logger.warn("Configured title is invalid or locked; using Newbie.")
        self._update_profile_status()
        daily_experience, streak_days = self.claim_daily_login()
        if daily_experience:
            self.notify(
                f"Daily login: +{daily_experience} EXP. Streak: {streak_days} day(s).",
                title="Daily login",
            )
        self.logger.info("Toolbox TUI started.")
        self.run_worker(
            self._check_for_updates(),
            name="check-for-updates",
            group="update-check",
            exclusive=True,
        )

    async def _check_for_updates(self) -> None:
        """Check GitHub in a background thread and update Home when needed."""
        try:
            latest_version = await asyncio.to_thread(check_for_update, APP_VERSION)
        except Exception as error:
            if self._running:
                self.logger.warn(f"Could not check for Toolbox updates: {error}")
            return

        if not self._running or latest_version is None:
            return

        self.query_one("#home-view", Home).show_update_notice(latest_version)
        self.logger.info(f"A newer Toolbox release is available: v{latest_version}.")

    def _profile_status_text(self) -> Text:
        """Build the level and selected title, coloring only the title."""
        level = config.level
        title = title_for_code(config.selected_title_code, level)
        if title is None:
            title = available_titles(0)[0]
        return render_title_label(f"Level {level} - ", title)

    def _profile_tooltip(self) -> str:
        """Show XP before the title selection hint on hover."""
        return f"Current EXP: {config.experience}\nClick to select an unlocked title"

    def award_experience(self, amount: int, **gamification_updates: object) -> bool:
        """Persist XP and select a title when the award crosses its unlock level."""
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return False

        previous_level = config.level
        new_experience = config.experience + amount
        new_level = level_for_experience(new_experience)

        changes: dict[str, object] = {"experience": new_experience}
        newly_unlocked = [
            title for title in TITLES if previous_level < title.level <= new_level
        ]
        if newly_unlocked:
            changes["selected_title"] = max(newly_unlocked, key=lambda title: title.level).code
        changes.update(gamification_updates)

        try:
            config.update_gamification(**changes)
        except (OSError, ValueError) as error:
            self.logger.error(f"Could not save gamification progress: {error}")
            return False

        self._update_profile_status()
        return True

    def claim_daily_login(self, today: date | None = None) -> tuple[int, int]:
        """Award the daily login XP once and persist the current streak."""
        current_date = today or date.today()
        date_value = current_date.isoformat()
        if config.last_started_date == date_value and config.daily_exp_received:
            return 0, config.streak_days

        streak_days = calculate_streak(
            config.last_started_date,
            config.streak_days,
            current_date,
        )
        experience = DAILY_LOGIN_BASE_EXP * streak_days
        awarded = self.award_experience(
            experience,
            last_started_date=date_value,
            daily_exp_received=True,
            streak_days=streak_days,
        )
        return (experience if awarded else 0), streak_days

    def award_first_theme_change(self) -> bool:
        """Award the one-time bonus for changing the application theme."""
        if config.first_theme_change_rewarded:
            return False
        return self.award_experience(
            FIRST_THEME_CHANGE_EXP,
            first_theme_change_rewarded=True,
        )

    def _update_profile_status(self) -> None:
        """Refresh the clickable profile summary in the top-left header area."""
        if self._profile_status_button is not None:
            self._profile_status_button.label = self._profile_status_text()
            self._profile_status_button.tooltip = self._profile_tooltip()
            self._profile_status_button.refresh(layout=True)

    def _update_runtime_status(self) -> None:
        """Refresh the local date, resource usage, and available battery status."""
        status_label = self._runtime_status_label
        if status_label is None:
            return

        timestamp = datetime.now().strftime("%H:%M:%S  %b %d, %Y")
        battery_status = self._battery_status_text()
        try:
            cpu_percent = self._process.cpu_percent()
            memory_mb = self._process.memory_info().rss / (1024 * 1024)
        except (psutil.Error, OSError) as error:
            if not self._runtime_metrics_warning_logged:
                self.logger.warn(f"Could not read TUI resource usage: {error}")
                self._runtime_metrics_warning_logged = True
            status_label.update(f"{timestamp}  CPU --  RAM --{battery_status}")
            return

        status_label.update(
            f"{timestamp}  CPU {cpu_percent:.1f}%  RAM {memory_mb:.1f} MB{battery_status}"
        )

    def _battery_status_text(self) -> str:
        """Return the battery percentage and power state when available."""
        try:
            battery = psutil.sensors_battery()
        except (NotImplementedError, OSError, psutil.Error) as error:
            if not self._battery_status_warning_logged:
                self.logger.warn(f"Could not read battery status: {error}")
                self._battery_status_warning_logged = True
            return ""

        if battery is None:
            return ""

        power_state = "Plugged" if battery.power_plugged else "Unplugged"
        return f"  {battery.percent:.0f}% ({power_state})"

    def apply_theme(self, theme_name: str) -> None:
        """Apply a theme and update seasonal navigation decorations."""
        if theme_name in SEASONAL_THEMES and not is_theme_available(theme_name):
            theme_name = DEFAULT_THEME
        halloween_active = theme_name == HALLOWEEN_THEME and is_theme_available(theme_name)
        christmas_active = theme_name == CHRISTMAS_THEME
        netrunner_active = theme_name == NETRUNNER_THEME
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

        if netrunner_active:
            self.add_class("netrunner-theme")
        else:
            self.remove_class("netrunner-theme")

        title = "Toolbox TUI"
        if halloween_active:
            title = "\U0001F987 Toolbox TUI \U0001F383"
        elif christmas_active:
            title = "\U0001F36A Toolbox TUI \U00002603 "
        self.query_one("#app-title", Label).update(title)
        self._render_sidebar_labels(theme_name)

    def _render_sidebar_labels(self, theme_name: str) -> None:
        sidebar = self.query_one("#sidebar-list", ListView)
        labels = [child.query_one(Label) for child in sidebar.children]
        captions = self._sidebar_captions(theme_name)
        decoration = (
            "\U0001F577"
            if theme_name == HALLOWEEN_THEME
            else "\U00002744"
            if theme_name == CHRISTMAS_THEME
            else ""
        )
        for index, (label, caption) in enumerate(zip(labels, captions)):
            marker = f" {decoration}" if decoration and index == self._decoration_row else ""
            label.update(Text(caption + marker))

    def _animate_seasonal_decoration(self) -> None:
        """Move the seasonal spider or snowflake down the sidebar menu."""
        if self.theme not in SEASONAL_THEMES:
            return
        if self.screen.id != "_default":
            return
        self._decoration_row = (self._decoration_row + 1) % max(1, len(self._addon_entries) + 14)
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
        if self._runtime_timer is not None:
            self._runtime_timer.stop()
            self._runtime_timer = None

    def show_markdown_preview(self, path: Path | None = None) -> None:
        """Switch the main content to the markdown viewer and load the selected file."""
        self.query_one("#sidebar-list", ListView).index = 8

        switcher = self.query_one("#main-content-switcher", ContentSwitcher)
        switcher.current = "markdow-preview-view"
        self.query_one("#markdow-preview-view", MarkdownPreview).load_markdown(path)
    

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection changes in the sidebar list view."""
        if event.list_view.id != "sidebar-list":
            return
        self._show_view(event.list_view.index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open and save the title selector from the profile header button."""
        if event.button.id != "profile-status":
            return
        event.stop()
        self.push_screen(
            TitleSelectionDialog(
                logger=self.logger,
                level=config.level,
                selected_code=config.selected_title_code,
            ),
            self._save_selected_title,
        )

    def _save_selected_title(self, selected_code: str | None) -> None:
        """Persist a title selected from the currently unlocked choices."""
        if selected_code is None:
            return
        unlocked_codes = {title.code for title in available_titles(config.level)}
        if selected_code not in unlocked_codes:
            self.logger.warn("Ignored a profile title that is not unlocked.")
            return
        try:
            config.update("gamification", "selected_title", selected_code)
        except OSError as error:
            self.logger.error(f"Could not save the selected profile title: {error}")
            return
        self.logger.info(f"Profile title changed to {config.selected_title_name}.")
        self._update_profile_status()

    def action_select_view(self, view_id: int) -> None:
        """Select a sidebar item and synchronously show its view."""
        list_view = self.query_one("#sidebar-list")
        list_view.index = view_id
        list_view.focus()
        self._show_view(view_id)

    def action_select_settings(self) -> None:
        """Select Settings after any installed Addon tabs in the sidebar."""
        self.action_select_view(12 + len(self._addon_entries))

    def _show_view(self, view_id: int) -> None:
        quit_index = 13 + len(self._addon_entries)
        if view_id == quit_index:
            self.exit()
            return
        if view_id == 12 + len(self._addon_entries):
            self.query_one("#main-content-switcher", ContentSwitcher).current = "settings-view"
            return
        if view_id == 11:
            self.query_one("#main-content-switcher", ContentSwitcher).current = "addons-view"
            return
        addon_index = view_id - 12
        if 0 <= addon_index < len(self._addon_entries):
            addon = self._addon_entries[addon_index]
            self.query_one("#main-content-switcher", ContentSwitcher).current = "addon-view"
            self.query_one("#addon-view", AddonView).load_addon(addon)
            return
        view_name = self.VIEW_IDS.get(view_id)
        if view_name is not None:
            self.query_one("#main-content-switcher", ContentSwitcher).current = view_name

    async def refresh_addon_navigation(self) -> None:
        """Refresh Addon tabs after installation or removal."""
        switcher = self.query_one("#main-content-switcher", ContentSwitcher)
        addon_view = self.query_one("#addon-view", AddonView)
        active_addon_id = addon_view.addon_id if switcher.current == "addon-view" else None
        try:
            self._addon_entries = self.addon_manager.list_installed()
        except AddonError as error:
            self.logger.error(f"Could not refresh installed Addons: {error}")
            return

        sidebar = self.query_one("#sidebar-list", ListView)
        await sidebar.clear()
        await sidebar.mount(
            *(
                ListItem(Label(Text(caption)), classes="sidebar-item")
                for caption in self._sidebar_captions(self.theme)
            )
        )
        remaining_index = next(
            (index for index, addon in enumerate(self._addon_entries) if addon.id == active_addon_id),
            None,
        )
        if active_addon_id is not None and remaining_index is None:
            switcher.current = "addons-view"
            sidebar.index = 11
        elif remaining_index is not None:
            sidebar.index = 12 + remaining_index
        elif switcher.current == "addons-view":
            sidebar.index = 11
        elif switcher.current == "settings-view":
            sidebar.index = 12 + len(self._addon_entries)
        else:
            sidebar.index = min(sidebar.index or 0, len(sidebar.children) - 1)
