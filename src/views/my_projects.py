import asyncio
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

from src.utils.config import config
from src.utils.logger import Logger


ProjectRow = tuple[str, str, str, str]


@dataclass(frozen=True)
class ProjectSnapshot:
    rows: tuple[ProjectRow, ...]
    vscode_executable: str | None
    visual_studio_executable: str | None
    warning: str | None = None


def action_label(executable: str | None, available: str, missing: str) -> str:
    return available if executable else missing


def find_vscode_executable() -> str | None:
    """Return the VS Code command available on this system, if any."""
    executable = shutil.which("code") or shutil.which("code-insiders")
    if executable:
        return executable

    candidates: list[Path] = []
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(
                Path(local_app_data) / "Programs" / "Microsoft VS Code" / "Code.exe"
            )
        candidates.extend(
            Path(root) / "Microsoft VS Code" / "Code.exe"
            for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))
            if root
        )
    elif sys.platform == "darwin":
        candidates.extend(
            Path(applications) / "Visual Studio Code.app" / "Contents" / "Resources" / "app" / "bin" / "code"
            for applications in ("/Applications", str(Path.home() / "Applications"))
        )

    return next((str(path) for path in candidates if path.is_file()), None)


def find_visual_studio_executable() -> str | None:
    """Find Visual Studio's devenv executable on supported platforms."""
    executable = shutil.which("devenv")
    if executable:
        return executable

    if os.name != "nt":
        return None

    roots = {
        root
        for root in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"))
        if root
    }
    vswhere_candidates = [
        Path(root) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        for root in roots
    ]
    vswhere = next((path for path in vswhere_candidates if path.is_file()), None)
    if vswhere is not None:
        try:
            result = subprocess.run(
                [
                    str(vswhere),
                    "-latest",
                    "-products",
                    "*",
                    "-find",
                    r"Common7\IDE\devenv.exe",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            for line in result.stdout.splitlines():
                candidate = Path(line.strip())
                if candidate.is_file():
                    return str(candidate)

    # vswhere is installed with current Visual Studio releases, but retain a
    # fallback for older or incomplete installations.
    for root in roots:
        installations = Path(root).glob("Microsoft Visual Studio/*/*/Common7/IDE/devenv.exe")
        candidate = next((path for path in installations if path.is_file()), None)
        if candidate is not None:
            return str(candidate)
    return None


def load_project_snapshot(projects_dir: Path) -> ProjectSnapshot:
    """Read project folders and detect editor commands without touching the UI."""
    vscode_executable = find_vscode_executable()
    visual_studio_executable = find_visual_studio_executable()
    if not projects_dir.exists() or not projects_dir.is_dir():
        return ProjectSnapshot(
            (),
            vscode_executable,
            visual_studio_executable,
            "Projects directory does not exist. Configure it in Settings.",
        )

    rows: list[ProjectRow] = []
    try:
        entries = sorted(projects_dir.iterdir())
        for entry in entries:
            if not entry.is_dir():
                continue

            sln_files = sorted(entry.glob("*.sln"))
            if sln_files:
                for sln in sln_files:
                    rows.append((
                        entry.name,
                        sln.name,
                        "🏗️ Visual Studio Solution",
                        action_label(
                            visual_studio_executable,
                            "▶ Open with Visual Studio",
                            "Visual Studio not found",
                        ),
                    ))
                    rows.append((
                        entry.name,
                        sln.name,
                        "🏗️ Visual Studio Solution",
                        action_label(
                            vscode_executable,
                            "▶ Open in VS Code",
                            "VSCode not found",
                        ),
                    ))
            else:
                rows.append((
                    entry.name,
                    "-",
                    "📂 Folder (no .sln)",
                    action_label(
                        vscode_executable,
                        "▶ Open in VS Code",
                        "VSCode not found",
                    ),
                ))
    except OSError as error:
        return ProjectSnapshot(
            (),
            vscode_executable,
            visual_studio_executable,
            f"Could not read projects directory: {error}",
        )

    return ProjectSnapshot(
        tuple(rows),
        vscode_executable,
        visual_studio_executable,
    )


class MyProjects(Static):
    """Lists project solutions from a configured directory."""

    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.rows: list[ProjectRow] = []
        self.vscode_executable: str | None = None
        self.visual_studio_executable: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("-", id="projects-label")
        with VerticalScroll():
            yield DataTable(id="projects-datatable", zebra_stripes=True)

    def on_show(self) -> None:
        self.refresh_projects()

    def refresh_projects(self) -> None:
        self.query_one("#projects-label", Static).content = (
            f"Reading projects from: 📂 {config.projects_dir.absolute()}"
        )
        self.run_worker(
            self._load_projects(),
            name="refresh-projects",
            group="my-projects-refresh",
            exclusive=True,
        )

    async def _load_projects(self) -> None:
        try:
            snapshot = await asyncio.to_thread(load_project_snapshot, config.projects_dir)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.logger.error(f"Could not refresh projects: {error}")
            return

        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: ProjectSnapshot) -> None:
        """Apply loaded project data and update widgets on the Textual loop."""
        self.rows = list(snapshot.rows)
        self.vscode_executable = snapshot.vscode_executable
        self.visual_studio_executable = snapshot.visual_studio_executable
        if snapshot.warning:
            self.logger.warn(snapshot.warning)
        self.build_projects_datatable()

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

        if cell_value == "▶ Open with Visual Studio":
            sln_name = str(row_data[1]).strip()
            sln_path = folder_path / sln_name
            executable = self.visual_studio_executable
            if executable is None:
                self.logger.warn("Visual Studio was not found.")
                return
            self._open_with(executable, sln_path, "Visual Studio")
        elif cell_value == "▶ Open in VS Code":
            executable = self.vscode_executable
            if executable is None:
                self.logger.warn("VSCode was not found.")
                return
            self._open_with(executable, folder_path, "VS Code")
        elif cell_value == "Visual Studio not found":
            self.logger.warn("Visual Studio was not found.")
        elif cell_value == "VSCode not found":
            self.logger.warn("VSCode was not found.")

    def _open_with(self, executable: str, path: Path, application: str) -> None:
        self.logger.info(f"Opening {path} with {application}: {executable}")
        try:
            if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
                # VS Code installs its command shim as code.cmd on Windows.
                subprocess.Popen([executable, str(path)], shell=True)
            else:
                subprocess.Popen([executable, str(path)])
        except OSError as error:
            self.logger.error(f"Could not open {path} with {application}: {error}")
