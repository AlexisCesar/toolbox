import os
from typing import Iterable
from pathlib import Path

from textual import Logger
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static, DirectoryTree, TextArea
from src.utils.config import config
from src.utils.confirm_dialog import ConfirmDialog

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
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

    def compose(self) -> ComposeResult:
        """Create the layout for the notes view."""
        
        with Horizontal(id="notes-container"):
            yield NotesDirectoryTree(config.notes_dir, id="notes-directory-tree")
              
            yield TextArea.code_editor(
                    "",
                    id="viewer",
                    read_only=False,
                    show_cursor=False,
                    show_line_numbers=True,
                    soft_wrap=True,
                )
            
        with Horizontal():
            
            yield Button("🔃 Refresh Folder", id="refresh-folder-button", flat=True, classes="icon-button")
            yield Button("🔎 Open File", id="open-file-button", flat=True, classes="icon-button")            
            yield Button("🔄️ Refresh File", id="refresh-file-button", flat=True, classes="icon-button")  
            yield Button("💾 Save", id="save-button", flat=True, classes="icon-button") 
            yield Button("📖 View Markdown", id="view-markdown-button", flat=True, classes="icon-button") 
            yield Button("❌ Delete", id="delete-button", flat=True, classes="icon-button") 
    
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
        """Abre o arquivo selecionado usando o aplicativo padrão do Windows."""
        selected_path = self.get_selected_path()
        if selected_path is None:
            self.show_message("Selecione um arquivo para abrir.")
            return

        try:
            os.startfile(selected_path)
            self.logger.info(f"Opened notes file with system default app: {selected_path}")
        except OSError as error:
            self.show_message(f"Não foi possível abrir o arquivo: {error}")

    def action_refresh_file(self) -> None:
        """Recarrega o arquivo selecionado no visualizador de texto."""
        self.load_selected_file()

    def action_save_file(self) -> None:
        """Salva o conteúdo do visualizador de texto no arquivo selecionado."""
        selected_path = self.get_selected_path()
        if selected_path is None:
            self.show_message("Selecione um arquivo para salvar.")
            return

        viewer = self.query_one("#viewer", TextArea)
        content = viewer.text

        try:
            selected_path.write_text(content, encoding="utf-8")
            self.logger.info(f"Saved notes file: {selected_path}")
            self.load_selected_file(selected_path)
        except OSError as error:
            viewer.load_text(f"Não foi possível salvar o arquivo:\n\n{error}")

    def action_view_markdown(self) -> None:
        """Switches to the markdown viewer and loads the selected markdown file."""
        selected_path = self.get_selected_path()
        if selected_path is None:
            self.show_message("Selecione um arquivo Markdown para visualizar.")
            return

        if selected_path.suffix.lower() not in {".md", ".markdown"}:
            self.show_message("Selecione um arquivo Markdown (.md ou .markdown).")
            return

        if hasattr(self.app, "show_markdown_view"):
            self.app.show_markdown_view(selected_path)
        else:
            self.logger.error("The current app does not implement markdown switching.")
    
    def action_delete_file(self) -> None:
        """Deletes the selected file after user confirmation."""
        selected_path = self.get_selected_path()
        if selected_path is None:
            self.show_message("Selecione um arquivo para excluir.")
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
                self.show_message(f"Could not delete the file:\n\n{error}")

    def get_selected_path(self) -> Path | None:
        """Retorna o arquivo selecionado na árvore, se houver um válido."""
        directory_tree = self.query_one(NotesDirectoryTree)
        selected_node = directory_tree.cursor_node

        if selected_node is None or selected_node.data is None:
            return None

        selected_path = selected_node.data.path

        if selected_path.is_dir():
            self.show_message("Selecione um arquivo, não uma pasta.")
            return None

        return selected_path

    def load_selected_file(self, path: Path | None = None) -> None:
        """Carrega o arquivo selecionado no editor, permitindo reuso em open/refresh."""
        selected_path = path or self.get_selected_path()
        if selected_path is None:
            self.show_message("Selecione um arquivo para abrir.")
            return

        self.display_file(selected_path)


    def display_file(self, path: Path) -> None:
        """Lê e mostra o conteúdo de um arquivo de texto no editor."""
        viewer = self.query_one("#viewer", TextArea)

        try:
            content = self.read_text_file(path)
        except (OSError, ValueError) as error:
            viewer.load_text(f"Não foi possível abrir o arquivo:\n\n{error}")
            return

        viewer.load_text(content)

        # Volta o visualizador para o início do arquivo.
        viewer.cursor_location = (0, 0)
        viewer.scroll_cursor_visible(animate=False)

    def on_directory_tree_file_selected(
        self,
        event: NotesDirectoryTree.FileSelected,
    ) -> None:
        """Chamado quando um arquivo é selecionado."""
        self.display_file(event.path)
        
    @staticmethod
    def read_text_file(path: Path) -> str:
        """Lê um arquivo de texto com validações básicas."""

        file_size = path.stat().st_size

        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"O arquivo possui {file_size / 1024 / 1024:.1f} MB. "
                "O limite configurado é 2 MB."
            )

        data = path.read_bytes()

        # Suporte a arquivos UTF-16 com BOM.
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16")

        # Arquivos binários normalmente possuem bytes nulos.
        if b"\x00" in data[:8192]:
            raise ValueError("O arquivo parece ser binário.")

        # UTF-8 é o padrão; CP1252 ajuda com arquivos antigos do Windows.
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue

        return data.decode("utf-8", errors="replace")