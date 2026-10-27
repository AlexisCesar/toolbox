from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from src.utils.config import normalize_directory_path
from src.utils.logger import Logger


@dataclass
class LogFolder:
    name: str
    location: str


class LogConfigDialog(ModalScreen[LogFolder | None]):
    """Collect and validate a log folder name and location."""

    def __init__(self, logger: Logger, initial: LogFolder | None = None) -> None:
        super().__init__()
        self.logger = logger
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="log-config-dialog"):
            yield Static(
                "Edit log folder" if self.initial else "Add log folder",
                id="log-config-title",
            )
            yield Static("Name", classes="log-config-label")
            yield Input(
                value=self.initial.name if self.initial else "",
                placeholder="Application X v2",
                id="log-config-name",
            )
            yield Static("Folder path (local or network share)", classes="log-config-label")
            yield Input(
                value=self.initial.location if self.initial else "",
                placeholder=r"C:\dev\my_projects\application_x_v2\logs\ or \\server\share\logs",
                id="log-config-location",
            )
            yield Static("", id="log-config-error")
            with Horizontal(id="log-config-buttons"):
                yield Button("Save", variant="success", id="log-config-save")
                yield Button("Cancel", id="log-config-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-config-cancel":
            self.dismiss(None)
        elif event.button.id == "log-config-save":
            self.save_log_folder()

    def save_log_folder(self) -> None:
        name = self.query_one("#log-config-name", Input).value.strip()
        location = normalize_directory_path(
            self.query_one("#log-config-location", Input).value.strip()
        )
        error_message = self.query_one("#log-config-error", Static)

        if not name:
            self.logger.warn("A log folder name is required.")
            error_message.update("Enter a name for this log folder.")
            return
        if not location:
            self.logger.warn("A path is required for the log folder.")
            error_message.update("Enter the path to a log folder.")
            return

        folder_path = Path(location).expanduser()
        if not folder_path.is_dir():
            self.logger.warn(f"The selected log folder is unavailable: {location}")
            error_message.update("This folder is unavailable or is not a directory.")
            return

        self.dismiss(LogFolder(name=name, location=location))
