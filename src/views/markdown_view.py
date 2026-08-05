from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import MarkdownViewer, Static

from src.utils.logger import Logger
from src.views.notes import Notes


class MarkdownView(Static):
    """A simple markdown view for the Toolbox TUI."""

    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger

    def compose(self) -> ComposeResult:
        """Create the layout for the markdown view."""
        
        with Horizontal(id="markdown-container"):
            yield MarkdownViewer(id="markdown-viewer")

    def load_markdown(self, path: Path | None = None, content: str | None = None) -> None:
        """Load markdown content into the viewer."""
        self.run_worker(self._load_markdown(path, content), exclusive=True)

    async def _load_markdown(self, path: Path | None = None, content: str | None = None) -> None:
        markdown_viewer = self.query_one(MarkdownViewer)

        if content is None:
            if path is None:
                content = ""
            else:
                try:
                    content = Notes.read_text_file(path)
                except Exception as error:
                    content = f"Something went wrong while reading the file:\n\n{error}"
                    self.logger.error(content)

        await markdown_viewer.document.update(content)