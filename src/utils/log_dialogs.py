from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static, TextArea

from src.utils.log_files import iter_log_files, read_log_text
from src.utils.logger import Logger


class LogFilesDialog(ModalScreen[Path | None]):
    """Show the supported log files in a configured folder."""

    def __init__(self, name: str, directory: Path, logger: Logger) -> None:
        super().__init__()
        self.log_name = name
        self.directory = directory
        self.logger = logger
        self.files: list[Path] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="log-files-dialog"):
            yield Label(f"Log files — {self.log_name}", id="log-files-title")
            yield Static(str(self.directory), id="log-files-location")
            yield ListView(id="log-files-list")
            yield Static("", id="log-files-status")
            with Horizontal(id="log-files-buttons"):
                yield Button("Open", variant="primary", id="log-files-open")
                yield Button("Close", id="log-files-close")

    async def on_mount(self) -> None:
        try:
            self.files = iter_log_files(self.directory)
        except OSError as error:
            self.logger.error(f"Could not read log folder {self.directory}: {error}")
            self.query_one("#log-files-status", Static).update(
                f"Could not read this folder: {error}"
            )
            self.query_one("#log-files-open", Button).disabled = True
            return

        file_list = self.query_one("#log-files-list", ListView)
        if self.files:
            await file_list.mount(
                *(ListItem(Label(path.name)) for path in self.files)
            )
            file_list.index = 0
        else:
            self.query_one("#log-files-status", Static).update(
                "No supported log files were found in this folder."
            )
            self.query_one("#log-files-open", Button).disabled = True

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "log-files-list" and event.index is not None:
            self.open_selected_file(event.index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-files-open":
            file_list = self.query_one("#log-files-list", ListView)
            if file_list.index is not None:
                self.open_selected_file(file_list.index)
        elif event.button.id == "log-files-close":
            self.dismiss(None)

    def open_selected_file(self, index: int) -> None:
        if 0 <= index < len(self.files):
            self.dismiss(self.files[index])


class LogFileDialog(ModalScreen[None]):
    """Display a log file with the newest lines initially in view."""

    def __init__(self, path: Path, logger: Logger) -> None:
        super().__init__()
        self.path = path
        self.logger = logger

    def compose(self) -> ComposeResult:
        with Vertical(id="log-file-dialog"):
            yield Label(self.path.name, id="log-file-title")
            yield Static(str(self.path), id="log-file-location")
            yield TextArea("", id="log-file-content", read_only=True, show_line_numbers=True)
            with Horizontal(id="log-file-buttons"):
                yield Button("Close", id="log-file-close")

    def on_mount(self) -> None:
        viewer = self.query_one("#log-file-content", TextArea)
        try:
            content = read_log_text(self.path)
        except (OSError, ValueError) as error:
            self.logger.error(f"Could not open log file {self.path}: {error}")
            viewer.load_text(f"Could not open this log file:\n\n{error}")
            return

        viewer.load_text(content)
        lines = content.splitlines()
        last_line = max(0, len(lines) - 1)
        last_column = len(lines[last_line]) if lines else 0
        viewer.cursor_location = (last_line, last_column)
        viewer.scroll_cursor_visible(animate=False)
        self.logger.info(f"Opened log file: {self.path}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-file-close":
            self.dismiss(None)
