"""Textual terminal surface with ANSI rendering and native keyboard events."""

from functools import lru_cache
from string import hexdigits

import pyte
from rich.segment import Segment
from rich.style import Style
from pyte.screens import Char
from textual import events
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget


KEY_SEQUENCES = {
    "enter": "\r", "tab": "\t", "backspace": "\x7f", "escape": "\x1b",
    "up": "\x1b[A", "down": "\x1b[B", "right": "\x1b[C", "left": "\x1b[D",
    "home": "\x1b[H", "end": "\x1b[F", "delete": "\x1b[3~", "insert": "\x1b[2~",
    "pageup": "\x1b[5~", "pagedown": "\x1b[6~", "shift+tab": "\x1b[Z",
    "ctrl+left": "\x1b[1;5D", "ctrl+right": "\x1b[1;5C",
    "f1": "\x1bOP", "f2": "\x1bOQ", "f3": "\x1bOR", "f4": "\x1bOS",
    "f5": "\x1b[15~", "f6": "\x1b[17~", "f7": "\x1b[18~", "f8": "\x1b[19~",
    "f9": "\x1b[20~", "f10": "\x1b[21~", "f11": "\x1b[23~", "f12": "\x1b[24~",
}


def key_sequence(key: str, character: str | None) -> str:
    """Translate Textual keys to terminal input, including readline controls."""
    if key in KEY_SEQUENCES:
        return KEY_SEQUENCES[key]
    if key.startswith("ctrl+") and len(key) == 6:
        letter = key[-1]
        if "a" <= letter <= "z":
            return chr(ord(letter) - ord("a") + 1)
    if key == "ctrl+space":
        return "\x00"
    if key.startswith("alt+") and len(key) == 5:
        return "\x1b" + key[-1]
    return character or ""


@lru_cache(maxsize=2048)
def character_style(character: Char) -> Style:
    def color(value: str) -> str | None:
        if value == "default":
            return None
        if len(value) == 6 and all(digit in hexdigits for digit in value):
            return f"#{value}"
        value = value.replace("brown", "yellow")
        return value.replace("bright", "bright_") if value.startswith("bright") else value

    return Style(
        color=color(character.fg), bgcolor=color(character.bg), bold=character.bold,
        italic=character.italics, underline=character.underscore,
        strike=character.strikethrough, reverse=character.reverse,
    )


class TerminalScreen(pyte.HistoryScreen):
    def after_event(self, event: str) -> None:
        # pyte 0.8.2 mutates row dictionaries while trimming restored history
        # after a resize. Trim using a snapshot before its pagination hook.
        if event in {"prev_page", "next_page"}:
            for line in self.buffer.values():
                for column in tuple(line):
                    if column >= self.columns:
                        del line[column]
        super().after_event(event)


class BashTerminal(Widget, can_focus=True):
    """Render a bounded terminal screen while Bash handles line editing."""

    class Input(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class Resized(Message):
        def __init__(self, rows: int, columns: int) -> None:
            super().__init__()
            self.rows = rows
            self.columns = columns

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.terminal_screen = TerminalScreen(80, 24, history=2000)
        self.terminal_screen.write_process_input = self._send_input
        self.stream = pyte.Stream(self.terminal_screen)

    def _send_input(self, text: str) -> None:
        self.post_message(self.Input(text))

    def reset_terminal(self) -> None:
        self.terminal_screen.reset()
        self.stream = pyte.Stream(self.terminal_screen)
        self.refresh()

    def feed(self, text: str) -> None:
        self.stream.feed(text)
        self.refresh()

    def on_resize(self, event: events.Resize) -> None:
        rows, columns = max(1, self.content_size.height), max(1, self.content_size.width)
        self.terminal_screen.resize(lines=rows, columns=columns)
        self.post_message(self.Resized(rows, columns))

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()

    def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        if event.key == "ctrl+g":
            self.app.query_one("#sidebar-list").focus()
        elif event.key in {"shift+pageup", "shift+pagedown"}:
            self._scroll_history(event.key == "shift+pageup")
        else:
            self.terminal_screen.before_event("input")
            self._send_input(key_sequence(event.key, event.character))

    def on_paste(self, event: events.Paste) -> None:
        event.stop()
        event.prevent_default()
        text = event.text.replace("\r\n", "\n").replace("\n", "\r")
        if 2004 << 5 in self.terminal_screen.mode:
            text = f"\x1b[200~{text}\x1b[201~"
        self._send_input(text)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self._scroll_history(True)

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self._scroll_history(False)

    def _scroll_history(self, up: bool) -> None:
        screen = self.terminal_screen
        (screen.prev_page if up else screen.next_page)()
        self.refresh()

    def render_line(self, y: int) -> Strip:
        screen = self.terminal_screen
        if y >= screen.lines:
            return Strip.blank(self.size.width, self.rich_style)
        segments = []
        cursor = screen.cursor
        for x in range(screen.columns):
            character = screen.buffer[y][x]
            style = self.rich_style + character_style(character)
            if self.has_focus and not cursor.hidden and (x, y) == (cursor.x, cursor.y):
                style += Style(reverse=True)
            segments.append(Segment(character.data, style))
        return Strip(segments, screen.columns).crop_extend(0, self.size.width, self.rich_style)
