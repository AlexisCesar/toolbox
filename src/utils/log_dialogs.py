import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static, TextArea

from src.utils.log_files import (
    DEFAULT_TAIL_BYTES,
    LOG_FILE_EXTENSIONS,
    is_supported_log_file,
    iter_log_entries,
    read_log_tail,
)
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
            yield Static("Loading folder contents…", id="log-files-status")
            with Horizontal(id="log-files-buttons"):
                yield Button("Open", variant="success", id="log-files-open")
                yield Button("Close", variant="primary", id="log-files-close")

    def on_mount(self) -> None:
        self.query_one("#log-files-open", Button).disabled = True
        self.run_worker(self.load_files(), name="load-log-folder", exclusive=True)

    async def load_files(self) -> None:
        try:
            self.files = await asyncio.to_thread(iter_log_entries, self.directory)
        except OSError as error:
            self.logger.error(f"Could not read log folder {self.directory}: {error}")
            self.query_one("#log-files-status", Static).update(
                f"Could not read this folder: {error}"
            )
            return

        file_list = self.query_one("#log-files-list", ListView)
        if self.files:
            await file_list.mount(
                *(ListItem(Label(path.name)) for path in self.files)
            )
            file_list.index = 0
            self.query_one("#log-files-status", Static).update(
                f"{len(self.files)} items. Select an entry and choose Open."
            )
            self.query_one("#log-files-open", Button).disabled = False
        else:
            self.query_one("#log-files-status", Static).update(
                "This folder is empty."
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-files-open":
            file_list = self.query_one("#log-files-list", ListView)
            if file_list.index is not None:
                self.query_one("#log-files-open", Button).disabled = True
                self.run_worker(
                    self.open_selected_file(file_list.index),
                    name="validate-log-file",
                    exclusive=True,
                )
        elif event.button.id == "log-files-close":
            self.dismiss(None)

    async def open_selected_file(self, index: int) -> None:
        if not 0 <= index < len(self.files):
            return

        path = self.files[index]
        self.query_one("#log-files-status", Static).update("Checking selected item…")
        if path.suffix.lower() not in LOG_FILE_EXTENSIONS:
            supported_extensions = ", ".join(sorted(LOG_FILE_EXTENSIONS))
            self.logger.warn(f"Unsupported log file type selected: {path}")
            self.query_one("#log-files-status", Static).update(
                f"Unsupported file type. Supported types: {supported_extensions}."
            )
            self.query_one("#log-files-open", Button).disabled = False
            return

        try:
            is_log_file = await asyncio.to_thread(is_supported_log_file, path)
        except OSError as error:
            self.logger.error(f"Could not access selected log file {path}: {error}")
            self.query_one("#log-files-status", Static).update(
                f"Could not access this item: {error}"
            )
            self.query_one("#log-files-open", Button).disabled = False
            return

        if not is_log_file:
            self.logger.warn(f"Selected log entry is not a regular file: {path}")
            self.query_one("#log-files-status", Static).update(
                "This item is not a regular file."
            )
            self.query_one("#log-files-open", Button).disabled = False
            return

        self.dismiss(path)


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
                yield Button("Close", variant="primary", id="log-file-close")

    def on_mount(self) -> None:
        self.query_one("#log-file-content", TextArea).load_text(
            "Loading the latest log entries…"
        )
        self.run_worker(self.load_log(), name="load-log-file", exclusive=True)

    async def load_log(self) -> None:
        viewer = self.query_one("#log-file-content", TextArea)
        try:
            content = await asyncio.to_thread(read_log_tail, self.path)
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
        self.logger.info(
            f"Opened log file: {self.path} (read up to {DEFAULT_TAIL_BYTES:,} trailing bytes)"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-file-close":
            self.dismiss(None)
