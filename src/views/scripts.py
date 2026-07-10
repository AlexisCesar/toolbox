from textual import Logger
from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll

from src.utils.config import config
from src.utils.logger import Logger
from src.utils.script_inspection_dialog import ScriptInspectionDialog
from src.utils.script_runner import ScriptRunner
from src.utils.confirm_dialog import ConfirmDialog

from textual.widgets import DataTable, Static

rows = []

class Scripts(Static):
    """Scripts view for the Toolbox TUI."""
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        self.script_runner = ScriptRunner(logger=self.logger)

    def compose(self) -> ComposeResult:
        """Create the layout for the scripts view."""
        self.logger.info("Initializing scripts.")
        
        for file_path in config.scripts_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in {".py", ".sh", ".sql", ".ps1"}:
                script_type = {
                        ".py": "🐍 Python Script",
                        ".sh": "🐚 Shell Script",
                        ".sql": "📊 SQL",
                        ".ps1": "</> Powershell Script"
                    }.get(file_path.suffix.lower(), "Unknown Type")
                rows.append((file_path.name, "WIP", script_type, "▶️  Run", "📟 Run - External Terminal", "🔢 Run - With Parameters", "🔍 Open"))
        
        yield Static(f"Reading scripts from: 📂 {config.scripts_dir.absolute()}", id="scripts-label")
        with VerticalScroll():
            yield self._build_scripts_datatable()
            
        self.logger.info(f"Scripts initialized with {len(rows)} scripts.")
    

    def _build_scripts_datatable(self):
        if not rows:
            self.logger.warn("No scripts found in the directory.")
            
        """Create a datatable for displaying scripts."""
        table = DataTable(id="scripts-datatable", zebra_stripes=True)

        table.add_columns("Script Name", "Description")
        type_key = table.add_column("Type")
        table.add_column("Action")
        table.add_column("Action")
        table.add_column("Action")
        table.add_column("Inspect")

        for row in rows:
            table.add_row(*row, key=row[0])

        table.sort(type_key)
        return table
    
    
    @on(DataTable.CellSelected)
    def handle_cell_click(self, event: DataTable.CellSelected) -> None:
        cell_value = event.value
        if cell_value == "▶️  Run":
            table = self.query_one(DataTable)
            row_data = table.get_row_at(event.coordinate.row)
            script_name = row_data[0]
            script_path = config.scripts_dir / script_name
            self.app.push_screen(ConfirmDialog(f"Run {script_name}?"), callback=lambda result: self.execute_script_callback(result, script_path))
        elif cell_value == "📟 Run - External Terminal":
            table = self.query_one(DataTable)
            row_data = table.get_row_at(event.coordinate.row)
            script_name = row_data[0]
            script_path = config.scripts_dir / script_name
            self.app.push_screen(ConfirmDialog(f"Run {script_name} in external terminal?"), callback=lambda result: self.run_external_terminal_callback(result, script_path))
        elif cell_value == "🔢 Run - With Parameters":
            self.logger.warn("Run with parameters is not implemented yet.")
        elif cell_value == "🔍 Open":
            table = self.query_one(DataTable)
            row_data = table.get_row_at(event.coordinate.row)
            script_name = row_data[0]
            file_content = (config.scripts_dir / script_name).read_text()
            self.app.push_screen(ScriptInspectionDialog(file_content, script_name))

    def execute_script_callback(self, result: bool, script_path) -> None:
        if result:
            self.script_runner.run(script_path)
            
    def run_external_terminal_callback(self, result: bool, script_path) -> None:
        if result:
            self.logger.info(f"Running {script_path.name} in external terminal.")
            self.script_runner.run(script_path, external_terminal=True)