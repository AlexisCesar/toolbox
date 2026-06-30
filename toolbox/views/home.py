from textual.app import ComposeResult
from textual.widgets import Label, Rule, Static


class Home(Static):
    """A simple home view for the Toolbox TUI."""

    def compose(self) -> ComposeResult:
        """Create the layout for the home view."""
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
        yield Label("Select an option from the sidebar to get started.\n\n"
                    + "First time using the Toolbox? Configure scripts and paths on the Settings tab.", id="home-instructions")
        yield Rule(line_style="dashed")
        yield Label("Dev log:", id="devlog")