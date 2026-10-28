import tomlkit

from tomlkit import comment, document, nl
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Label, Select, Static
from textual import on
from pathlib import Path

from src.utils.config import config, iter_script_files, normalize_directory_path
from src.utils.logger import Logger
from src.utils.confirm_dialog import ConfirmDialog
from src.utils.log_config_dialog import LogConfigDialog, LogFolder
from src.utils.health_check_config_dialog import HealthCheckConfig, HealthCheckConfigDialog


THEMES = """nord
gruvbox
tokyo-night
textual-dark
solarized-light
atom-one-dark
atom-one-light
""".splitlines()

SCRIPTS_DESC_INSTRUCTIONS = """To add descriptions for your scripts, generate the descriptions file then edit it (located on your scripts folder)."""

class Settings(Static):
    """Settings view for the Toolbox TUI allowing customization and folder configurations."""
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger

    def compose(self) -> ComposeResult:
        """Create the layout for the settings view."""
        with VerticalScroll():
            yield Label("Settings", id="settings-title")
            yield Label("Configure your theme, paths, logs, and services.", id="settings-subtitle")
            with Horizontal(id="settings-columns"):
                with Vertical(id="settings-left-column"):
                    yield from self.build_path_settings()
                    yield from self.build_theme_settings()
                with Vertical(id="settings-right-column"):
                    yield from self.build_logs_settings()
                    yield from self.build_services_settings()
    
    def build_path_settings(self) -> ComposeResult:
        """Build the path settings section of the settings view."""
        with VerticalScroll(id="paths-settings"):
            yield from self.build_scripts_path_settings()
            yield from self.build_notes_path_settings()
            yield from self.build_projects_path_settings()
    
    def build_scripts_path_settings(self) -> ComposeResult:
        """Build the scripts path settings section of the settings view."""
        yield Label("Directories", id="settings-directories-title")
        yield Label("Scripts Directory")
        yield Label("Path to the folder containing your scripts.", classes="settings-general-label-italic")
        yield Input(placeholder="/example/scripts", disabled=True, id="settings-directories-scripts-input")
        yield Label("Scripts Folder Depth")
        yield Label("Include scripts from subfolders up to this depth (0–5).", classes="settings-general-label-italic")
        yield Select(((str(depth), depth) for depth in range(config.MAX_SCRIPTS_DEPTH + 1)), id="settings-scripts-depth-select")
        yield Static(SCRIPTS_DESC_INSTRUCTIONS, classes="settings-general-label-italic")
        with Horizontal(classes="settings-directories-buttons"):
            yield Button(label="Change Directory", id="settings-directories-scripts-change-button")
            yield Button(label="Generate Scripts Configuration File", id="settings-directories-generate-scripts-config-file")
    
    def build_notes_path_settings(self) -> ComposeResult:
        """Build the notes path settings section of the settings view."""
        yield Label("Notes Directory")
        yield Label("Path to the folder containing your notes.", classes="settings-general-label-italic")
        yield Input(placeholder="/example/notes", disabled=True, id="settings-directories-notes-input")
        with Horizontal(classes="settings-directories-buttons"):
            yield Button(label="Change Directory", id="settings-directories-notes-change-button")
    
    def build_projects_path_settings(self) -> ComposeResult:
        """Build the projects path settings section of the settings view."""
        yield Label("Projects Directory")
        yield Label("Path to the folder containing your project solutions.", classes="settings-general-label-italic")
        yield Input(placeholder="/example/projects", disabled=True, id="settings-directories-projects-input")
        with Horizontal(classes="settings-directories-buttons"):
            yield Button(label="Change Directory", id="settings-directories-projects-change-button")
    
    def build_theme_settings(self) -> ComposeResult:
        """Build the theme settings section of the settings view."""
        with VerticalScroll(id="theme-settings"):
            yield Label("Application Theme", id="settings-theme-title")
            with Horizontal():
                yield Select(id="settings-theme-select", options=((line, line) for line in THEMES))
                yield Button(label="Apply", id="settings-theme-apply-button")
    
    def build_logs_settings(self) -> ComposeResult:
        """Build the log folders configuration section."""
        with Vertical(id="settings-logs-settings"):
            yield Label("Logs", id="settings-logs-title")
            yield DataTable(id="settings-logs-table", zebra_stripes=True, cursor_type="row")
            with Horizontal(id="settings-logs-buttons"):
                yield Button("Add", id="settings-logs-add")
                yield Button("Edit", id="settings-logs-edit")
                yield Button("Remove", id="settings-logs-remove", variant="error")

    def build_services_settings(self) -> ComposeResult:
        with Vertical(id="settings-services-settings"):
            yield Label("Health Checks", id="settings-services-title")
            yield DataTable(id="settings-services-table", zebra_stripes=True, cursor_type="row")
            with Horizontal(id="settings-services-buttons"):
                yield Button("Add", id="settings-services-add")
                yield Button("Edit", id="settings-services-edit")
                yield Button("Remove", id="settings-services-remove", variant="error")
    
    def on_mount(self) -> None:
        self.update_fields()
        
    def on_show(self) -> None:
        self.update_fields()
        
    def update_fields(self) -> None:
        self.query_one("#settings-directories-scripts-input", Input).value = str(config.scripts_dir.absolute())
        self.query_one("#settings-directories-notes-input", Input).value = str(config.notes_dir.absolute())
        self.query_one("#settings-directories-projects-input", Input).value = str(config.projects_dir.absolute())
        self.query_one("#settings-theme-select", Select).value = str(config.theme)
        self.query_one("#settings-scripts-depth-select", Select).value = config.scripts_depth
        self.refresh_logs_table()
        self.refresh_services_table()

    def refresh_logs_table(self) -> None:
        table = self.query_one("#settings-logs-table", DataTable)
        table.clear(columns=True)
        table.add_column("Name")
        table.add_column("Folder")
        for index, entry in enumerate(config.logs):
            table.add_row(entry["name"], entry["location"], key=str(index))

    def refresh_services_table(self) -> None:
        table = self.query_one("#settings-services-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Type", "Target", "Interval")
        for index, entry in enumerate(config.services):
            check_type = str(entry.get("type", "invalid config")).upper()
            interval = f"{entry.get('interval', '?')}s" if "interval" in entry else "?"
            table.add_row(
                str(entry.get("name", "(unnamed)")),
                check_type,
                str(entry.get("target", entry.get("server", "(missing)"))),
                interval,
                key=str(index),
            )

    @on(Select.Changed, "#settings-scripts-depth-select")
    def on_scripts_depth_changed(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK:
            return
        depth = int(event.value)
        if depth != config.scripts_depth:
            config.update("scripts", "depth", depth)
            self.logger.info(f"Scripts folder depth changed to {depth}.")
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-theme-apply-button":
            theme_name = self.query_one("#settings-theme-select", Select).value
            if not theme_name in THEMES:
                return
            self.app.theme = theme_name
            config.update("ui", "theme", theme_name)
            self.logger.info(f"Application theme changed to: \"{theme_name}\".")
        
        if event.button.id == "settings-directories-scripts-change-button":
            self.app.push_screen(ConfirmDialog(f"Change scripts directory:",
                                               askParameters=True,
                                               confirmButtonText="Save",
                                               cancelButtonText="Cancel",
                                               parametersPlaceholder="Enter new path (e.g. /myfolder/myscripts)..."), callback=lambda result: self.change_scripts_dir(result))
        
        if event.button.id == "settings-directories-generate-scripts-config-file":
            self.validate_scripts_config_file()
        
        if event.button.id == "settings-directories-notes-change-button":
            self.app.push_screen(ConfirmDialog(f"Change notes directory:",
                                               askParameters=True,
                                               confirmButtonText="Save",
                                               cancelButtonText="Cancel",
                                               parametersPlaceholder="Enter new path (e.g. /myfolder/mynotes)..."), callback=lambda result: self.change_notes_dir(result))
        
        if event.button.id == "settings-directories-projects-change-button":
            self.app.push_screen(ConfirmDialog(f"Change projects directory:",
                                               askParameters=True,
                                               confirmButtonText="Save",
                                               cancelButtonText="Cancel",
                                               parametersPlaceholder="Enter new path (e.g. /myfolder/myprojects)..."), callback=lambda result: self.change_projects_dir(result))

        if event.button.id == "settings-logs-add":
            self.open_log_editor()

        if event.button.id == "settings-logs-edit":
            self.open_log_editor(self.selected_log_index())

        if event.button.id == "settings-logs-remove":
            self.confirm_remove_log(self.selected_log_index())

        if event.button.id == "settings-services-add":
            self.open_health_check_editor()

        if event.button.id == "settings-services-edit":
            self.open_health_check_editor(self.selected_service_index())

        if event.button.id == "settings-services-remove":
            self.confirm_remove_health_check(self.selected_service_index())

    def selected_log_index(self) -> int | None:
        entries = config.logs
        table = self.query_one("#settings-logs-table", DataTable)
        index = table.cursor_row
        if index is None or not 0 <= index < len(entries):
            self.logger.warn("Select a configured log folder first.")
            return None
        return index

    def open_log_editor(self, index: int | None = None) -> None:
        initial = None
        if index is not None:
            entry = config.logs[index]
            initial = LogFolder(name=entry["name"], location=entry["location"])

        self.app.push_screen(
            LogConfigDialog(logger=self.logger, initial=initial),
            callback=lambda result: self.save_log_folder(result, index),
        )

    def save_log_folder(self, result: LogFolder | None, index: int | None) -> None:
        if result is None:
            return

        entries = config.logs
        entry = {"name": result.name, "location": result.location}
        if index is None:
            entries.append(entry)
            log_message = f"Added log folder '{result.name}' at '{result.location}'."
        elif 0 <= index < len(entries):
            entries[index] = entry
            log_message = f"Updated log folder '{result.name}' at '{result.location}'."
        else:
            self.logger.warn("The selected log folder is no longer configured.")
            return

        try:
            config.update_logs(entries)
        except OSError as error:
            self.logger.error(f"Could not save log folder configuration: {error}")
            return
        self.logger.info(log_message)
        self.refresh_logs_table()

    def confirm_remove_log(self, index: int | None) -> None:
        if index is None:
            return

        entry = config.logs[index]
        self.app.push_screen(
            ConfirmDialog(
                f"Remove the log folder '{entry['name']}'?",
                confirmButtonText="Remove",
                cancelButtonText="Cancel",
            ),
            callback=lambda result: self.remove_log_folder(result.confirmed, index),
        )

    def remove_log_folder(self, confirmed: bool, index: int) -> None:
        if not confirmed:
            return

        entries = config.logs
        if not 0 <= index < len(entries):
            self.logger.warn("The selected log folder is no longer configured.")
            return

        removed = entries.pop(index)
        try:
            config.update_logs(entries)
        except OSError as error:
            self.logger.error(f"Could not save log folder configuration: {error}")
            return
        self.logger.info(f"Removed log folder '{removed['name']}'.")
        self.refresh_logs_table()

    def selected_service_index(self) -> int | None:
        entries = config.services
        index = self.query_one("#settings-services-table", DataTable).cursor_row
        if index is None or not 0 <= index < len(entries):
            self.logger.warn("Select a health check first.")
            return None
        return index

    def open_health_check_editor(self, index: int | None = None) -> None:
        initial = None
        if index is not None:
            entry = config.services[index]
            try:
                if entry["type"] not in {"http", "tcp"}:
                    raise ValueError("Unsupported check type")
                interval = int(entry["interval"])
                if interval not in {5, 10, 15, 30, 60}:
                    raise ValueError("Unsupported check interval")
                initial = HealthCheckConfig(
                    name=str(entry["name"]),
                    check_type=str(entry["type"]),
                    target=str(entry["target"]),
                    interval=interval,
                )
            except (KeyError, TypeError, ValueError):
                self.logger.warn("This health check uses an older or invalid configuration. Remove it and add it again.")
                return
        self.app.push_screen(
            HealthCheckConfigDialog(logger=self.logger, initial=initial),
            callback=lambda result: self.save_health_check(result, index),
        )

    def save_health_check(self, result: HealthCheckConfig | None, index: int | None) -> None:
        if result is None:
            return
        entries = config.services
        if any(
            str(entry.get("name", "")).casefold() == result.name.casefold()
            for existing_index, entry in enumerate(entries)
            if existing_index != index
        ):
            self.logger.warn(f"A health check named '{result.name}' already exists.")
            return

        entry = {
            "name": result.name,
            "type": result.check_type,
            "target": result.target,
            "interval": result.interval,
        }
        if index is None:
            entries.append(entry)
            message = f"Added {result.check_type.upper()} health check '{result.name}'."
        elif 0 <= index < len(entries):
            entries[index] = entry
            message = f"Updated health check '{result.name}'."
        else:
            self.logger.warn("The selected health check is no longer configured.")
            return

        try:
            config.update_services(entries)
        except OSError as error:
            self.logger.error(f"Could not save health check configuration: {error}")
            return
        self.logger.info(message)
        self.refresh_services_table()

    def confirm_remove_health_check(self, index: int | None) -> None:
        if index is None:
            return
        entry = config.services[index]
        name = str(entry.get("name", "(unnamed)"))
        self.app.push_screen(
            ConfirmDialog(
                f"Remove the health check '{name}'?",
                confirmButtonText="Remove",
                cancelButtonText="Cancel",
            ),
            callback=lambda result: self.remove_health_check(result.confirmed, index),
        )

    def remove_health_check(self, confirmed: bool, index: int) -> None:
        if not confirmed:
            return
        entries = config.services
        if not 0 <= index < len(entries):
            self.logger.warn("The selected health check is no longer configured.")
            return
        removed = entries.pop(index)
        try:
            config.update_services(entries)
        except OSError as error:
            self.logger.error(f"Could not save health check configuration: {error}")
            return
        self.logger.info(f"Removed health check '{removed.get('name', '(unnamed)')}'.")
        self.refresh_services_table()
    
    def change_scripts_dir(self, confirmationResult: bool):
        if confirmationResult.confirmed:
            if not confirmationResult.parameters:
                self.logger.warn(f"No path was provided. Keeping the current one.")
            else:
                path = normalize_directory_path(confirmationResult.parameters)
                if self.validate_directory(path):
                    self.logger.info(f"Updating scripts path to \"{path}\".")
                    config.update("paths", "scripts", path)
                    self.logger.info("Scripts path updated successfully.");
                    self.update_fields()
                else:
                    self.logger.error(f"\"{path}\" is an invalid path.")
    
    def change_notes_dir(self, confirmationResult: bool):
        if confirmationResult.confirmed:
            if not confirmationResult.parameters:
                self.logger.warn(f"No path was provided. Keeping the current one.")
            else:
                path = normalize_directory_path(confirmationResult.parameters)
                if self.validate_directory(path):
                    self.logger.info(f"Updating notes path to \"{path}\".")
                    config.update("paths", "notes", path)
                    self.logger.info("Notes path updated successfully.");
                    self.update_fields()
                else:
                    self.logger.error(f"\"{path}\" is an invalid path.")

    def change_projects_dir(self, confirmationResult: bool):
        if confirmationResult.confirmed:
            if not confirmationResult.parameters:
                self.logger.warn(f"No path was provided. Keeping the current one.")
            else:
                path = normalize_directory_path(confirmationResult.parameters)
                if self.validate_directory(path):
                    self.logger.info(f"Updating projects path to \"{path}\".")
                    config.update("paths", "projects", path)
                    self.logger.info("Projects path updated successfully.");
                    self.update_fields()
                else:
                    self.logger.error(f"\"{path}\" is an invalid path.")

    def validate_directory(self, path: str) -> bool:
        p = Path(path).expanduser()
        return p.exists() and p.is_dir()
    
    def validate_scripts_config_file(self) -> None:
        file = config.scripts_dir / "scripts_configuration.toml"
        
        if file.exists():
            self.logger.info("Config file already exists in the scripts directory.")
            self.app.push_screen(ConfirmDialog(f"Config file already exists.\nDo you want to recreate it?",
                                                confirmButtonText="Recreate",
                                                cancelButtonText="Cancel"), callback=lambda result: self.generate_scripts_config_file(result.confirmed))
        else:
            self.logger.info("Config file doesn't exists in the scripts directory. Generating a new one...")
            self.generate_scripts_config_file()
    
    def generate_scripts_config_file(self, confirmationResult: bool = True) -> None:
        if confirmationResult:
            with open(config.scripts_dir / "scripts_configuration.toml", "w", encoding="utf-8") as f:
                doc = document()
                
                doc.add(comment("This file controls configurations such as descriptions of scripts shown in the Toolbox."))
                doc.add(comment("To regenerate this file, use the settings tab in the Toolbox."))
                
                for file_path in sorted(iter_script_files(config.scripts_dir, config.scripts_depth)):
                    script_name = file_path.relative_to(config.scripts_dir).as_posix()
                    doc.add(nl())

                    script_table = tomlkit.table()
                    script_table["description"] = ""
                    if file_path.suffix.lower() != ".sql":
                        script_table["latest_parameters"] = ""

                    doc[script_name] = script_table
                
                f.write(tomlkit.dumps(doc))
                
            self.logger.info("Scripts config file generated successfully.")
