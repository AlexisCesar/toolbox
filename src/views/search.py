from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, Select, Static

RESOURCES = """Everything
Scripts
Logs
""".splitlines()

class Search(Static):
    """Search view for the Toolbox TUI allowing semantic search across all resources."""

    def compose(self) -> ComposeResult:
        """Create the layout for the search view."""
        with VerticalScroll():
            with Horizontal():
                yield Label("Select resource type:")
                yield Select((line, line) for line in RESOURCES)