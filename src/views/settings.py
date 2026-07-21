from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Static

from src.utils.config import config
from src.utils.logger import Logger

SCRIPTS_DESC_INSTRUCTIONS = """To add descriptions for your scripts, generate the descriptions file then edit it (located on your scripts folder)."""

class Settings(Static):
    """Settings view for the Toolbox TUI allowing customization and folder configurations."""
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger

    def compose(self) -> ComposeResult:
        """Create the layout for the settings view."""
        with VerticalScroll():
            yield Label("Settings", id="settings-title")
            yield Label("Configure your theme, paths, and services.", id="settings-subtitle")
            with Horizontal():
                with Vertical():
                    with VerticalScroll(id="paths-settings"):
                        yield Label("Directories", id="settings-directories-title")
                        yield Label("Scripts Directory")
                        yield Label("Path to the folder containing your scripts.", classes="settings-general-label-italic")
                        yield Input(placeholder="/example/scripts", disabled=True, id="settings-directories-input")
                        yield Static(SCRIPTS_DESC_INSTRUCTIONS, classes="settings-general-label-italic")
                        with Horizontal(id="settings-directories-buttons"):
                            yield Button(label="Change Path", id="settings-directories-change-button")
                            yield Button(label="Generate Descriptions File")
                    with Horizontal(id="theme-settings"):
                        yield Label("Application Theme:", id="settings-theme-title")
                with Vertical():
                    yield Container(id="health-checkers-settings")
    
    def on_mount(self) -> None:
        self.query_one("#settings-directories-input", Input).value = str(config.scripts_dir.absolute())