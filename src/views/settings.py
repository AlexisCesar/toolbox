import tomlkit

from tomlkit import comment, document, nl
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static
from textual import on
from pathlib import Path

from src.utils.config import config, iter_script_files, normalize_directory_path
from src.utils.logger import Logger
from src.utils.confirm_dialog import ConfirmDialog


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
            yield Label("Configure your theme, paths, and services.", id="settings-subtitle")
            with Horizontal():
                with Vertical():
                    yield from self.build_path_settings()
                    yield from self.build_theme_settings()
                with Vertical():
                    yield from self.build_health_checkers_settings()
    
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
    
    def build_health_checkers_settings(self) -> ComposeResult:
        """Build the health checkers settings section of the settings view."""
        yield Container(id="health-checkers-settings")
    
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
