import asyncio
from pathlib import Path

from textual.widgets import Checkbox, Static

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.script_editor_dialog import ScriptEditorDialog
from src.utils.vim_motions import VimTextArea
from src.views.bash import Bash
from src.views.notes import Notes


def test_script_and_notes_editors_can_toggle_vim_motions(
    tmp_path: Path, monkeypatch
) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    monkeypatch.setitem(config._data["paths"], "notes", str(notes_dir))
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    monkeypatch.setattr("src.tui.check_for_update", lambda _version: None)
    app = ToolboxTUI()

    async def check_editors() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(ScriptEditorDialog(tmp_path / "sample.py", "alpha beta"))
            await pilot.pause()
            script_dialog = app.screen
            script_editor = script_dialog.query_one(
                "#script-editor-content", VimTextArea
            )
            script_mode = script_dialog.query_one(
                "#script-editor-vim-mode", Static
            )
            assert script_dialog.query_one(
                "#script-editor-vim-toggle", Checkbox
            ).value is False
            assert script_mode.display is False

            await pilot.click("#script-editor-vim-toggle")
            await pilot.pause()
            assert str(script_mode.content) == "NORMAL"
            await pilot.press("w")
            assert script_editor.cursor_location == (0, 6)
            await pilot.press("v", "l")
            assert script_editor.selected_text == "b"
            await pilot.press("escape")
            script_editor.move_cursor((0, 6))
            await pilot.press("i")
            assert str(script_mode.content) == "INSERT"
            assert script_editor.cursor_blink is False
            assert script_editor._draw_cursor is False
            await pilot.press("X")
            await pilot.press("escape")
            assert script_editor.text == "alpha Xbeta"
            assert script_editor.cursor_location == (0, 6)
            assert str(script_mode.content) == "NORMAL"
            await pilot.click("#script-editor-vim-toggle")
            await pilot.pause()
            assert script_dialog.query_one(
                "#script-editor-vim-toggle", Checkbox
            ).value is False
            assert script_mode.display is False
            await pilot.click("#script-editor-cancel")
            await pilot.pause()

            saved_script = tmp_path / "saved.py"
            app.push_screen(ScriptEditorDialog(saved_script, "clean"))
            await pilot.pause()
            await pilot.click("#script-editor-vim-toggle")
            await pilot.pause()
            await pilot.press(":", "w", "enter")
            await pilot.pause()
            assert saved_script.read_text(encoding="utf-8") == "clean"
            assert app.screen.query_one("#script-editor-vim-mode", Static).display
            await pilot.press(":", "q", "enter")
            await pilot.pause()

            app.push_screen(ScriptEditorDialog(tmp_path / "discard.py", "clean"))
            await pilot.pause()
            await pilot.click("#script-editor-vim-toggle")
            await pilot.pause()
            await pilot.press("i", "!", "escape")
            await pilot.press(":", "q", "enter")
            await pilot.pause()
            assert "E37" in str(
                app.screen.query_one("#script-editor-status", Static).content
            )
            await pilot.press(":", "q", "!", "enter")
            await pilot.pause()

            app.action_select_view(7)
            await pilot.pause()
            notes_editor = app.query_one("#viewer", VimTextArea)
            note_path = notes_dir / "command.md"
            note_path.write_text("alpha beta", encoding="utf-8")
            notes_view = app.query_one(Notes)
            notes_view.display_file(note_path)
            notes_editor.move_cursor((0, 0))
            notes_mode = app.query_one("#notes-vim-mode", Static)
            assert app.query_one("#notes-vim-toggle", Checkbox).value is False

            await pilot.click("#notes-vim-toggle")
            await pilot.pause()
            assert str(notes_mode.content) == "NORMAL"
            await pilot.press("w")
            assert notes_editor.cursor_location == (0, 6)
            await pilot.press("i")
            await pilot.press("X")
            await pilot.press("escape")
            assert notes_editor.text == "alpha Xbeta"
            assert str(notes_mode.content) == "NORMAL"
            await pilot.press(":", "s", "e", "t", " ", "r", "n", "u", "enter")
            assert notes_editor.relative_numbers is True
            await pilot.press(":", "w", "q", "enter")
            await pilot.pause()
            assert note_path.read_text(encoding="utf-8") == "alpha Xbeta"
            assert notes_view.current_file_path is None
            assert notes_editor.text == ""

    asyncio.run(check_editors())
