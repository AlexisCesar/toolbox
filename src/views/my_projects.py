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
from src.utils.project_editor_dialog import EditorOption, ProjectEditorDialog


ProjectRow = tuple[str, str, str, str]


@dataclass(frozen=True)
class ProjectSnapshot:
    rows: tuple[ProjectRow, ...]
    editors: tuple[EditorOption, ...]
    warning: str | None = None


EDITOR_COMMANDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("rider", "JetBrains Rider", ("rider", "rider64")),
    ("idea", "IntelliJ IDEA", ("idea", "idea64")),
    ("pycharm", "PyCharm", ("pycharm", "pycharm64")),
    ("webstorm", "WebStorm", ("webstorm", "webstorm64")),
    ("goland", "GoLand", ("goland", "goland64")),
    ("clion", "CLion", ("clion", "clion64")),
    ("phpstorm", "PhpStorm", ("phpstorm", "phpstorm64")),
    ("rubymine", "RubyMine", ("rubymine", "rubymine64")),
    ("rustrover", "RustRover", ("rustrover", "rustrover64")),
    ("devin", "Devin Desktop", ("devin", "windsurf")),
    ("cursor", "Cursor", ("cursor",)),
    ("sublime", "Sublime Text", ("subl", "sublime_text")),
    ("zed", "Zed", ("zed",)),
    ("notepadpp", "Notepad++", ("notepad++", "notepad-plus-plus")),
)

JETBRAINS_PRODUCT_DIRS: dict[str, tuple[str, ...]] = {
    "rider": ("Rider", "JetBrains Rider"),
    "idea": ("IntelliJ IDEA",),
    "pycharm": ("PyCharm",),
    "webstorm": ("WebStorm",),
    "goland": ("GoLand",),
    "clion": ("CLion",),
    "phpstorm": ("PhpStorm",),
    "rubymine": ("RubyMine",),
    "rustrover": ("RustRover",),
}

JETBRAINS_WINDOWS_BINARIES: dict[str, tuple[str, ...]] = {
    "rider": ("rider64.exe", "rider.exe"),
    "idea": ("idea64.exe", "idea.exe"),
    "pycharm": ("pycharm64.exe", "pycharm.exe"),
    "webstorm": ("webstorm64.exe", "webstorm.exe"),
    "goland": ("goland64.exe", "goland.exe"),
    "clion": ("clion64.exe", "clion.exe"),
    "phpstorm": ("phpstorm64.exe", "phpstorm.exe"),
    "rubymine": ("rubymine64.exe", "rubymine.exe"),
    "rustrover": ("rustrover64.exe", "rustrover.exe"),
}

MACOS_APP_LAUNCHERS: dict[str, tuple[tuple[str, str], ...]] = {
    "rider": (
        ("JetBrains Rider.app", "Contents/MacOS/rider"),
        ("Rider.app", "Contents/MacOS/rider"),
    ),
    "idea": (
        ("IntelliJ IDEA.app", "Contents/MacOS/idea"),
        ("IntelliJ IDEA CE.app", "Contents/MacOS/idea"),
    ),
    "pycharm": (
        ("PyCharm.app", "Contents/MacOS/pycharm"),
        ("PyCharm CE.app", "Contents/MacOS/pycharm"),
    ),
    "webstorm": (("WebStorm.app", "Contents/MacOS/webstorm"),),
    "goland": (("GoLand.app", "Contents/MacOS/goland"),),
    "clion": (("CLion.app", "Contents/MacOS/clion"),),
    "phpstorm": (("PhpStorm.app", "Contents/MacOS/phpstorm"),),
    "rubymine": (("RubyMine.app", "Contents/MacOS/rubymine"),),
    "rustrover": (("RustRover.app", "Contents/MacOS/rustrover"),),
    "devin": (
        ("Devin.app", "Contents/MacOS/Devin"),
        ("Devin.app", "Contents/MacOS/Electron"),
        ("Windsurf.app", "Contents/MacOS/Windsurf"),
        ("Windsurf.app", "Contents/MacOS/Electron"),
    ),
    "cursor": (("Cursor.app", "Contents/MacOS/Cursor"),),
    "sublime": (("Sublime Text.app", "Contents/SharedSupport/bin/subl"),),
    "zed": (("Zed.app", "Contents/MacOS/zed"),),
}


def _first_existing(paths: list[Path]) -> str | None:
    return next((str(path) for path in paths if path.is_file()), None)


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

    return _first_existing(candidates)


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


def _find_jetbrains_windows_executable(
    editor_id: str,
    local_root: Path | None,
    program_files: list[Path],
) -> str | None:
    """Find a JetBrains launcher in a standard install or Toolbox directory."""
    binaries = JETBRAINS_WINDOWS_BINARIES[editor_id]
    candidates: list[Path] = []
    if local_root:
        for product_dir in JETBRAINS_PRODUCT_DIRS[editor_id]:
            toolbox_root = local_root / "JetBrains" / "Toolbox" / "apps" / product_dir
            candidates.extend(
                path
                for binary in binaries
                for path in toolbox_root.glob(f"*/*/bin/{binary}")
            )

    roots = [*program_files]
    if local_root:
        roots.append(local_root / "Programs")
    for root in roots:
        product_root = root / "JetBrains"
        for product_dir in JETBRAINS_PRODUCT_DIRS[editor_id]:
            for install in product_root.glob(f"{product_dir}*/bin"):
                candidates.extend(install / name for name in binaries)
    return _first_existing(candidates)


def _find_windows_editor_executable(editor_id: str) -> str | None:
    """Find an editor executable in common Windows installation directories."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    local_root = Path(local_app_data) if local_app_data else None
    program_files = [
        Path(root)
        for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))
        if root
    ]
    if editor_id in JETBRAINS_WINDOWS_BINARIES:
        return _find_jetbrains_windows_executable(editor_id, local_root, program_files)

    candidates: list[Path] = []
    if editor_id == "cursor":
        if local_root:
            candidates.append(local_root / "Programs" / "Cursor" / "Cursor.exe")
        candidates.extend(root / "Cursor" / "Cursor.exe" for root in program_files)
    elif editor_id == "devin":
        install_names = (("Devin", "Devin.exe"), ("Windsurf", "Windsurf.exe"))
        if local_root:
            candidates.extend(
                local_root / "Programs" / folder / executable
                for folder, executable in install_names
            )
        candidates.extend(
            root / folder / executable
            for root in program_files
            for folder, executable in install_names
        )
    elif editor_id == "sublime":
        candidates.extend(root / "Sublime Text" / "subl.exe" for root in program_files)
    elif editor_id == "zed" and local_root:
        candidates.append(local_root / "Programs" / "Zed" / "Zed.exe")
    elif editor_id == "notepadpp":
        candidates.extend(root / "Notepad++" / "notepad++.exe" for root in program_files)
    return _first_existing(candidates)


def _find_macos_editor_executable(editor_id: str) -> str | None:
    """Find a macOS app launcher in the system or user's Applications folder."""
    candidates = [
        applications / app_name / binary
        for app_name, binary in MACOS_APP_LAUNCHERS.get(editor_id, ())
        for applications in (Path("/Applications"), Path.home() / "Applications")
    ]
    return _first_existing(candidates)


def _find_editor_executable(editor_id: str, commands: tuple[str, ...]) -> str | None:
    """Find an editor command or a common per-user installation location."""
    executable = next((path for name in commands if (path := shutil.which(name))), None)
    if executable:
        return executable
    if os.name == "nt":
        return _find_windows_editor_executable(editor_id)
    if sys.platform == "darwin":
        return _find_macos_editor_executable(editor_id)
    return None


def find_installed_editors() -> tuple[EditorOption, ...]:
    """Return supported editors found on PATH or in common install locations."""
    editors: list[EditorOption] = []
    vscode = find_vscode_executable()
    if vscode:
        editors.append(EditorOption("vscode", "Visual Studio Code", vscode))
    visual_studio = find_visual_studio_executable()
    if visual_studio:
        editors.append(EditorOption("visual-studio", "Visual Studio", visual_studio))

    for editor_id, name, commands in EDITOR_COMMANDS:
        executable = _find_editor_executable(editor_id, commands)
        if executable:
            editors.append(
                EditorOption(
                    editor_id,
                    name,
                    executable,
                    supports_folders=editor_id != "notepadpp",
                )
            )
    return tuple(editors)


def load_project_snapshot(projects_dir: Path) -> ProjectSnapshot:
    """Read project folders and detect installed IDEs without touching the UI."""
    editors = find_installed_editors()
    if not projects_dir.exists() or not projects_dir.is_dir():
        return ProjectSnapshot(
            (),
            editors,
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
                rows.extend(
                    (
                        entry.name,
                        sln.name,
                        "🏗️ Visual Studio Solution",
                        "▶ Open",
                    )
                    for sln in sln_files
                )
            else:
                rows.append((entry.name, "-", "📂 Folder (no .sln)", "▶ Open"))
    except OSError as error:
        return ProjectSnapshot(
            (),
            editors,
            f"Could not read projects directory: {error}",
        )

    return ProjectSnapshot(tuple(rows), editors)


class MyProjects(Static):
    """Lists project solutions from a configured directory."""

    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.rows: list[ProjectRow] = []
        self.editors: tuple[EditorOption, ...] = ()

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
        self.editors = snapshot.editors
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
        if str(event.value).strip() != "▶ Open":
            return

        table = self.query_one("#projects-datatable", DataTable)
        row_data = table.get_row_at(event.coordinate.row)
        folder_name = str(row_data[0]).strip()
        solution_name = str(row_data[1]).strip()
        available_editors = self.editors
        if solution_name == "-":
            available_editors = tuple(
                editor for editor in self.editors if editor.supports_folders
            )
        if not available_editors:
            self.logger.warn("No supported IDEs or editors were found.")
            self.notify("No supported IDEs or editors were found.", severity="warning")
            return

        folder_path = config.projects_dir / folder_name
        self.app.push_screen(
            ProjectEditorDialog(available_editors, folder_path),
            lambda editor_id: self.open_project_with_editor(
                editor_id,
                folder_path,
                folder_path / solution_name if solution_name != "-" else None,
            ),
        )

    def open_project_with_editor(
        self,
        editor_id: str | None,
        folder_path: Path,
        solution_path: Path | None,
    ) -> None:
        if editor_id is None:
            return
        editor = next((option for option in self.editors if option.id == editor_id), None)
        if editor is None:
            self.logger.warn("The selected editor is no longer available.")
            return
        path = (
            solution_path
            if solution_path is not None and editor.id in {"visual-studio", "rider"}
            else folder_path
        )
        self._open_with(editor.executable, path, editor.name)

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
