from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Rule, Static


class Home(Static):
    """A simple home view for the Toolbox TUI."""

    def compose(self) -> ComposeResult:
        """Create the layout for the home view."""
        with VerticalScroll():
            yield Label("""
         ___
  ______//_\\\\______
 /                 \\
|________ _ ________|
 |       |_|       |
 |                 |
 |                 |
 |_________________| 
        """, id="ascii-art")
            yield Rule(line_style="dashed")
            yield Label("Select an option from the sidebar to get started.\n\n"
                        + "First time using the Toolbox? Configure your paths and more on the Settings tab.", id="home-instructions")