"""Modal dialog for creating a note file."""

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from src.utils.logger import Logger

DEFAULT_NOTE_EXTENSION = "txt"


@dataclass(frozen=True)
class NewNoteDraft:
    name: str
    extension: str


class NewNoteDialog(ModalScreen[NewNoteDraft | None]):
    """Collect a file name and extension for a new note."""

    def __init__(self, logger: Logger, supported_extensions: set[str]) -> None:
        super().__init__()
        self.logger = logger
        self.supported_extensions = {
            extension.lower() for extension in supported_extensions
        }

    def compose(self) -> ComposeResult:
        with Vertical(id="new-note-dialog"):
            yield Static("New Note", id="new-note-title")
            yield Static(
                "File name (without extension)", classes="new-note-label"
            )
            yield Input(placeholder="meeting-notes", id="new-note-name")
            yield Static("Extension", classes="new-note-label")
            yield Input(
                value=DEFAULT_NOTE_EXTENSION,
                placeholder=DEFAULT_NOTE_EXTENSION,
                id="new-note-extension",
            )
            yield Static("", id="new-note-error")
            with Horizontal(id="new-note-buttons"):
                yield Button("Create", variant="success", id="new-note-create")
                yield Button("Cancel", id="new-note-cancel")

    def on_mount(self) -> None:
        self.query_one("#new-note-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new-note-cancel":
            self.dismiss(None)
        elif event.button.id == "new-note-create":
            self.create_note_draft()

    def create_note_draft(self) -> None:
        name = self.query_one("#new-note-name", Input).value.strip()
        extension = self.query_one("#new-note-extension", Input).value.strip()
        if extension.startswith("."):
            extension = extension[1:]

        error = self.query_one("#new-note-error", Static)
        if not name:
            self.logger.warn("A note file name is required.")
            error.update("Enter a file name.")
            return
        if (
            not self._is_valid_file_part(name, allow_dots=True)
            or name.startswith(".")
        ):
            self.logger.warn("The note file name contains invalid characters.")
            error.update("Use a valid file name without path separators.")
            return
        if not extension:
            self.logger.warn("A note file extension is required.")
            error.update("Enter a file extension, such as txt.")
            return
        if not self._is_valid_file_part(extension, allow_dots=False):
            self.logger.warn("The note file extension contains invalid characters.")
            error.update("Use a valid extension without path separators.")
            return
        if f".{extension.lower()}" not in self.supported_extensions:
            self.logger.warn(f"The note file extension is not supported: {extension}.")
            error.update("This extension is not supported in Notes.")
            return

        reserved_name = name.split(".", maxsplit=1)[0].upper()
        if reserved_name in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or (
            len(reserved_name) == 4
            and reserved_name[:3] in {"COM", "LPT"}
            and reserved_name[3] in "123456789"
        ):
            self.logger.warn("The note file name is reserved by Windows.")
            error.update("Choose a different file name.")
            return

        self.dismiss(NewNoteDraft(name=name, extension=extension))

    @staticmethod
    def _is_valid_file_part(value: str, *, allow_dots: bool) -> bool:
        invalid_characters = '<>:"/\\|?*'
        if not allow_dots:
            invalid_characters += "."
        return (
            value not in {".", ".."}
            and not value.endswith((" ", "."))
            and not any(
                character in invalid_characters or ord(character) < 32
                for character in value
            )
        )
