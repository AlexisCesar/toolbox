from textual import Logger
from textual.app import ComposeResult
from textual.containers import VerticalScroll

from toolbox.utils.config import config
from toolbox.utils.logger import Logger
from textual.widgets import DataTable, Static

rows = []

class Scripts(Static):
    """Scripts view for the Toolbox TUI."""
    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger

    def compose(self) -> ComposeResult:
        """Create the layout for the scripts view."""
        self.logger.info("Initializing scripts.")
        
        for file_path in config.scripts_dir.iterdir():
            if file_path.is_file() and file_path.suffix in {".py", ".sh", ".sql", ".ps1"}:
                script_type = {
                        ".py": "🐍 Python Script",
                        ".sh": "🐚 Shell Script",
                        ".sql": "📊 SQL",
                        ".ps1": "</> Powershell Script"
                    }.get(file_path.suffix, "Unknown Type")
                rows.append((file_path.name, "WIP", script_type, "Execute (not available)"))
        
        yield Static(f"Reading scripts from: 📂 {config.scripts_dir}", id="scripts-label")
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

        for row in rows:
            table.add_row(*row)

        table.sort(type_key)
        return table
    