from textual.events import Key

from src.utils.vim_motions import VimTextArea


def press(editor: VimTextArea, key: str, character: str | None = None) -> bool:
    event = Key(key, character if character is not None else (key if len(key) == 1 else None))
    return editor.vim_motions.handle_key(event)


def test_normal_mode_supports_cursor_and_word_motions() -> None:
    editor = VimTextArea("alpha beta\ngamma")
    editor.vim_motions.set_enabled(True)

    assert press(editor, "w") is True
    assert editor.cursor_location == (0, 6)
    assert press(editor, "e") is True
    assert editor.cursor_location == (0, 9)
    assert press(editor, "0") is True
    assert editor.cursor_location == (0, 0)
    assert press(editor, "g") is True
    assert press(editor, "g") is True
    assert editor.cursor_location == (0, 0)
    assert press(editor, "G") is True
    assert editor.cursor_location == (1, 4)
    assert press(editor, "b") is True
    assert editor.cursor_location == (1, 0)


def test_single_character_and_vertical_motions() -> None:
    editor = VimTextArea("abc def\nghi")
    editor.vim_motions.set_enabled(True)
    editor.cursor_location = (0, 1)

    press(editor, "h")
    assert editor.cursor_location == (0, 0)
    press(editor, "l")
    assert editor.cursor_location == (0, 1)
    press(editor, "j")
    assert editor.cursor_location == (1, 1)
    press(editor, "k")
    assert editor.cursor_location == (0, 1)
    press(editor, "$")
    assert editor.cursor_location == (0, 6)


def test_delete_inner_word_and_undo() -> None:
    editor = VimTextArea("one two")
    editor.vim_motions.set_enabled(True)
    editor.cursor_location = (0, 1)

    press(editor, "d")
    press(editor, "i")
    press(editor, "w")

    assert editor.text == " two"
    press(editor, "u")
    assert editor.text == "one two"


def test_change_word_enters_insert_mode_without_deleting_following_spaces() -> None:
    editor = VimTextArea("one two")
    editor.vim_motions.set_enabled(True)

    press(editor, "c")
    press(editor, "w")

    assert editor.text == " two"
    assert editor.vim_motions.mode == "INSERT"


def test_change_inner_word_enters_insert_mode() -> None:
    editor = VimTextArea("one two")
    editor.vim_motions.set_enabled(True)
    editor.cursor_location = (0, 1)

    for key in ("c", "i", "w"):
        press(editor, key)

    assert editor.text == " two"
    assert editor.vim_motions.mode == "INSERT"


def test_delete_word_to_line_end_and_delete_line() -> None:
    editor = VimTextArea("one two\nthree")
    editor.vim_motions.set_enabled(True)

    press(editor, "d")
    press(editor, "w")
    assert editor.text == "two\nthree"
    press(editor, "u")
    editor.cursor_location = (0, 4)
    press(editor, "d")
    press(editor, "$")
    assert editor.text == "one \nthree"
    press(editor, "u")
    editor.cursor_location = (1, 0)
    press(editor, "d")
    press(editor, "d")
    assert editor.text == "one two"


def test_character_delete_replace_and_paste() -> None:
    editor = VimTextArea("abc")
    editor.vim_motions.set_enabled(True)

    press(editor, "x")
    assert editor.text == "bc"
    press(editor, "p")
    assert editor.text == "bac"
    press(editor, "l")
    press(editor, "r")
    press(editor, "X")
    assert editor.text == "baX"


def test_gg_uppercase_v_and_g_select_the_whole_document() -> None:
    editor = VimTextArea("one\ntwo")
    editor.vim_motions.set_enabled(True)

    for key in ("g", "g", "V", "G"):
        press(editor, key)

    assert editor.selected_text == "one\ntwo"


def test_yank_line_and_paste_below_current_line() -> None:
    editor = VimTextArea("one\ntwo")
    editor.vim_motions.set_enabled(True)

    press(editor, "y")
    press(editor, "y")
    press(editor, "p")

    assert editor.text == "one\none\ntwo"
    assert editor.cursor_location == (1, 0)


def test_insert_commands_and_mode_callback() -> None:
    reported_modes: list[str] = []
    editor = VimTextArea("one\ntwo", on_mode_changed=reported_modes.append)
    editor.vim_motions.set_enabled(True)

    assert editor.show_cursor is True
    assert editor.cursor_blink is False
    assert reported_modes == ["NORMAL"]
    press(editor, "o")

    assert editor.vim_motions.mode == "INSERT"
    assert editor.text == "one\n\ntwo"
    assert editor.cursor_location == (1, 0)
    press(editor, "escape")
    assert editor.vim_motions.mode == "NORMAL"
    editor.vim_motions.set_enabled(False)
    assert editor.vim_motions.mode == ""
    assert reported_modes[-1] == ""
    assert press(editor, "x") is False
    assert editor.cursor_blink is True


def test_append_and_open_line_above() -> None:
    editor = VimTextArea("one\ntwo")
    editor.vim_motions.set_enabled(True)

    press(editor, "a")
    assert editor.cursor_location == (0, 1)
    press(editor, "escape")
    assert editor.cursor_location == (0, 0)

    press(editor, "O")
    assert editor.text == "\none\ntwo"
    assert editor.cursor_location == (0, 0)
    assert editor.vim_motions.mode == "INSERT"


def test_capital_a_enters_insert_at_line_end() -> None:
    editor = VimTextArea("first line\nsecond")
    editor.vim_motions.set_enabled(True)
    editor.cursor_location = (0, 2)

    press(editor, "A")

    assert editor.cursor_location == (0, len("first line"))
    assert editor.vim_motions.mode == "INSERT"


def test_v_starts_characterwise_selection() -> None:
    editor = VimTextArea("one two")
    editor.vim_motions.set_enabled(True)

    press(editor, "v")
    press(editor, "l")

    assert editor.vim_motions.mode == "VISUAL"
    assert editor.selected_text == "o"


def test_command_line_reports_input_and_submits_commands() -> None:
    prompts: list[str] = []
    submitted: list[str] = []
    editor = VimTextArea(
        "one\ntwo",
        on_command_changed=prompts.append,
        on_command_submitted=submitted.append,
    )
    editor.vim_motions.set_enabled(True)

    for key in (":", "w", "enter"):
        press(editor, key)

    assert prompts == ["", ":", ":w", ""]
    assert submitted == ["w"]


def test_set_rnu_enables_relative_line_numbers() -> None:
    editor = VimTextArea("one\ntwo")
    editor.vim_motions.set_enabled(True)

    for key in (":", "s", "e", "t", " ", "r", "n", "u", "enter"):
        press(editor, key)

    assert editor.relative_numbers is True
