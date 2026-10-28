import os
from typing import Iterable
from pathlib import Path

from textual import Logger
from textual.app import ComposeResult
from textual.containers import Horizontal, HorizontalScroll
from textual.widgets import Button, Static, DirectoryTree, TextArea
from src.utils.config import config
from src.utils.confirm_dialog import ConfirmDialog

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

SCRIPTS_EXTENSIONS = {
    ".py",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
    ".cs",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".psm1",
    ".psd1",
    ".bat",
    ".cmd",
    ".rb",
    ".pl",
    ".pm",
    ".php",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".lua",
    ".r",
    ".awk",
    ".sql",
    ".go",
    ".rs",
    ".kt",
    ".kts",
    ".java",
    ".swift",
    ".dart",
    ".groovy",
    ".makefile",
}

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".log",
    ".csv",
} | SCRIPTS_EXTENSIONS

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".cs": "csharp",
    ".sh": "bash",
    ".ps1": "pwsh",
    ".rb": "ruby",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
    ".c": "c",
    ".cpp": "cpp",
    ".lua": "lua",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
}

class NotesDirectoryTree(DirectoryTree):
    """DirectoryTree que mostra apenas diretórios e arquivos de texto."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if not path.name.startswith(".")
            and (
                path.is_dir()
                or path.suffix.lower() in TEXT_EXTENSIONS
            )
        ]

class Notes(Static):
    """A simple notes view for the Toolbox TUI."""

    BUTTON_ACTIONS = {
        "refresh-folder-button": "refresh_folder",
        "open-file-button": "open_file",
        "refresh-file-button": "refresh_file",
        "save-button": "save_file",
        "view-markdown-button": "view_markdown",
        "delete-button": "delete_file",
    }

    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.current_file_path: Path | None = None
        self.saved_content: str | None = None

    def compose(self) -> ComposeResult:
        """Create the layout for the notes view."""
        
        with Horizontal(id="notes-container"):
            with HorizontalScroll(id="notes-directory-tree-wrapper"):
                yield NotesDirectoryTree(config.notes_dir, id="notes-directory-tree")
              
            yield TextArea.code_editor(
                    "",
                    id="viewer",
                    read_only=False,
                    show_cursor=False,
                    show_line_numbers=True,
                    soft_wrap=True,
                    language=None
                )
            
        with Horizontal():
            
            yield Button("\U0001F503 Refresh Folder", id="refresh-folder-button", flat=True, classes="icon-button")
            yield Button("\U0001F50E Open File", id="open-file-button", flat=True, classes="icon-button")
            yield Button("\U0001F504\uFE0F Refresh File", id="refresh-file-button", flat=True, classes="icon-button")
            yield Button("\U0001F4BE Save", id="save-button", flat=True, classes="icon-button")
            yield Button("\U0001F4D6 View Markdown", id="view-markdown-button", flat=True, classes="icon-button")
            yield Button("\u274C Delete", id="delete-button", flat=True, classes="icon-button")
    
    def on_show(self) -> None:
        self.action_refresh_folder(silent=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        action_name = self.BUTTON_ACTIONS.get(button_id)
        if action_name is not None:
            getattr(self, f"action_{action_name}")()

    def action_refresh_folder(self, silent: bool = False) -> None:
        if not silent:
            self.logger.info("Refreshing notes directory tree...")
        directory_tree = self.query_one(NotesDirectoryTree)
        directory_tree.path = config.notes_dir
        directory_tree.reload()

    def action_open_file(self) -> None:
        """Opens the selected file using the default Windows application."""
        selected_path = self.get_selected_path()
        if selected_path is None:
            self.logger.warn("Select a file to open.")
            return

        try:
            os.startfile(selected_path)
            self.logger.info(f"Opened notes file with system default app: {selected_path}")
        except Exception as error:
            self.logger.error(f"Error occurred while trying to open the file: {error}")

    def action_refresh_file(self) -> None:
        """Refreshes the selected file in the text viewer."""
        self.load_selected_file()

    def action_save_file(self) -> None:
        """Saves the content of the text viewer to the currently opened file."""
        file_path = self.current_file_path
        if file_path is None:
            self.logger.warn("Open a file before saving.")
            return

        viewer = self.query_one("#viewer", TextArea)
        content = viewer.text

        try:
            file_path.write_bytes(content.encode("utf-8"))
            self.saved_content = content
            self.logger.info(f"Saved notes file: {file_path}")
        except Exception as error:
            self.logger.error(f"Could not save notes file {file_path}: {error}")

    def action_view_markdown(self) -> None:
        """Switches to the markdown viewer and loads the selected markdown file."""
        selected_path = self.get_selected_path()
        if selected_path is None:
            self.logger.warn("Select a Markdown file to view.")
            return

        if selected_path.suffix.lower() not in {".md", ".markdown"}:
            self.logger.warn("Select a Markdown file (.md or .markdown).")
            return

        if hasattr(self.app, "show_markdown_preview"):
            self.app.show_markdown_preview(selected_path)
        else:
            self.logger.error("The current app does not implement markdown switching.")
    
    def action_delete_file(self) -> None:
        """Deletes the selected file after user confirmation."""
        selected_path = self.get_selected_path()
        if selected_path is None:
            self.logger.warn("Select a file to delete.")
            return

        self.app.push_screen(
            ConfirmDialog(
                f"Are you sure you want to delete the file:\n{selected_path.name}?",
                confirmButtonText="Delete",
                cancelButtonText="Cancel"
            ),
            callback=lambda result: self.confirm_delete_file(result, selected_path)
        )
    
    def confirm_delete_file(self, confirmationResult: bool, path: Path) -> None:
        if confirmationResult.confirmed:
            try:
                path.unlink()
                self.logger.info(f"Deleted notes file: {path}")
                self.action_refresh_folder(silent=True)
                self.query_one("#viewer", TextArea).load_text("")
            except OSError as error:
                self.logger.warn(f"Could not delete the file:\n\n{error}")

    def get_selected_path(self) -> Path | None:
        """Returns the selected file in the tree, if a valid one exists."""
        directory_tree = self.query_one(NotesDirectoryTree)
        selected_node = directory_tree.cursor_node

        if selected_node is None or selected_node.data is None:
            return None

        selected_path = selected_node.data.path

        if selected_path.is_dir():
            self.logger.warn("Select a file, not a folder.")
            return None

        return selected_path

    def load_selected_file(self, path: Path | None = None) -> None:
        """Loads the selected file in the editor, allowing reuse in open/refresh."""
        selected_path = path or self.get_selected_path()
        if selected_path is None:
            self.logger.warn("Select a file to open.")
            return

        self.display_file(selected_path)


    def display_file(self, path: Path) -> None:
        """Reads and displays the content of a text file in the editor."""
        viewer = self.query_one("#viewer", TextArea)

        try:
            content = self.read_text_file(path)
        except (OSError, ValueError) as error:
            self.current_file_path = None
            self.saved_content = None
            viewer.load_text(f"Could not open the file:\n\n{error}")
            return

        viewer.load_text(content)
        self.current_file_path = path
        self.saved_content = content
        self.update_highlight_based_on_file_type(viewer, path)

        # Return the viewer to the beginning of the file.
        viewer.cursor_location = (0, 0)
        viewer.scroll_cursor_visible(animate=False)
    
    def update_highlight_based_on_file_type(
        self,
        viewer: TextArea,
        file_path: Path,
    ) -> None:
        try:
            viewer.language = LANGUAGE_BY_EXTENSION.get(
                file_path.suffix.lower()
            )
        except:
            viewer.language = None

    def on_directory_tree_file_selected(
        self,
        event: NotesDirectoryTree.FileSelected,
    ) -> None:
        """Called when a file is selected."""
        if event.path == self.current_file_path:
            return

        viewer = self.query_one("#viewer", TextArea)
        if (
            self.current_file_path is not None
            and self.saved_content is not None
            and viewer.text != self.saved_content
        ):
            self.logger.warn(
                f"Unsaved changes detected in {self.current_file_path}."
            )
            self.app.push_screen(
                ConfirmDialog(
                    f"Discard unsaved changes to {self.current_file_path.name}?",
                    confirmButtonText="Discard",
                    cancelButtonText="Keep Editing",
                ),
                callback=lambda result: self.confirm_file_selection(
                    result, event.path
                ),
            )
            return

        self.display_file(event.path)

    def confirm_file_selection(
        self,
        confirmation_result,
        selected_path: Path,
    ) -> None:
        """Open a selected file only after unsaved changes are discarded."""
        if confirmation_result.confirmed:
            self.display_file(selected_path)
            return

        self.restore_current_file_selection()

    def restore_current_file_selection(self) -> None:
        """Restore the tree cursor to the file that remains open in the viewer."""
        if self.current_file_path is None:
            return

        directory_tree = self.query_one(NotesDirectoryTree)
        nodes = [directory_tree.root]
        while nodes:
            node = nodes.pop()
            if (
                node.data is not None
                and node.data.path == self.current_file_path
            ):
                directory_tree.move_cursor(node)
                return
            nodes.extend(node.children)
        
    @staticmethod
    def read_text_file(path: Path) -> str:
        """Reads a text file with basic validations."""

        file_size = path.stat().st_size

        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"The file has {file_size / 1024 / 1024:.1f} MB. "
                "The configured limit is 2 MB."
            )

        data = path.read_bytes()

        # UTF-16 + BOM file support.
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16")

        # Binary files usually have null bytes.
        if b"\x00" in data[:8192]:
            raise ValueError("The file appears to be binary.")

        # UTF-8 is the default; CP1252 helps with old Windows files.
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue

        return data.decode("utf-8", errors="replace")
