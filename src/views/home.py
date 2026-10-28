from src.utils.seasonal_theme import (
    CHRISTMAS_THEME,
    HALLOWEEN_THEME,
    is_halloween_season,
    is_theme_available,
)
from src.utils.config import config

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Rule, Static


LOGO_ASCII_ART = """[bold #ff5f00]
         ___
  ______//_\\\\______
 /                 \\
|________ _ ________|
 |       |_|       |
 |                 |
 |                 |
 |_________________| [/bold #ff5f00]"""

INSTRUCTIONS = """[bold]Select an option from the sidebar to get started.[/bold]

First time using the Toolbox? Configure your directories, log folders, health checks, theme and more on the [bold #5f5fff]Settings[/bold #5f5fff] tab.

[bold]Tips:[/bold]

- Need to copy something from the screen such as logs? Hold down the [bold #5f5fff]SHIFT[/bold #5f5fff] key to select text from anywhere on the screen.

- Generating a [u]scripts configuration file[/u] through the [bold #5f5fff]Settings[/bold #5f5fff] tab enable script parameter history. Trust me, it's very helpful!

- You can edit and save text/script files using the [bold #5f5fff]Notes[/bold #5f5fff] tab.

- Open [bold #5f5fff]Bash[/bold #5f5fff] (shortcut [bold]b[/bold]) for an interactive shell inside Toolbox. On Windows, install Git for Windows first. Use Ctrl+G to return to the sidebar; Ctrl+C interrupts the running command.

- Add local or network log folders in [bold #5f5fff]Settings[/bold #5f5fff], then open them from the [bold #5f5fff]Logs[/bold #5f5fff] tab. Log files open at their latest entries.

- Add HTTP endpoint or TCP health checks in [bold #5f5fff]Settings[/bold #5f5fff]. They run while the [bold #5f5fff]Health Checkers[/bold #5f5fff] tab is open.

- Track tasks in the [bold #5f5fff]TODO list[/bold #5f5fff] tab (shortcut [bold]d[/bold]). Create tasks and sub-items, set priorities, pause work, and reorder the list. TODO items are saved between launches; startup notifications can be changed in [bold #5f5fff]Settings[/bold #5f5fff].
"""

class Home(Static):
    """A simple home view for the Toolbox TUI."""

    def instructions(self) -> str:
        """Return the home guidance with seasonal information when available."""
        if not is_halloween_season():
            return INSTRUCTIONS
        return INSTRUCTIONS.replace(
            "[bold]Tips:[/bold]",
            "[bold]Tips:[/bold]\n\n- 🎃 The Halloween theme is available in Settings from October 1 through November 10.",
            1,
        )

    def logo_art(self, theme_name: str | None) -> str:
        """Add seasonal greetings directly after the toolbox base."""
        if theme_name == HALLOWEEN_THEME:
            return LOGO_ASCII_ART.replace(
                "|_________________| [/bold #ff5f00]",
                "|_________________|[/bold #ff5f00] [#888888]"
                "🧛 Witching you a spooktacular Halloween! 🐈‍⬛[/#888888]",
            )
        if theme_name == CHRISTMAS_THEME:
            return LOGO_ASCII_ART.replace(
                "[bold #ff5f00]", "[bold #f8fafc]", 1
            ).replace(
                "|_________________| [/bold #ff5f00]",
                "|_________________|[/bold #f8fafc] [#d1fae5]"
                "🎁 Wishing you a Merry Christmas![/#d1fae5]",
            )
        else:
            return LOGO_ASCII_ART

    def compose(self) -> ComposeResult:
        """Create the layout for the home view."""
        with VerticalScroll():
            theme_name = config.theme if is_theme_available(config.theme) else None
            yield Static(self.logo_art(theme_name), id="ascii-art")
            yield Rule(line_style="dashed")
            yield Static(self.instructions(), id="home-instructions")

    def on_show(self) -> None:
        """Refresh seasonal guidance when returning to the home screen."""
        self.query_one("#home-instructions", Static).update(self.instructions())
        theme_name = getattr(self.app, "theme", None)
        if theme_name not in {HALLOWEEN_THEME, CHRISTMAS_THEME} or not is_theme_available(theme_name):
            theme_name = None
        self.query_one("#ascii-art", Static).update(self.logo_art(theme_name))
