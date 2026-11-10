"""Connection and result dialogs for running SQL Server scripts."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Select, Static, TextArea

from src.utils.sql_server import SQLServerCredentials, SQLServerProfile


class SQLServerConnectionDialog(ModalScreen[SQLServerCredentials | None]):
    """Collect one SQL Server connection without saving its password."""

    def __init__(self, initial: SQLServerProfile | None = None) -> None:
        super().__init__()
        self.initial = initial

    def compose(self) -> ComposeResult:
        initial = self.initial
        with Vertical(id="sql-server-connection-dialog"):
            yield Static("Run on SQL Server", id="sql-server-connection-title")
            with VerticalScroll(id="sql-server-connection-form"):
                yield Static(
                    "Review the SQL file first. Changes may be committed even if a later batch fails.",
                    id="sql-server-connection-warning",
                )
                with Horizontal(id="sql-server-connection-fields"):
                    with Vertical(classes="sql-server-connection-field"):
                        yield Static("Server", classes="sql-server-field-label")
                        yield Input(
                            value=initial.server if initial else "",
                            placeholder="localhost or server\\instance",
                            id="sql-server-host",
                        )
                    with Vertical(classes="sql-server-connection-field"):
                        yield Static("Database", classes="sql-server-field-label")
                        yield Input(
                            value=initial.database if initial else "",
                            placeholder="Database name",
                            id="sql-server-database",
                        )
                    with Vertical(classes="sql-server-connection-field"):
                        yield Static("Authentication", classes="sql-server-field-label")
                        yield Select(
                            (
                                ("Integrated", "integrated"),
                                ("SQL Server", "sql"),
                            ),
                            value=initial.authentication if initial else "integrated",
                            allow_blank=False,
                            id="sql-server-authentication",
                        )
                with Horizontal(id="sql-server-sql-auth-fields"):
                    with Vertical(classes="sql-server-connection-field"):
                        yield Static("Username", classes="sql-server-field-label")
                        yield Input(
                            value=initial.username if initial else "",
                            placeholder="SQL Server username",
                            id="sql-server-username",
                        )
                    with Vertical(classes="sql-server-connection-field"):
                        yield Static("Password", classes="sql-server-field-label")
                        yield Input(
                            placeholder="Enter password for this run",
                            password=True,
                            id="sql-server-password",
                        )
                yield Checkbox(
                    "Trust the server certificate (local/testing only)",
                    value=initial.trust_server_certificate if initial else False,
                    id="sql-server-trust-certificate",
                )
                yield Static(
                    "Connection details stay in memory until Toolbox closes. Passwords are requested each run and never saved to a file.",
                    id="sql-server-connection-security-note",
                )
                yield Static("", id="sql-server-connection-error")
            with Horizontal(id="sql-server-connection-buttons"):
                yield Button("Connect & Run", variant="success", id="sql-server-connect-run")
                yield Button("Cancel", id="sql-server-cancel")

    def on_mount(self) -> None:
        self._update_authentication_fields()
        self.query_one("#sql-server-host", Input).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sql-server-authentication":
            self._update_authentication_fields()

    def _update_authentication_fields(self) -> None:
        authentication = self.query_one("#sql-server-authentication", Select).value
        fields = self.query_one("#sql-server-sql-auth-fields", Horizontal)
        fields.styles.display = "block" if authentication == "sql" else "none"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sql-server-cancel":
            self.dismiss(None)
        elif event.button.id == "sql-server-connect-run":
            self.connect_and_run()

    def connect_and_run(self) -> None:
        server = self.query_one("#sql-server-host", Input).value.strip()
        database = self.query_one("#sql-server-database", Input).value.strip()
        authentication = self.query_one("#sql-server-authentication", Select).value
        username = self.query_one("#sql-server-username", Input).value.strip()
        password = self.query_one("#sql-server-password", Input).value
        error = self.query_one("#sql-server-connection-error", Static)

        if not server:
            error.update("Enter a SQL Server name or address.")
            self.query_one("#sql-server-host", Input).focus()
            return
        if not database:
            error.update("Enter the database name.")
            self.query_one("#sql-server-database", Input).focus()
            return
        if authentication not in {"integrated", "sql"}:
            error.update("Choose a supported authentication method.")
            return
        if authentication == "sql" and (not username or not password):
            error.update("Enter the SQL Server username and password.")
            self.query_one(
                "#sql-server-username" if not username else "#sql-server-password",
                Input,
            ).focus()
            return

        profile = SQLServerProfile(
            server=server,
            database=database,
            authentication=str(authentication),
            username=username if authentication == "sql" else "",
            trust_server_certificate=self.query_one(
                "#sql-server-trust-certificate", Checkbox
            ).value,
        )
        self.dismiss(
            SQLServerCredentials(
                profile=profile,
                password=password if authentication == "sql" else "",
            )
        )


class SQLServerResultDialog(ModalScreen[None]):
    """Show a bounded query preview or a sanitized execution error."""

    def __init__(self, title: str, report: str) -> None:
        super().__init__()
        self.heading = title
        self.report = report

    def compose(self) -> ComposeResult:
        with Vertical(id="sql-server-result-dialog"):
            yield Static(self.heading, id="sql-server-result-title")
            yield TextArea(
                self.report,
                read_only=True,
                soft_wrap=True,
                id="sql-server-result-output",
            )
            with Horizontal(id="sql-server-result-buttons"):
                yield Button("Close", variant="primary", id="sql-server-result-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sql-server-result-close":
            self.dismiss()
