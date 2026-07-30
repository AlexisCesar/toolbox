import tomlkit

from tomlkit import array, comment, document, nl, table
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static
from pathlib import Path

from src.utils.config import config
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
                    with VerticalScroll(id="paths-settings"):
                        yield Label("Directories", id="settings-directories-title")
                        yield Label("Scripts Directory")
                        yield Label("Path to the folder containing your scripts.", classes="settings-general-label-italic")
                        yield Input(placeholder="/example/scripts", disabled=True, id="settings-directories-input")
                        yield Static(SCRIPTS_DESC_INSTRUCTIONS, classes="settings-general-label-italic")
                        with Horizontal(id="settings-directories-buttons"):
                            yield Button(label="Change Directory", id="settings-directories-change-button")
                            yield Button(label="Generate Scripts Configuration File", id="settings-directories-generate-scripts-config-file")
                    with VerticalScroll(id="theme-settings"):
                        yield Label("Application Theme", id="settings-theme-title")
                        with Horizontal():
                            yield Select(id="settings-theme-select", options=((line, line) for line in THEMES))
                            yield Button(label="Apply", id="settings-theme-apply-button")
                with Vertical():
                    yield Container(id="health-checkers-settings")
    
    def on_mount(self) -> None:
        self.update_fields()
        
    def on_show(self) -> None:
        self.update_fields()
        
    def update_fields(self) -> None:
        self.query_one("#settings-directories-input", Input).value = str(config.scripts_dir.absolute())
        self.query_one("#settings-theme-select", Select).value = str(config.theme)
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-theme-apply-button":
            theme_name = self.query_one("#settings-theme-select", Select).value
            if not theme_name in THEMES:
                return
            self.app.theme = theme_name
            config.update("ui", "theme", theme_name)
            self.logger.info(f"Application theme changed to: \"{theme_name}\".")
        
        if event.button.id == "settings-directories-change-button":
            self.app.push_screen(ConfirmDialog(f"Change scripts directory:",
                                               askParameters=True,
                                               confirmButtonText="Save",
                                               cancelButtonText="Cancel",
                                               parametersPlaceholder="Enter new path (e.g. /myfolder/myscripts)..."), callback=lambda result: self.change_scripts_dir(result))
        
        if event.button.id == "settings-directories-generate-scripts-config-file":
            self.validate_scripts_config_file()
    
    def change_scripts_dir(self, confirmationResult: bool):
        if confirmationResult.confirmed:
            if not confirmationResult.parameters:
                self.logger.warn(f"No path was provided. Keeping the current one.")
            else:
                if self.validate_directory(confirmationResult.parameters):
                    self.logger.info(f"Updating scripts path to \"{confirmationResult.parameters}\".")
                    config.update("paths", "scripts", confirmationResult.parameters)
                    self.logger.info("Scripts path updated successfully.");
                    self.update_fields()
                else:
                    self.logger.error(f"\"{confirmationResult.parameters}\" is an invalid path.")

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
                
                for file_path in config.scripts_dir.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in {".py", ".sh", ".sql", ".ps1"}:
                        doc.add(nl())
                                 
                        table = tomlkit.table()
                        table["description"] = ""

                        doc[file_path.name] = table               
                
                f.write(tomlkit.dumps(doc))
                
            self.logger.info("Scripts config file generated successfully.")