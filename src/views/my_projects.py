import os
import subprocess
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from src.utils.config import config
from src.utils.logger import Logger


class MyProjects(Static):
    """Lists project solutions from a configured directory."""

    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.rows: list[tuple[str, str, str, str]] = []

    def compose(self) -> ComposeResult:
        yield Static("-", id="projects-label")
        with VerticalScroll():
            yield DataTable(id="projects-datatable", zebra_stripes=True)

    def on_mount(self) -> None:
        self.refresh_projects()

    def on_show(self) -> None:
        self.refresh_projects()

    def refresh_projects(self) -> None:
        self.update_projects_list()
        self.query_one("#projects-label", Static).content = (
            f"Reading projects from: 📂 {config.projects_dir.absolute()}"
        )
        self.build_projects_datatable()

    def update_projects_list(self) -> None:
        self.rows = []
        projects_dir = config.projects_dir

        if not projects_dir.exists() or not projects_dir.is_dir():
            self.logger.warn("Projects directory does not exist. Configure it in Settings.")
            return

        for entry in sorted(projects_dir.iterdir()):
            if not entry.is_dir():
                continue

            sln_files = list(entry.glob("*.sln"))
            if sln_files:
                for sln in sln_files:
                    self.rows.append((
                        entry.name,
                        sln.name,
                        "🏗️ Visual Studio Solution",
                        "▶ Open Solution",
                    ))
            else:
                self.rows.append((
                    entry.name,
                    "-",
                    "📂 Folder (no .sln)",
                    "▶ Open in VS Code",
                ))

    def build_projects_datatable(self) -> None:
        table = self.query_one("#projects-datatable", DataTable)
        table.clear(columns=True)

        table.add_column("Project Folder")
        table.add_column("Solution File")
        table.add_column("Type")
        table.add_column("Action")

        for row in self.rows:
            cells = [f"\n{cell}\n" for cell in row]
            table.add_row(*cells, height=3)

    @on(DataTable.CellSelected)
    def handle_cell_click(self, event: DataTable.CellSelected) -> None:
        cell_value = str(event.value).strip()
        table = self.query_one("#projects-datatable", DataTable)
        row_data = table.get_row_at(event.coordinate.row)
        folder_name = str(row_data[0]).strip()
        folder_path = config.projects_dir / folder_name

        if cell_value == "▶ Open Solution":
            sln_name = str(row_data[1]).strip()
            sln_path = folder_path / sln_name
            self.logger.info(f"Opening solution: {sln_path}")
            os.startfile(str(sln_path))
        elif cell_value == "▶ Open in VS Code":
            self.logger.info(f"Opening folder in VS Code: {folder_path}")
            subprocess.Popen(["code", str(folder_path)])
