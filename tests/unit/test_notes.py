from pathlib import Path
from unittest.mock import MagicMock

from src.views.notes import Notes


def make_notes(viewer: MagicMock) -> Notes:
    notes = Notes(logger=MagicMock())
    notes.query_one = MagicMock(return_value=viewer)
    return notes


def test_save_writes_current_file_without_reloading_editor(tmp_path: Path) -> None:
    current_file = tmp_path / "opened.md"
    current_file.write_text("original", encoding="utf-8")
    viewer = MagicMock()
    viewer.text = "edited content"
    viewer.cursor_location = (12, 4)
    viewer.scroll_offset = (0, 12)
    notes = make_notes(viewer)
    notes.current_file_path = current_file
    notes.get_selected_path = MagicMock(side_effect=AssertionError("tree selection should not be used"))

    notes.action_save_file()

    assert current_file.read_text(encoding="utf-8") == "edited content"
    assert viewer.cursor_location == (12, 4)
    assert viewer.scroll_offset == (0, 12)
    viewer.load_text.assert_not_called()


def test_save_failure_keeps_editor_content(tmp_path: Path, monkeypatch) -> None:
    current_file = tmp_path / "opened.md"
    viewer = MagicMock()
    viewer.text = "unsaved edits"
    notes = make_notes(viewer)
    notes.current_file_path = current_file

    def fail_write(_path: Path, _data: bytes) -> int:
        raise OSError("disk is read-only")

    monkeypatch.setattr(Path, "write_bytes", fail_write)

    notes.action_save_file()

    assert viewer.text == "unsaved edits"
    viewer.load_text.assert_not_called()
    notes.logger.error.assert_called_once()


def test_save_without_loaded_file_does_not_use_tree_selection() -> None:
    viewer = MagicMock()
    viewer.text = "error message"
    notes = make_notes(viewer)
    notes.get_selected_path = MagicMock(
        side_effect=AssertionError("tree selection should not be used")
    )

    notes.action_save_file()

    notes.get_selected_path.assert_not_called()
    notes.logger.warn.assert_called_once_with("Open a file before saving.")
