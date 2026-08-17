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

First time using the Toolbox? Configure your directories, theme and more on the [bold #5f5fff]Settings[/bold #5f5fff] tab.

[bold]Tips:[/bold]

- Need to copy something from the screen such as logs? Hold down the [bold #5f5fff]SHIFT[/bold #5f5fff] key to select text from anywhere on the screen.

- Generating a [u]scripts configuration file[/u] through the [bold #5f5fff]Settings[/bold #5f5fff] tab enable script parameter history. Trust me, it's very helpful!

- You can edit and save text/script files using the [bold #5f5fff]Notes[/bold #5f5fff] tab.
"""

class Home(Static):
    """A simple home view for the Toolbox TUI."""

    def compose(self) -> ComposeResult:
        """Create the layout for the home view."""
        with VerticalScroll():
            yield Static(LOGO_ASCII_ART, id="ascii-art")
            yield Rule(line_style="dashed")
            yield Static(INSTRUCTIONS, id="home-instructions")