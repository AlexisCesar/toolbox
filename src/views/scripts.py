import tomllib

import pyperclip
from textual import Logger
from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from rich.text import Text

from src.utils.config import config
from src.utils.logger import Logger
from src.utils.script_inspection_dialog import ScriptInspectionDialog
from src.utils.script_runner import ScriptRunner
from src.utils.confirm_dialog import ConfirmDialog

from textual.widgets import DataTable, Static

class Scripts(Static):
    """Scripts view for the Toolbox TUI."""
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.script_runner = ScriptRunner(logger=self.logger)
        self.rows = []

    def compose(self) -> ComposeResult:
        """Create the layout for the scripts view."""
        yield Static("-", id="scripts-label")
        with VerticalScroll():
            yield DataTable(id="scripts-datatable", zebra_stripes=True)
    
    def on_mount(self) -> None:
        self.logger.info("Initializing scripts.")
        self.update_scripts_list()
        if not self.rows:
            self.logger.warn("No scripts found in the directory.")
        else:
            self.logger.info(f"Scripts initialized with {len(self.rows)} scripts.")
        
    def on_show(self) -> None:
        self.update_scripts_list()
        self.update_script_dir_label()
        self.build_scripts_datatable()
    
    def update_script_dir_label(self) -> None:
        self.query_one("#scripts-label", Static).content = f"Reading scripts from: 📂 {config.scripts_dir.absolute()}"
    
    def update_scripts_list(self) -> None:
        try:
            with open(config.scripts_dir / "scripts_configuration.toml", "rb") as file:
                scripts_descriptions = tomllib.load(file)
        except FileNotFoundError:
            self.logger.warn("Scripts configurations file not found.")
            
        self.rows = []
        for file_path in config.scripts_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in {".py", ".sh", ".sql", ".ps1"}:
                script_type = {
                    ".py": "\U0001F40D Python Script",
                    ".sh": "\U0001F41A Shell Script",
                    ".sql": "\U0001F4DC SQL",
                    ".ps1": "</> Powershell Script"
                }.get(file_path.suffix.lower(), "Unknown Type")
                
                action_1 = "\U000025B6 Run"
                action_2 = "\U0001F4DF Run External"
                action_3 = "\U0001F522 Run With Parameters"
                
                if file_path.suffix.lower() == ".sql":
                    action_1 = "\U0001F4CB Copy"
                    action_2 = ""
                    action_3 = ""
                    
                self.rows.append((file_path.name, scripts_descriptions.get(file_path.name, {}).get("description"), script_type, action_1, action_2, action_3, "\U0001F50D Open"))

    def build_scripts_datatable(self):
        table = self.query_one("#scripts-datatable", DataTable)
        table.clear(columns=True)

        table.add_column("Script Name")
        table.add_column("Description", width=25)
        type_key = table.add_column("Type")
        table.add_column("Action")
        table.add_column("Action")
        table.add_column("Action")
        table.add_column("Inspect")

        for row in self.rows:
            cells = list(row)
            
            cells = [f"\n{cell}\n" for cell in cells]
            height = 3

            desc_length = len(str(cells[1]))
            if desc_length > 25:
                height = 4
                if desc_length > 40:
                    cells[1] = cells[1][:40] + "..."

            table.add_row(*cells, key=row[0], height=height)

        table.sort(type_key)
    
    
    @on(DataTable.CellSelected)
    def handle_cell_click(self, event: DataTable.CellSelected) -> None:
        cell_value = str(event.value).strip()
        if cell_value == "\U000025B6 Run":
            script_name = self.get_script_name_from_row(event.coordinate.row)
            script_path = self.get_script_path(script_name)
            self.app.push_screen(ConfirmDialog(f"Run {script_name}?"), callback=lambda result: self.execute_script_callback(result, script_path))
        elif cell_value == "\U0001F4DF Run External":
            script_name = self.get_script_name_from_row(event.coordinate.row)
            script_path = self.get_script_path(script_name)
            self.app.push_screen(ConfirmDialog(f"Run {script_name} in external terminal?"), callback=lambda result: self.run_external_terminal_callback(result, script_path))
        elif cell_value == "\U0001F522 Run With Parameters":
            script_name = self.get_script_name_from_row(event.coordinate.row)
            script_path = self.get_script_path(script_name)
            self.app.push_screen(ConfirmDialog(f"Run {script_name} with parameters?", askParameters=True), callback=lambda result: self.run_with_parameters_callback(result, script_path))
        elif cell_value == "\U0001F50D Open":
            script_name = self.get_script_name_from_row(event.coordinate.row)
            file_content = (self.get_script_path(script_name)).read_text()
            self.app.push_screen(ScriptInspectionDialog(file_content, script_name))
        elif cell_value == "\U0001F4CB Copy":
            try:
                script_name = self.get_script_name_from_row(event.coordinate.row)
                file_content = (self.get_script_path(script_name)).read_text()
                pyperclip.copy(file_content)
                self.logger.info(f"Content of {script_name} copied to clipboard.")
            except pyperclip.PyperclipException:
                self.logger.error("Unable to access the clipboard. If you are using linux, you may need to install xclip or xsel (clipboard backend).")
    
    def get_script_name_from_row(self, row_index: int) -> str:
        """Get the script name from the datatable row index."""
        table = self.query_one(DataTable)
        row_data = table.get_row_at(row_index)
        return str(row_data[0]).strip()
    
    def get_script_path(self, script_name: str):
        """Get the full path of the script."""
        return config.scripts_dir / script_name

    def execute_script_callback(self, result: bool, script_path) -> None:
        if result.confirmed:
            self.script_runner.run(script_path)
            
    def run_external_terminal_callback(self, result: bool, script_path) -> None:
        if result.confirmed:
            self.logger.info(f"Running {script_path.name} in external terminal.")
            self.script_runner.run(script_path, external_terminal=True)
    
    def run_with_parameters_callback(self, result: bool, script_path) -> None:
        if result.confirmed:
            if not result.parameters:
                self.logger.warn(f"No parameters provided. Running {script_path.name} without parameters.")
            else:
                self.logger.info(f"Running {script_path.name} with parameters: {result.parameters}")
            self.script_runner.run(script_path, parameters=result.parameters)