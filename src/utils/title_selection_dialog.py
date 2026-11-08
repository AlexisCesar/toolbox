"""Dialog for selecting an unlocked profile title."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Select, Static

from src.utils.gamification import Title, available_titles, render_title_label
from src.utils.logger import Logger


class TitleSelectionDialog(ModalScreen[str | None]):
    """Let the user choose from titles unlocked at their current level."""

    def __init__(self, logger: Logger, level: int, selected_code: str) -> None:
        super().__init__()
        self.logger = logger
        self.titles: tuple[Title, ...] = available_titles(level)
        self.selected_code = selected_code

    def compose(self) -> ComposeResult:
        with Vertical(id="title-selection-dialog"):
            yield Static("Select profile title", id="title-selection-title")
            yield Static("Titles unlocked at your current level", classes="title-selection-label")
            yield Select(
                (
                    (render_title_label(f"Level {title.level} - ", title), title.code)
                    for title in self.titles
                ),
                value=self.selected_code,
                allow_blank=False,
                id="title-selection-choice",
            )
            with Horizontal(id="title-selection-buttons"):
                yield Button("Save", variant="success", id="title-selection-save")
                yield Button("Cancel", id="title-selection-cancel")

    def on_mount(self) -> None:
        self.query_one("#title-selection-choice", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "title-selection-cancel":
            self.dismiss(None)
        elif event.button.id == "title-selection-save":
            self.save_selection()

    def save_selection(self) -> None:
        selected_code = self.query_one("#title-selection-choice", Select).value
        valid_codes = {title.code for title in self.titles}
        if not isinstance(selected_code, str) or selected_code not in valid_codes:
            self.logger.warn("The selected profile title is not unlocked.")
            return
        self.dismiss(selected_code)
