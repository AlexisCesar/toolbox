import pytest
from textual import events

from src.utils.bash_terminal import BashTerminal, character_style, key_sequence


@pytest.mark.parametrize(
    ("key", "character", "expected"),
    [
        ("q", "q", "q"), ("enter", None, "\r"), ("tab", None, "\t"),
        ("up", None, "\x1b[A"), ("backspace", None, "\x7f"),
        ("ctrl+c", None, "\x03"), ("ctrl+d", None, "\x04"),
        ("ctrl+l", None, "\x0c"), ("alt+b", None, "\x1bb"),
        ("ctrl+space", None, "\x00"), ("unknown", None, ""),
        ("é", "é", "é"),
    ],
)
def test_keys_are_sent_as_terminal_sequences(key, character, expected) -> None:
    assert key_sequence(key, character) == expected


def test_terminal_applies_ansi_colors_cursor_movement_and_unicode() -> None:
    terminal = BashTerminal()
    terminal.feed("\x1b[31mOlá\x1b[0m\r\nsecond line\rREPLACED")
    screen = terminal.terminal_screen
    assert screen.display[0].rstrip() == "Olá"
    assert screen.buffer[0][0].fg == "red"
    assert screen.display[1].startswith("REPLACEDine")
    terminal.feed("\x1b[2J\x1b[Hclear")
    assert screen.display[0].rstrip() == "clear"
    assert not screen.display[1].strip()


def test_terminal_replies_to_cursor_position_queries(monkeypatch) -> None:
    terminal = BashTerminal()
    messages = []
    monkeypatch.setattr(terminal, "post_message", messages.append)
    terminal.feed("abc\x1b[6n")
    assert messages[0].text == "\x1b[1;4R"


@pytest.mark.parametrize("code", [*range(30, 38), *range(90, 98), "38;2;255;128;0"])
def test_all_ansi_foreground_colors_render(code) -> None:
    terminal = BashTerminal()
    terminal.feed(f"\x1b[{code}mX")
    assert character_style(terminal.terminal_screen.buffer[0][0]).color is not None


def test_paste_uses_bracketed_paste_when_requested(monkeypatch) -> None:
    terminal = BashTerminal()
    terminal.feed("\x1b[?2004h")
    messages = []
    monkeypatch.setattr(terminal, "post_message", messages.append)
    terminal.on_paste(events.Paste("echo one\r\necho two"))
    assert messages[0].text == "\x1b[200~echo one\recho two\x1b[201~"


def test_history_can_be_scrolled_and_resets_for_new_session() -> None:
    terminal = BashTerminal()
    terminal.feed("\r\n".join(f"line {number}" for number in range(60)))
    screen = terminal.terminal_screen
    latest = list(screen.display)
    terminal._scroll_history(True)
    assert screen.display != latest
    terminal._scroll_history(False)
    assert screen.display == latest
    terminal.reset_terminal()
    assert not screen.history.top
    assert all(not line.strip() for line in screen.display)


def test_new_session_does_not_keep_a_partial_escape_sequence() -> None:
    terminal = BashTerminal()
    terminal.feed("\x1b[")
    terminal.reset_terminal()
    terminal.feed("hello")
    assert terminal.terminal_screen.display[0].rstrip() == "hello"


def test_history_can_be_scrolled_after_shrinking_terminal_width() -> None:
    terminal = BashTerminal()
    terminal.feed(("x" * 80 + "\r\n") * 60)
    terminal.terminal_screen.resize(columns=50)
    terminal._scroll_history(True)
    terminal._scroll_history(False)
    assert all(len(line) == 50 for line in terminal.terminal_screen.display)
