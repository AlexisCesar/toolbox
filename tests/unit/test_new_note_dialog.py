from types import SimpleNamespace
from unittest.mock import MagicMock

from src.utils.new_note_dialog import (
    DEFAULT_NOTE_EXTENSION,
    NewNoteDialog,
    NewNoteDraft,
)


def make_dialog(name: str, extension: str) -> NewNoteDialog:
    dialog = NewNoteDialog(MagicMock(), supported_extensions={".txt", ".md"})
    widgets = {
        "#new-note-name": SimpleNamespace(value=name),
        "#new-note-extension": SimpleNamespace(value=extension),
        "#new-note-error": MagicMock(),
    }
    dialog.query_one = MagicMock(
        side_effect=lambda selector, *_args: widgets[selector]
    )
    dialog.dismiss = MagicMock()
    return dialog


def test_new_note_dialog_returns_normalized_draft() -> None:
    dialog = make_dialog("  meeting notes  ", ".MD")

    dialog.create_note_draft()

    dialog.dismiss.assert_called_once_with(NewNoteDraft("meeting notes", "MD"))


def test_new_note_dialog_uses_txt_as_default_extension() -> None:
    assert DEFAULT_NOTE_EXTENSION == "txt"


def test_new_note_dialog_rejects_path_separators() -> None:
    dialog = make_dialog("../outside", "txt")

    dialog.create_note_draft()

    dialog.dismiss.assert_not_called()
    dialog.query_one("#new-note-error").update.assert_called_once_with(
        "Use a valid file name without path separators."
    )


def test_new_note_dialog_rejects_unsupported_extensions() -> None:
    dialog = make_dialog("notes", "png")

    dialog.create_note_draft()

    dialog.dismiss.assert_not_called()
    dialog.query_one("#new-note-error").update.assert_called_once_with(
        "This extension is not supported in Notes."
    )
