"""Choose an installed IDE or editor for a project."""

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Select, Static


@dataclass(frozen=True)
class EditorOption:
    id: str
    name: str
    executable: str
    supports_folders: bool = True


class ProjectEditorDialog(ModalScreen[str | None]):
    """Let the user pick one of the locally detected project editors."""

    def __init__(self, editors: tuple[EditorOption, ...], target: Path) -> None:
        super().__init__()
        self.editors = editors
        self.target = target

    def compose(self) -> ComposeResult:
        with Vertical(id="project-editor-dialog"):
            yield Static("Open project with", id="project-editor-title")
            yield Static(str(self.target), id="project-editor-target")
            yield Select(
                ((editor.name, editor.id) for editor in self.editors),
                value=self.editors[0].id,
                allow_blank=False,
                id="project-editor-choice",
            )
            with Horizontal(id="project-editor-buttons"):
                yield Button("Open", variant="success", id="project-editor-open")
                yield Button("Cancel", id="project-editor-cancel")

    def on_mount(self) -> None:
        self.query_one("#project-editor-choice", Select).focus()
        self.call_after_refresh(self._select_first_editor)

    def _select_first_editor(self) -> None:
        """Ensure the Select has an active value after its options mount."""
        choice = self.query_one("#project-editor-choice", Select)
        if choice.value != self.editors[0].id:
            choice.value = self.editors[0].id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "project-editor-cancel":
            self.dismiss(None)
        elif event.button.id == "project-editor-open":
            self.open_selection()

    def open_selection(self) -> None:
        selected_id = self.query_one("#project-editor-choice", Select).value
        valid_ids = {editor.id for editor in self.editors}
        if not isinstance(selected_id, str) or selected_id not in valid_ids:
            return
        self.dismiss(selected_id)
