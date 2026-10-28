from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.utils.confirm_dialog import ConfirmResult
from src.views.notes import Notes
from textual.app import App
from textual._context import active_app


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
    notes._parent = app
    return notes


def test_selecting_another_file_prompts_when_current_file_is_dirty(
    tmp_path: Path,
) -> None:
    current_path = tmp_path / "current.md"
    next_path = tmp_path / "next.md"
    viewer = MagicMock()
    viewer.text = "edited"
    tree = MagicMock()
    current_node = SimpleNamespace(
        data=SimpleNamespace(path=current_path), children=[]
    )
    tree.root = SimpleNamespace(data=None, children=[current_node])
    notes = make_notes(viewer, tree)
    notes.current_file_path = current_path
    notes.saved_content = "original"
    event = SimpleNamespace(path=next_path)

    app_token = active_app.set(notes._parent)
    try:
        notes.on_directory_tree_file_selected(event)
    finally:
        active_app.reset(app_token)

    notes.app.push_screen.assert_called_once()
    dialog = notes.app.push_screen.call_args.args[0]
    assert dialog.message == "Discard unsaved changes to current.md?"
    assert dialog.confirmButtonText == "Discard"
    assert dialog.cancelButtonText == "Keep Editing"
    notes.app.push_screen.call_args.kwargs["callback"](
        ConfirmResult(confirmed=False, parameters="")
    )
    tree.move_cursor.assert_called_once_with(current_node)


def test_confirmed_file_selection_opens_new_file(tmp_path: Path) -> None:
    viewer = MagicMock()
    viewer.text = "edited"
    notes = make_notes(viewer)
    notes.current_file_path = tmp_path / "current.md"
    notes.saved_content = "original"
    selected_path = tmp_path / "next.md"
    notes.display_file = MagicMock()

    notes.confirm_file_selection(
        ConfirmResult(confirmed=True, parameters=""), selected_path
    )

    notes.display_file.assert_called_once_with(selected_path)


def test_selecting_same_file_does_not_reload_dirty_content(tmp_path: Path) -> None:
    viewer = MagicMock()
    viewer.text = "edited"
    notes = make_notes(viewer)
    current_path = tmp_path / "current.md"
    notes.current_file_path = current_path
    notes.saved_content = "original"
    notes.display_file = MagicMock()

    notes.on_directory_tree_file_selected(SimpleNamespace(path=current_path))

    notes.display_file.assert_not_called()
