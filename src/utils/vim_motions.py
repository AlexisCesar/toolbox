"""Optional Vim-style controls for Textual text areas."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from rich.segment import Segment
from rich.style import Style
from textual.events import Key
from textual.strip import Strip
from textual.widgets import TextArea


TextLocation = tuple[int, int]
ModeChanged = Callable[[str], None]
CommandChanged = Callable[[str], None]
CommandSubmitted = Callable[[str], None]
CommandResult = Callable[[str], None]
WORD_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class VimTextArea(TextArea):
    """TextArea that can delegate key handling to an optional Vim controller."""

    def __init__(
        self,
        text: str = "",
        *,
        on_mode_changed: ModeChanged | None = None,
        on_command_changed: CommandChanged | None = None,
        on_command_submitted: CommandSubmitted | None = None,
        on_command_result: CommandResult | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(text, **kwargs)
        self.relative_numbers = False
        self.vim_motions = VimMotions(
            self,
            on_mode_changed,
            on_command_changed,
            on_command_submitted,
            on_command_result,
        )

    @property
    def _draw_cursor(self) -> bool:
        """Use a thin underline marker in INSERT mode instead of the block cursor."""
        if self.vim_motions.enabled and self.vim_motions.mode == "INSERT":
            return False
        return super()._draw_cursor

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        scroll_x, scroll_y = self.scroll_offset

        if (
            self.relative_numbers
            and self.vim_motions.enabled
            and self.show_line_numbers
        ):
            line_offset = y + scroll_y
            line_map = self.wrapped_document._offset_to_line_info
            if 0 <= line_offset < len(line_map):
                line_info = line_map[line_offset]
                if line_info is not None:
                    line_index, section_offset = line_info
                    cursor_row = self.cursor_location[0]
                    label = (
                        str(abs(line_index - cursor_row))
                        if section_offset == 0
                        else ""
                    )
                    style_name = (
                        "text-area--cursor-gutter"
                        if line_index == cursor_row and self.highlight_cursor_line
                        else "text-area--gutter"
                    )
                    gutter_style = self.get_component_rich_style(style_name)
                    gutter_width = self.gutter_width
                    gutter = Strip(
                        [Segment(f"{label:>{gutter_width - 2}}  ", gutter_style)],
                        cell_length=gutter_width,
                    )
                    strip = Strip.join(
                        [gutter, strip.crop(gutter_width, strip.cell_length)]
                    )

        if (
            self.vim_motions.enabled
            and self.vim_motions.mode == "INSERT"
            and self.has_focus
        ):
            cursor_x, cursor_y = self._cursor_offset
            cursor_x = cursor_x - scroll_x + self.gutter_width
            cursor_y -= scroll_y
            if cursor_y == y and 0 <= cursor_x < strip.cell_length:
                strip = Strip.join(
                    [
                        strip.crop(0, cursor_x),
                        strip.crop(cursor_x, cursor_x + 1).apply_style(
                            Style(underline=True)
                        ),
                        strip.crop(cursor_x + 1, strip.cell_length),
                    ]
                )
        return strip

    def set_relative_numbers(self, enabled: bool) -> None:
        """Show line distances from the cursor in the TextArea gutter."""
        if self.relative_numbers == enabled:
            return
        self.relative_numbers = enabled
        self._line_cache.clear()
        self.refresh()

    async def _on_key(self, event: Key) -> None:
        """Handle Vim keys first, then fall back to Textual's normal editing."""
        if self.vim_motions.handle_key(event):
            event.stop()
            event.prevent_default()
            return
        previous_text = self.text
        await super()._on_key(event)
        if self.text != previous_text:
            self.vim_motions.note_insert_edit()


class VimMotions:
    """Implement a focused set of normal and insert mode editing commands."""

    def __init__(
        self,
        editor: TextArea,
        on_mode_changed: ModeChanged | None = None,
        on_command_changed: CommandChanged | None = None,
        on_command_submitted: CommandSubmitted | None = None,
        on_command_result: CommandResult | None = None,
    ) -> None:
        self.editor = editor
        self.on_mode_changed = on_mode_changed
        self.on_command_changed = on_command_changed
        self.on_command_submitted = on_command_submitted
        self.on_command_result = on_command_result
        self.enabled = False
        self.mode = ""
        self.register = ""
        self._register_is_linewise = False
        self._pending = ""
        self._visual = False
        self.command_mode = False
        self.command_buffer = ""
        self._insert_modified = False
        self._insert_return_location = editor.cursor_location
        self._default_cursor_visibility = editor.show_cursor
        self._default_cursor_blink = editor.cursor_blink

    def set_enabled(self, enabled: bool) -> None:
        """Enable Vim in NORMAL mode, or restore the TextArea's normal behavior."""
        if self.enabled == enabled:
            return
        self.enabled = enabled
        self._pending = ""
        self._visual = False
        self.command_mode = False
        self.command_buffer = ""
        self._update_command_prompt()
        if enabled:
            self.editor.show_cursor = True
            self.editor.cursor_blink = False
            self.editor.move_cursor(self.editor.cursor_location)
            self._set_mode("NORMAL")
        else:
            if isinstance(self.editor, VimTextArea):
                self.editor.set_relative_numbers(False)
            self.editor.show_cursor = self._default_cursor_visibility
            self.editor.cursor_blink = self._default_cursor_blink
            self.editor.move_cursor(self.editor.cursor_location)
            self._set_mode("")

    def handle_key(self, event: Key) -> bool:
        """Handle a key and return whether Textual's default handler should stop."""
        if not self.enabled:
            return False

        if self.command_mode:
            return self._handle_command_key(event)

        if self.mode == "INSERT":
            if event.key == "escape":
                self._pending = ""
                if self._insert_modified:
                    row, column = self.editor.cursor_location
                    if column > 0:
                        location = (row, column - 1)
                    elif row > 0:
                        previous_row = row - 1
                        location = (
                            previous_row,
                            max(len(self._lines()[previous_row]) - 1, 0),
                        )
                    else:
                        location = (row, column)
                else:
                    location = self._insert_return_location
                self._set_mode("NORMAL")
                self._move_cursor(location)
                return True
            return False

        if event.key == "escape":
            self._pending = ""
            self._visual = False
            self._move_cursor(self.editor.cursor_location)
            self._set_mode("NORMAL")
            return True

        if event.key.startswith(("ctrl+", "alt+", "super+")):
            return False
        if not event.is_printable:
            return event.key not in {
                "up",
                "down",
                "left",
                "right",
                "home",
                "end",
                "pageup",
                "pagedown",
            }

        character = event.character
        if character is None:
            return True
        self._handle_normal_character(character)
        return True

    def _handle_normal_character(self, character: str) -> None:
        if self._pending:
            if self._continue_pending(character):
                return
        self._dispatch_normal(character)

    def _continue_pending(self, character: str) -> bool:
        pending = self._pending
        self._pending = ""

        if pending == "g":
            if character == "g":
                self._move_cursor((0, 0))
                return True
        elif pending == "y":
            if character == "y":
                self._yank_line()
                return True
        elif pending == "r":
            self._replace_character(character)
            return True
        elif pending in {"d", "c"}:
            if character == pending:
                if pending == "c":
                    self._change_line()
                else:
                    self._delete_line()
                return True
            if character == "w":
                if pending == "c":
                    self._change_word()
                else:
                    self._delete_word()
                return True
            if character == "$":
                self._delete_to_line_end(change=pending == "c")
                return True
            if character == "i":
                self._pending = pending + "i"
                return True
        elif pending in {"di", "ci"} and character == "w":
            self._delete_inner_word(change=pending == "ci")
            return True

        return False

    def _dispatch_normal(self, character: str) -> None:
        if character == "h":
            self._move_cursor(self.editor.get_cursor_left_location())
        elif character == "j":
            self._move_cursor(self.editor.get_cursor_down_location())
        elif character == "k":
            self._move_cursor(self.editor.get_cursor_up_location())
        elif character == "l":
            row, column = self.editor.cursor_location
            line = self._lines()[row]
            self._move_cursor((row, min(column + 1, max(len(line) - 1, 0))))
        elif character == "w":
            self._move_to_word_start()
        elif character == "b":
            self._move_to_previous_word_start()
        elif character == "e":
            self._move_to_word_end()
        elif character == "0":
            self._move_cursor((self.editor.cursor_location[0], 0))
        elif character == "$":
            row = self.editor.cursor_location[0]
            self._move_cursor((row, max(len(self._lines()[row]) - 1, 0)))
        elif character == "G":
            row = len(self._lines()) - 1
            last_column = len(self._lines()[row])
            if not self._visual:
                last_column = max(last_column - 1, 0)
            self._move_cursor((row, last_column))
        elif character == "g":
            self._pending = "g"
        elif character in {"i", "a", "A", "o", "O"}:
            self._enter_insert_mode(character)
        elif character == "x":
            self._delete_character()
        elif character == "d":
            self._pending = "d"
        elif character == "c":
            self._pending = "c"
        elif character == "y":
            self._pending = "y"
        elif character == "p":
            self._paste_register()
        elif character == "u":
            self.editor.action_undo()
        elif character == "r":
            self._pending = "r"
        elif character == "V":
            self.editor.select_line(self.editor.cursor_location[0])
            self._visual = True
            self._set_mode("VISUAL")
        elif character == "v":
            self.editor.move_cursor(self.editor.cursor_location)
            self._visual = True
            self._set_mode("VISUAL")
        elif character == ":":
            self.command_mode = True
            self.command_buffer = ""
            self._update_command_prompt()

    def _enter_insert_mode(self, command: str) -> None:
        row, column = self.editor.cursor_location
        original_location = (row, column)
        lines = self._lines()
        if command == "a":
            column = min(column + 1, len(lines[row]))
        elif command == "A":
            column = len(lines[row])
        elif command == "o":
            self.editor.insert("\n", (row, len(lines[row])))
            row += 1
            column = 0
        elif command == "O":
            self.editor.insert("\n", (row, 0))
            column = 0
        self._move_cursor((row, column))
        self._set_mode("INSERT")
        if command in {"a", "A"}:
            self._insert_return_location = original_location

    def _delete_character(self) -> None:
        row, column = self.editor.cursor_location
        line = self._lines()[row]
        if column >= len(line):
            return
        self._delete_range((row, column), (row, column + 1))

    def _delete_line(self) -> None:
        lines = self._lines()
        row = self.editor.cursor_location[0]
        self.register = lines[row] + "\n"
        self._register_is_linewise = True

        if len(lines) == 1:
            start, end, cursor = (0, 0), (0, len(lines[0])), (0, 0)
        elif row < len(lines) - 1:
            start, end, cursor = (row, 0), (row + 1, 0), (row, 0)
        else:
            previous_line = lines[row - 1]
            start = (row - 1, len(previous_line))
            end = (row, len(lines[row]))
            cursor = (row - 1, max(len(previous_line) - 1, 0))

        self.editor.replace("", start, end, maintain_selection_offset=False)
        self._move_cursor(cursor)

    def _change_line(self) -> None:
        row = self.editor.cursor_location[0]
        line = self._lines()[row]
        self.register = line
        self._register_is_linewise = True
        self.editor.replace(
            "",
            (row, 0),
            (row, len(line)),
            maintain_selection_offset=False,
        )
        self._move_cursor((row, 0))
        self._set_mode("INSERT")

    def _yank_line(self) -> None:
        row = self.editor.cursor_location[0]
        self.register = self._lines()[row] + "\n"
        self._register_is_linewise = True

    def _delete_word(self) -> None:
        lines = self._lines()
        start = self.editor.cursor_location
        offset = self._location_to_offset(start)
        next_word = next(
            (match.start() for match in self._word_matches() if match.start() > offset),
            None,
        )
        if next_word is None:
            end = (start[0], len(lines[start[0]]))
        else:
            end = self._offset_to_location(next_word)
        if self._location_to_offset(end) <= offset:
            return
        self._delete_range(start, end)

    def _change_word(self) -> None:
        offset = self._location_to_offset(self.editor.cursor_location)
        match = next(
            (item for item in self._word_matches() if item.start() <= offset < item.end()),
            None,
        )
        if match is None:
            match = next(
                (item for item in self._word_matches() if item.start() > offset),
                None,
            )
        if match is None:
            return
        self._delete_range(
            self.editor.cursor_location,
            self._offset_to_location(match.end()),
        )
        self._set_mode("INSERT")

    def _delete_inner_word(self, *, change: bool) -> None:
        bounds = self._word_bounds(self.editor.cursor_location)
        if bounds is None:
            return
        self._delete_range(*bounds)
        if change:
            self._set_mode("INSERT")

    def _delete_to_line_end(self, *, change: bool) -> None:
        row, column = self.editor.cursor_location
        self._delete_range((row, column), (row, len(self._lines()[row])))
        if change:
            self._set_mode("INSERT")

    def _delete_range(self, start: TextLocation, end: TextLocation) -> None:
        self.register = self._text_between(start, end)
        self._register_is_linewise = False
        self.editor.replace("", start, end, maintain_selection_offset=False)
        self._move_cursor(start)

    def _replace_character(self, character: str) -> None:
        row, column = self.editor.cursor_location
        line = self._lines()[row]
        if len(character) != 1 or not character.isprintable() or column >= len(line):
            return
        self.editor.replace(
            character,
            (row, column),
            (row, column + 1),
            maintain_selection_offset=False,
        )
        self._move_cursor((row, column))

    def _paste_register(self) -> None:
        if not self.register:
            return
        row, column = self.editor.cursor_location
        lines = self._lines()
        if self._register_is_linewise:
            if row < len(lines) - 1:
                location = (row + 1, 0)
                value = self.register if self.register.endswith("\n") else self.register + "\n"
                cursor = location
            else:
                location = (row, len(lines[row]))
                value = "\n" + self.register.rstrip("\n")
                cursor = (row + 1, 0)
            self.editor.insert(value, location, maintain_selection_offset=False)
            self._move_cursor(cursor)
            return

        location = (row, min(column + 1, len(lines[row])))
        self.editor.insert(self.register, location, maintain_selection_offset=False)
        final_offset = self._location_to_offset(location) + len(self.register) - 1
        self._move_cursor(self._offset_to_location(final_offset))

    def _move_to_word_start(self) -> None:
        offset = self._location_to_offset(self.editor.cursor_location)
        word_start = next(
            (match.start() for match in self._word_matches() if match.start() > offset),
            None,
        )
        if word_start is not None:
            self._move_cursor(self._offset_to_location(word_start))

    def _move_to_previous_word_start(self) -> None:
        offset = self._location_to_offset(self.editor.cursor_location)
        word_starts = [match.start() for match in self._word_matches() if match.start() < offset]
        if word_starts:
            self._move_cursor(self._offset_to_location(word_starts[-1]))
        else:
            self._move_cursor((0, 0))

    def _move_to_word_end(self) -> None:
        offset = self._location_to_offset(self.editor.cursor_location)
        matches = self._word_matches()
        current = next(
            (match for match in matches if match.start() <= offset < match.end()),
            None,
        )
        target = (
            current
            if current is not None and offset < current.end() - 1
            else next((match for match in matches if match.start() > offset), None)
        )
        if target is not None:
            self._move_cursor(self._offset_to_location(target.end() - 1))

    def _word_bounds(self, location: TextLocation) -> tuple[TextLocation, TextLocation] | None:
        offset = self._location_to_offset(location)
        matches = self._word_matches()
        match = next(
            (item for item in matches if item.start() <= offset < item.end()),
            None,
        )
        if match is None:
            match = next((item for item in matches if item.start() > offset), None)
        if match is None:
            match = next((item for item in reversed(matches) if item.end() <= offset), None)
        if match is None:
            return None
        return self._offset_to_location(match.start()), self._offset_to_location(match.end())

    def _word_matches(self) -> list[re.Match[str]]:
        return list(WORD_PATTERN.finditer(self.editor.text))

    def _text_between(self, start: TextLocation, end: TextLocation) -> str:
        text = self.editor.text
        return text[self._location_to_offset(start) : self._location_to_offset(end)]

    def _location_to_offset(self, location: TextLocation) -> int:
        row, column = location
        lines = self._lines()
        row = min(max(row, 0), len(lines) - 1)
        return sum(len(line) + 1 for line in lines[:row]) + min(
            max(column, 0), len(lines[row])
        )

    def _offset_to_location(self, offset: int) -> TextLocation:
        remaining = min(max(offset, 0), len(self.editor.text))
        for row, line in enumerate(self._lines()):
            if remaining <= len(line):
                return row, remaining
            remaining -= len(line) + 1
        row = len(self._lines()) - 1
        return row, len(self._lines()[row])

    def _lines(self) -> list[str]:
        return self.editor.text.split("\n")

    def _move_cursor(self, location: TextLocation) -> None:
        self.editor.move_cursor(location, select=self._visual)
        if self.editor.is_mounted:
            self.editor.scroll_cursor_visible(animate=False)

    def _set_mode(self, mode: str) -> None:
        if self.mode == mode:
            return
        if mode == "INSERT" and self.mode != "INSERT":
            self._insert_modified = False
            self._insert_return_location = self.editor.cursor_location
        self.mode = mode
        if isinstance(self.editor, VimTextArea):
            self.editor._line_cache.clear()
            self.editor.refresh()
        if self.on_mode_changed is not None:
            self.on_mode_changed(mode)

    def note_insert_edit(self) -> None:
        """Remember that INSERT mode changed document text before Escape."""
        if self.enabled and self.mode == "INSERT":
            self._insert_modified = True

    def set_relative_numbers(self, enabled: bool) -> None:
        """Toggle relative line numbering without persisting the preference."""
        if isinstance(self.editor, VimTextArea):
            self.editor.set_relative_numbers(enabled)
            self._show_command_result(
                "relative numbers enabled" if enabled else "relative numbers disabled"
            )

    def _handle_command_key(self, event: Key) -> bool:
        if event.key == "escape":
            self.command_mode = False
            self.command_buffer = ""
            self._update_command_prompt()
            return True
        if event.key == "enter":
            command = self.command_buffer.strip()
            self.command_mode = False
            self.command_buffer = ""
            self._update_command_prompt()
            self._execute_command(command)
            return True
        if event.key == "backspace":
            self.command_buffer = self.command_buffer[:-1]
            self._update_command_prompt()
            return True
        if event.key == "ctrl+u":
            self.command_buffer = ""
            self._update_command_prompt()
            return True
        if event.is_printable and event.character is not None:
            self.command_buffer += event.character
            self._update_command_prompt()
        return True

    def _execute_command(self, command: str) -> None:
        normalized = command.lower()
        if normalized in {"set rnu", "set relativenumber"}:
            self.set_relative_numbers(True)
            return
        if normalized in {"set nornu", "set norelativenumber"}:
            self.set_relative_numbers(False)
            return
        if normalized.startswith("set "):
            self._show_command_result(
                f"E518: Unknown option: {command[4:].strip()}"
            )
            return
        if not command:
            return
        if self.on_command_submitted is not None:
            self.on_command_submitted(command)
        else:
            self._show_command_result(f"E492: Not an editor command: {command}")

    def _update_command_prompt(self) -> None:
        if self.on_command_changed is not None:
            prompt = f":{self.command_buffer}" if self.command_mode else ""
            self.on_command_changed(prompt)

    def _show_command_result(self, message: str) -> None:
        if self.on_command_result is not None:
            self.on_command_result(message)
