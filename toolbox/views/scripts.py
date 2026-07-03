from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static

RESOURCES = """Everything
Scripts
Logs
""".splitlines()

ROWS_MOCK = [
    ("Reset Service A001", "This script resets Service A001 on all nodes", "🐍 Python Script", "Execute"),
    ("Update Config S002", "Updates configuration S002 across the cluster", "🐚 Shell Script", "Execute"),
    ("Monitor Service Omega", "Monitors the status of Service Omega", "🐍 Python Script", "Execute"),
    ("Analyze Logs Beta", "Analyzes logs for Application Beta and generates insights", "🐍 Python Script", "Execute"),
    ("Remove Pending Requests", "Removes pending requests from the system", "📊 SQL", "Execute"),
    ("Backup Database DB1", "Creates a backup of Database DB1", "🐚 Shell Script", "Execute"),
    ("Generate Report ABC123", "Generates Report ABC123 based on the latest data", "🐍 Python Script", "Execute"),
    ("Clean Temporary Files", "Cleans up temporary files in the system", "🐚 Shell Script", "Execute"),
    ("Deploy Application X", "Deploys Application X to the production environment", "</> Powershell Script", "Execute"),
    ("Check Health K002", "Performs health checks for Service K002", "🐍 Python Script", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute"),
    ("Mock", "...", "📊 SQL", "Execute")
]

class Scripts(Static):
    """Scripts view for the Toolbox TUI."""

    def compose(self) -> ComposeResult:
        """Create the layout for the scripts view."""
        yield Static("Reading scripts from: 📂 /path/to/scripts", id="scripts-label")
        with VerticalScroll():
            yield self._build_scripts_datatable()


    def _build_scripts_datatable(self):
        """Create a datatable for displaying scripts."""
        table = DataTable(id="scripts-datatable", zebra_stripes=True)

        table.add_columns("Script Name", "Description")
        type_key = table.add_column("Type")
        table.add_column("Action")

        for row in ROWS_MOCK:
            table.add_row(*row)

        table.sort(type_key)
        return table
    