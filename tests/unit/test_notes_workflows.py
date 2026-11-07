from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.utils.new_note_dialog import NewNoteDialog, NewNoteDraft
from src.views import notes as notes_module
from src.views.notes import Notes, NotesDirectoryTree
from textual.app import App
from textual.widgets import TextArea


def make_notes(viewer: MagicMock, tree: MagicMock | None = None) -> Notes:
    notes = Notes(logger=MagicMock())
    tree = tree or MagicMock()
    notes.query_one = MagicMock(
        side_effect=lambda selector, *_args: (
            viewer if selector == "#viewer" else tree
        )
    )
    app = App()
    app.push_screen = MagicMock()
    app.notify = MagicMock()
    notes._parent = app
    notes.test_app = app
    return notes


def test_directory_tree_lists_supported_files_and_directories(tmp_path: Path) -> None:
    visible_directory = tmp_path / "folder"
    visible_directory.mkdir()
    visible_files = [tmp_path / "note.MD", tmp_path / "script.py", tmp_path / "data.csv"]
    hidden_file = tmp_path / ".private.md"
    unsupported_file = tmp_path / "image.png"
    for path in [*visible_files, hidden_file, unsupported_file]:
        path.write_text("content", encoding="utf-8")

    filtered_paths = NotesDirectoryTree.filter_paths(
        MagicMock(), [*visible_files, visible_directory, hidden_file, unsupported_file]
    )

    assert set(filtered_paths) == {
        *visible_files,
        visible_directory,
    }


def test_get_selected_path_returns_file_and_rejects_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "note.md"
    file_path.write_text("note", encoding="utf-8")
    tree = MagicMock()
    tree.cursor_node.data.path = file_path
    notes = make_notes(MagicMock(), tree)

    assert notes.get_selected_path() == file_path

    tree.cursor_node.data.path = tmp_path
    assert notes.get_selected_path() is None
    notes.logger.warn.assert_called_once_with("Select a file, not a folder.")


def test_load_selected_file_displays_selected_file_and_tracks_baseline(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "note.md"
    file_path.write_text("# Example\nText", encoding="utf-8")
    viewer = MagicMock(spec=TextArea)
    tree = MagicMock()
    tree.cursor_node.data.path = file_path
    notes = make_notes(viewer, tree)

    notes.load_selected_file()

    expected_content = Notes.read_text_file(file_path)
    viewer.load_text.assert_called_once_with(expected_content)
    assert notes.current_file_path == file_path
    assert notes.saved_content == expected_content
    assert viewer.language is None
    assert viewer.cursor_location == (0, 0)
    viewer.scroll_cursor_visible.assert_called_once_with(animate=False)


def test_load_selected_file_warns_when_nothing_is_selected() -> None:
    tree = MagicMock()
    tree.cursor_node = None
    notes = make_notes(MagicMock(), tree)

    notes.load_selected_file()

    notes.logger.warn.assert_called_once_with("Select a file to open.")


def test_display_file_reports_read_error_and_clears_open_file_state(
    tmp_path: Path,
) -> None:
    viewer = MagicMock(spec=TextArea)
    notes = make_notes(viewer)
    notes.current_file_path = tmp_path / "previous.md"
    notes.saved_content = "previous"
    missing_path = tmp_path / "missing.md"

    notes.display_file(missing_path)

    assert notes.current_file_path is None
    assert notes.saved_content is None
    viewer.load_text.assert_called_once()
    assert "Could not open the file:" in viewer.load_text.call_args.args[0]


def test_selecting_clean_file_opens_it_without_confirmation(tmp_path: Path) -> None:
    viewer = MagicMock(spec=TextArea)
    viewer.text = "saved"
    notes = make_notes(viewer)
    current_path = tmp_path / "current.md"
    current_path.write_text("saved", encoding="utf-8")
    next_path = tmp_path / "next.md"
    next_path.write_text("next note", encoding="utf-8")
    notes.current_file_path = current_path
    notes.saved_content = "saved"

    notes.on_directory_tree_file_selected(SimpleNamespace(path=next_path))

    viewer.load_text.assert_called_once_with("next note")
    assert notes.current_file_path == next_path
    assert notes.saved_content == "next note"
    notes.test_app.push_screen.assert_not_called()


def test_refresh_folder_uses_configured_notes_directory(monkeypatch) -> None:
    tree = MagicMock()
    notes = make_notes(MagicMock(), tree)
    configured_path = Path("notes-root")
    monkeypatch.setattr(
        notes_module, "config", SimpleNamespace(notes_dir=configured_path)
    )

    notes.action_refresh_folder()

    assert tree.path == configured_path
    tree.reload.assert_called_once_with()
    notes.logger.info.assert_called_once_with("Refreshing notes directory tree...")


def test_new_note_creates_and_opens_empty_file_in_selected_folder(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tree = MagicMock()
    tree.cursor_node.data.path = tmp_path
    viewer = MagicMock(spec=TextArea)
    notes = make_notes(viewer, tree)
    monkeypatch.setattr(
        notes_module, "config", SimpleNamespace(notes_dir=tmp_path)
    )

    notes.action_new_note()

    dialog = notes.test_app.push_screen.call_args.args[0]
    assert isinstance(dialog, NewNoteDialog)
    notes.test_app.push_screen.call_args.kwargs["callback"](
        NewNoteDraft("meeting-notes", "txt")
    )

    created_file = tmp_path / "meeting-notes.txt"
    assert created_file.exists()
    assert created_file.read_text(encoding="utf-8") == ""
    assert notes.current_file_path == created_file
    viewer.load_text.assert_called_once_with("")
    tree.reload.assert_called_once_with()


def test_new_note_requires_a_selected_folder() -> None:
    tree = MagicMock()
    tree.cursor_node = None
    notes = make_notes(MagicMock(), tree)

    notes.action_new_note()

    notes.test_app.push_screen.assert_not_called()
    notes.logger.warn.assert_called_once_with("Select a folder to create a note.")


def test_new_note_does_not_overwrite_an_existing_file(tmp_path: Path) -> None:
    existing_file = tmp_path / "meeting-notes.txt"
    existing_file.write_text("keep this", encoding="utf-8")
    notes = make_notes(MagicMock())

    notes.create_note(tmp_path, NewNoteDraft("meeting-notes", "txt"))

    assert existing_file.read_text(encoding="utf-8") == "keep this"
    notes.logger.warn.assert_called_once_with(
        f"A notes file already exists at {existing_file}."
    )
    notes.test_app.notify.assert_called_once_with(
        "A file named 'meeting-notes.txt' already exists.",
        title="New Note",
        severity="warning",
    )
