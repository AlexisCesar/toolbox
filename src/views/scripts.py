"""Searchable, folder-grouped catalog of local scripts."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import pyperclip
import tomlkit
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from src.utils.config import config, iter_script_files
from src.utils.confirm_dialog import ConfirmDialog, ConfirmResult
from src.utils.logger import Logger
from src.utils.script_description_dialog import ScriptDescriptionDialog
from src.utils.script_editor_dialog import ScriptEditorDialog
from src.utils.script_runner import ScriptRunner


SCRIPT_TYPES = {
    ".py": "🐍 Python Script",
    ".sh": "🐚 Shell Script",
    ".sql": "📜 SQL",
    ".ps1": "PowerShell Script",
    ".bat": "Windows Batch Script",
    ".cmd": "Windows Command Script",
}


@dataclass(frozen=True)
class ScriptEntry:
    """A script and the metadata shown in the browser."""

    path: Path
    relative_path: str
    name: str
    script_type: str
    description: str

    @property
    def is_sql(self) -> bool:
        return self.path.suffix.lower() == ".sql"


def format_scripts_directory_label(scripts_dir: Path, depth: int) -> str:
    label = f"Reading scripts from: 📂 {Path(scripts_dir).absolute()}"
    if depth > 0:
        label += f" (with a depth of {depth} subfolders)"
    return label


def format_script_display_name(script_path: Path, scripts_dir: Path) -> str:
    """Format a script name with its nesting depth for legacy callers."""
    relative_path = Path(script_path).relative_to(scripts_dir)
    depth = len(relative_path.parts) - 1
    if depth == 0:
        return relative_path.name
    return f"📁 ({depth}) {relative_path.name}"


class Scripts(Static):
    """Browse scripts by folder, then run or inspect the selected script."""

    def __init__(self, logger: Logger, **kwargs) -> None:
        super().__init__(**kwargs)
        self.logger = logger
        self.script_runner = ScriptRunner(logger=self.logger)
        self.scripts: dict[str, ScriptEntry] = {}
        self.selected_script: ScriptEntry | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="scripts-container"):
            yield Label("Scripts", id="scripts-title")
            yield Static("", id="scripts-label")
            yield Input(
                placeholder="Search by name, folder, or description…", id="script-search"
            )
            with Horizontal(id="scripts-browser"):
                yield OptionList(id="script-list")
                with VerticalScroll(id="script-details-scroll"):
                    with Vertical(id="script-details"):
                        yield Label("Select a script", id="script-details-title")
                        yield Static(
                            "Choose a script to see its folder and available actions.",
                            id="script-details-description",
                        )
                        with Vertical(id="script-actions"):
                            yield Button("Run", variant="primary", id="script-run", disabled=True)
                            yield Button("Run External", id="script-run-external", disabled=True)
                            yield Button(
                                "Run With Parameters", id="script-run-parameters", disabled=True
                            )
                            yield Button("Copy SQL", id="script-copy", disabled=True)
                            yield Button("Open / Edit", id="script-open-edit", disabled=True)
                            yield Button(
                                "Update Description",
                                id="script-update-description",
                                disabled=True,
                            )

    def on_mount(self) -> None:
        self.logger.info("Initializing scripts.")
        self.update_script_dir_label()
        self.update_scripts_list()
        if not self.scripts:
            self.logger.warn("No scripts found in the directory.")
        else:
            self.logger.info(f"Scripts initialized with {len(self.scripts)} scripts.")

    def on_show(self) -> None:
        search = self.query_one("#script-search", Input).value
        self.update_script_dir_label()
        self.update_scripts_list(silent=True, query=search)

    def update_script_dir_label(self) -> None:
        self.query_one("#scripts-label", Static).update(
            format_scripts_directory_label(config.scripts_dir, config.scripts_depth)
        )

    def update_scripts_list(self, silent: bool = False, query: str = "") -> None:
        scripts_configs = self._load_script_configs(silent)
        scripts_dir = config.scripts_dir
        script_files = sorted(
            (
                path
                for path in iter_script_files(scripts_dir, config.scripts_depth)
                if path.is_file()
            ),
            key=lambda path: path.relative_to(scripts_dir).as_posix().casefold(),
        )

        self.scripts = {}
        for script_path in script_files:
            relative_path = script_path.relative_to(scripts_dir).as_posix()
            script_config = scripts_configs.get(
                relative_path, scripts_configs.get(script_path.name, {})
            )
            description = (
                str(script_config.get("description", ""))
                if isinstance(script_config, dict)
                else ""
            )
            script_id = relative_path
            self.scripts[script_id] = ScriptEntry(
                path=script_path,
                relative_path=relative_path,
                name=script_path.name,
                script_type=SCRIPT_TYPES.get(script_path.suffix.lower(), "Unknown Type"),
                description=description,
            )

        self._populate_list(query)

    def _load_script_configs(self, silent: bool) -> dict[str, object]:
        config_path = config.scripts_dir / "scripts_configuration.toml"
        try:
            with config_path.open("rb") as config_file:
                loaded = tomllib.load(config_file)
        except FileNotFoundError:
            if not silent:
                self.logger.warn(
                    "Scripts configurations file not found. Generate it in the Settings tab."
                )
            return {}
        except (OSError, tomllib.TOMLDecodeError) as error:
            self.logger.error(f"Could not read scripts configuration: {error}")
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "script-search":
            self._populate_list(event.value)

    def _populate_list(self, query: str) -> None:
        script_list = self.query_one("#script-list", OptionList)
        script_list.clear_options()
        self.selected_script = None
        self._update_details()

        normalized_query = query.casefold().strip()
        visible = [
            (script_id, script)
            for script_id, script in self.scripts.items()
            if normalized_query
            in f"{script.name} {script.relative_path} {script.description} {script.script_type}".casefold()
        ]

        folders: dict[str, list[tuple[str, ScriptEntry]]] = {}
        for script_id, script in visible:
            folder = Path(script.relative_path).parent.as_posix()
            folders.setdefault(folder, []).append((script_id, script))

        root_name = self._scripts_root_name()
        for folder, entries in folders.items():
            folder_path = f"/{root_name}"
            if folder != ".":
                folder_path = f"{folder_path}/{folder}"
            script_list.add_option(
                Option(Text(folder_path, style="bold"), id=f"folder:{folder}", disabled=True)
            )
            script_list.add_options(
                Option(f"  {script.name}", id=script_id) for script_id, script in entries
            )

        if not visible:
            message = "No scripts match this search." if normalized_query else "No scripts found."
            script_list.add_option(Option(message, id="no-results", disabled=True))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._select_script(event.option.id)

    def _select_script(self, script_id: str) -> None:
        self.selected_script = self.scripts.get(script_id)
        if self.selected_script is not None:
            self._update_details()

    def _update_details(self) -> None:
        self.query_one("#script-details-scroll", VerticalScroll).scroll_home(animate=False)
        title = self.query_one("#script-details-title", Label)
        description = self.query_one("#script-details-description", Static)
        actions = {
            "script-run": self.query_one("#script-run", Button),
            "script-run-external": self.query_one("#script-run-external", Button),
            "script-run-parameters": self.query_one("#script-run-parameters", Button),
            "script-copy": self.query_one("#script-copy", Button),
            "script-open-edit": self.query_one("#script-open-edit", Button),
            "script-update-description": self.query_one(
                "#script-update-description", Button
            ),
        }

        script = self.selected_script
        if script is None:
            title.update("Select a script")
            description.update("Choose a script to see its folder and available actions.")
            for button in actions.values():
                button.disabled = True
                button.styles.display = "block"
            actions["script-copy"].styles.display = "none"
            return

        title.update(script.name)
        details = f"/{self._scripts_root_name()}/{script.relative_path}\n{script.script_type}"
        if script.description:
            details += f"\n\n{script.description}"
        else:
            details += "\n\nNo description available."
        description.update(details)

        for button in actions.values():
            button.disabled = False
            button.styles.display = "block"
        if script.is_sql:
            for action_id in ("script-run", "script-run-external", "script-run-parameters"):
                actions[action_id].styles.display = "none"
            actions["script-copy"].disabled = False
        else:
            actions["script-copy"].styles.display = "none"
        actions["script-update-description"].disabled = not self._scripts_config_path().is_file()

    @staticmethod
    def _scripts_root_name() -> str:
        scripts_dir = config.scripts_dir
        return scripts_dir.name or scripts_dir.anchor.rstrip("\\/") or scripts_dir.as_posix()

    @on(Button.Pressed)
    def handle_action(self, event: Button.Pressed) -> None:
        script = self.selected_script
        if script is None:
            return

        if event.button.id == "script-run":
            self.app.push_screen(
                ConfirmDialog(f"Run {script.relative_path}?"),
                callback=lambda result: self.execute_script_callback(result, script.path),
            )
        elif event.button.id == "script-run-external":
            self.app.push_screen(
                ConfirmDialog(f"Run {script.relative_path} in external terminal?"),
                callback=lambda result: self.run_external_terminal_callback(result, script.path),
            )
        elif event.button.id == "script-run-parameters":
            latest_parameters = self._latest_parameters(script)
            self.app.push_screen(
                ConfirmDialog(
                    f"Run {script.relative_path} with parameters?",
                    askParameters=True,
                    initialValue=latest_parameters,
                ),
                callback=lambda result: self.run_with_parameters_callback(result, script.path),
            )
        elif event.button.id == "script-copy":
            self._copy_script(script)
        elif event.button.id == "script-open-edit":
            self._edit_script(script)
        elif event.button.id == "script-update-description":
            self._open_description_dialog(script)

    def _scripts_config_path(self) -> Path:
        return config.scripts_dir / "scripts_configuration.toml"

    def _latest_parameters(self, script: ScriptEntry) -> str:
        try:
            config_path = config.scripts_dir / "scripts_configuration.toml"
            with config_path.open("rb") as config_file:
                scripts_configs = tomllib.load(config_file)
        except (OSError, tomllib.TOMLDecodeError) as error:
            self.logger.warn(
                f"Could not load saved parameters for {script.relative_path}: {error}"
            )
            return ""
        script_config = scripts_configs.get(
            script.relative_path, scripts_configs.get(script.name, {})
        )
        if isinstance(script_config, dict):
            return str(script_config.get("latest_parameters", ""))
        return ""

    def _copy_script(self, script: ScriptEntry) -> None:
        try:
            pyperclip.copy(script.path.read_text())
        except (OSError, pyperclip.PyperclipException) as error:
            self.logger.error(f"Could not copy {script.relative_path}: {error}")
            return
        self.logger.info(f"Content of {script.relative_path} copied to clipboard.")

    def _edit_script(self, script: ScriptEntry) -> None:
        try:
            file_content = script.path.read_text()
        except OSError as error:
            self.logger.error(f"Could not open {script.relative_path} for editing: {error}")
            return
        self.app.push_screen(
            ScriptEditorDialog(script.path, file_content),
            callback=lambda saved: self.on_script_edit_closed(saved, script),
        )

    def on_script_edit_closed(self, saved: bool, script: ScriptEntry) -> None:
        if saved:
            self.logger.info(f"Saved script: {script.relative_path}")
            self._refresh_script_list(script.relative_path)

    def _open_description_dialog(self, script: ScriptEntry) -> None:
        if not self._scripts_config_path().is_file():
            self.logger.warn("Cannot update script descriptions without scripts_configuration.toml.")
            return
        self.app.push_screen(
            ScriptDescriptionDialog(script.name, script.description),
            callback=lambda description: self._save_script_description(description, script),
        )

    def _save_script_description(self, description: str | None, script: ScriptEntry) -> None:
        if description is None:
            return

        config_path = self._scripts_config_path()
        try:
            with config_path.open("r", encoding="utf-8") as config_file:
                doc = tomlkit.parse(config_file.read())
            config_key = script.relative_path
            if config_key not in doc and script.name in doc:
                config_key = script.name
            if config_key not in doc:
                doc[config_key] = tomlkit.table()
            doc[config_key]["description"] = description
            with config_path.open("w", encoding="utf-8") as config_file:
                config_file.write(tomlkit.dumps(doc))
        except (OSError, tomlkit.exceptions.TOMLKitError, TypeError, AttributeError) as error:
            self.logger.error(
                f"Failed to update the description for {script.relative_path}: {error}"
            )
            return

        self.logger.info(f"Updated description for {script.relative_path}.")
        self._refresh_script_list(script.relative_path)

    def _refresh_script_list(self, selected_script_id: str) -> None:
        search = self.query_one("#script-search", Input).value
        self.update_scripts_list(silent=True, query=search)
        option_list = self.query_one("#script-list", OptionList)
        option_index = option_list.get_option_index(selected_script_id)
        if option_index is not None:
            option_list.highlighted = option_index
            self._select_script(selected_script_id)

    def execute_script_callback(self, result: ConfirmResult, script_path: Path) -> None:
        if result.confirmed:
            self.script_runner.run(script_path)

    def run_external_terminal_callback(self, result: ConfirmResult, script_path: Path) -> None:
        if result.confirmed:
            self.logger.info(f"Running {script_path.name} in external terminal.")
            self.script_runner.run(script_path, external_terminal=True)

    def run_with_parameters_callback(self, result: ConfirmResult, script_path: Path) -> None:
        if result.confirmed:
            if not result.parameters:
                self.logger.warn(
                    f"No parameters provided. Running {script_path.name} without parameters."
                )
            else:
                self.logger.info(f"Running {script_path.name} with parameters: {result.parameters}")
                self.save_script_parameters(
                    script_path.relative_to(config.scripts_dir).as_posix(), result.parameters
                )
            self.script_runner.run(script_path, parameters=result.parameters)

    def save_script_parameters(self, script_name: str, parameters: str) -> None:
        try:
            config_path = config.scripts_dir / "scripts_configuration.toml"
            with config_path.open("r", encoding="utf-8") as file:
                doc = tomlkit.parse(file.read())
            if script_name not in doc:
                doc[script_name] = {}
            doc[script_name]["latest_parameters"] = parameters
            with config_path.open("w", encoding="utf-8") as file:
                file.write(tomlkit.dumps(doc))
        except (OSError, tomlkit.exceptions.TOMLKitError, TypeError) as error:
            self.logger.error(f"Failed to save parameters for {script_name}: {error}")
