"""Execute SQL Server scripts through an installed ODBC driver."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


CONNECT_TIMEOUT_SECONDS = 15
MAX_BATCH_REPEAT_COUNT = 1000
MAX_PREVIEW_ROWS = 100
MAX_PREVIEW_CELL_LENGTH = 120
SQL_SERVER_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
)
GO_LINE = re.compile(r"^\s*GO(?:\s+(\d+))?\s*(?:--.*)?$", re.IGNORECASE)


@dataclass(frozen=True)
class SQLServerProfile:
    """Non-secret connection fields that can be reused in the current session."""

    server: str
    database: str
    authentication: str
    username: str = ""
    trust_server_certificate: bool = False


@dataclass(frozen=True)
class SQLServerCredentials:
    """Connection details for one execution; the password is never persisted."""

    profile: SQLServerProfile
    password: str = ""


@dataclass(frozen=True)
class SQLQueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    total_rows: int


@dataclass(frozen=True)
class SQLServerExecutionReport:
    batches_executed: int
    rows_affected: int
    result_sets: tuple[SQLQueryResult, ...]

    def render(self) -> str:
        """Render a plain-text report for the result dialog."""
        lines = [
            "SQL Server script completed.",
            f"Batches executed: {self.batches_executed}",
            f"Rows affected: {self.rows_affected}",
        ]
        for index, result in enumerate(self.result_sets, start=1):
            shown_rows = len(result.rows)
            lines.extend(
                [
                    "",
                    f"Result set {index}: {result.total_rows} row(s).",
                    " | ".join(result.columns),
                ]
            )
            lines.extend(" | ".join(row) for row in result.rows)
            if shown_rows < result.total_rows:
                lines.append(
                    f"Showing the first {shown_rows} of {result.total_rows} rows."
                )
        return "\n".join(lines)


def _odbc_value(value: str) -> str:
    """Quote a connection-string value and escape closing braces."""
    return "{" + value.replace("}", "}}") + "}"


def build_connection_string(driver: str, credentials: SQLServerCredentials) -> str:
    """Build a SQL Server ODBC string without exposing credentials in logs."""
    profile = credentials.profile
    attributes = [
        f"DRIVER={_odbc_value(driver)}",
        f"SERVER={_odbc_value(profile.server)}",
        f"DATABASE={_odbc_value(profile.database)}",
        "Encrypt=yes",
        f"TrustServerCertificate={'yes' if profile.trust_server_certificate else 'no'}",
    ]
    if profile.authentication == "integrated":
        attributes.append("Trusted_Connection=yes")
    elif profile.authentication == "sql":
        attributes.extend(
            [
                f"UID={_odbc_value(profile.username)}",
                f"PWD={_odbc_value(credentials.password)}",
            ]
        )
    else:
        raise ValueError("Choose Windows or SQL Server authentication.")
    return ";".join(attributes) + ";"


def split_sql_server_batches(sql: str) -> list[str]:
    """Split on SQL Server's GO batch separator, ignoring strings and comments."""
    batches: list[str] = []
    current_lines: list[str] = []
    quote: str | None = None
    block_comment_depth = 0

    for line in sql.splitlines():
        separator = (
            GO_LINE.fullmatch(line)
            if quote is None and block_comment_depth == 0
            else None
        )
        if separator:
            batch = "\n".join(current_lines).strip()
            if batch:
                repeat_count = int(separator.group(1) or "1")
                if not 1 <= repeat_count <= MAX_BATCH_REPEAT_COUNT:
                    raise ValueError(
                        f"GO repeat count must be between 1 and {MAX_BATCH_REPEAT_COUNT}."
                    )
                batches.extend([batch] * repeat_count)
            current_lines.clear()
            continue

        current_lines.append(line)
        quote, block_comment_depth = _advance_lexical_state(
            line, quote, block_comment_depth
        )

    final_batch = "\n".join(current_lines).strip()
    if final_batch:
        batches.append(final_batch)
    return batches


def _advance_lexical_state(
    line: str, quote: str | None, block_comment_depth: int
) -> tuple[str | None, int]:
    index = 0
    while index < len(line):
        pair = line[index : index + 2]
        if block_comment_depth:
            if pair == "/*":
                block_comment_depth += 1
                index += 2
            elif pair == "*/":
                block_comment_depth -= 1
                index += 2
            else:
                index += 1
            continue

        if quote:
            terminator = "]" if quote == "[" else quote
            if line[index] == terminator:
                if index + 1 < len(line) and line[index + 1] == terminator:
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if pair == "--":
            break
        if pair == "/*":
            block_comment_depth = 1
            index += 2
        elif line[index] in "'\"[":
            quote = "[" if line[index] == "[" else line[index]
            index += 1
        else:
            index += 1

    return quote, block_comment_depth


def _format_cell(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        rendered = value[: MAX_PREVIEW_CELL_LENGTH // 2].hex()
        if len(value) > MAX_PREVIEW_CELL_LENGTH // 2:
            rendered += "…"
    else:
        rendered = str(value)
        rendered = " ".join(rendered.split())
        if len(rendered) > MAX_PREVIEW_CELL_LENGTH:
            rendered = rendered[: MAX_PREVIEW_CELL_LENGTH - 1] + "…"
    return rendered.replace("|", "\\|")


def execute_sql_server_script(
    script_path: Path,
    credentials: SQLServerCredentials,
    query_timeout_seconds: int,
) -> SQLServerExecutionReport:
    """Execute a SQL Server script and collect a bounded preview of result rows."""
    try:
        import pyodbc
    except ImportError as error:
        raise RuntimeError(
            "SQL Server execution requires the pyodbc package and Microsoft ODBC Driver 17 or 18."
        ) from error

    installed_drivers = set(pyodbc.drivers())
    driver = next((item for item in SQL_SERVER_DRIVERS if item in installed_drivers), None)
    if driver is None:
        raise RuntimeError(
            "Install Microsoft ODBC Driver 17 or 18 for SQL Server, then restart Toolbox."
        )

    sql = Path(script_path).read_text(encoding="utf-8-sig")
    batches = split_sql_server_batches(sql)
    if not batches:
        raise ValueError("The SQL script is empty.")

    connection = pyodbc.connect(
        build_connection_string(driver, credentials),
        timeout=CONNECT_TIMEOUT_SECONDS,
        autocommit=True,
    )
    result_sets: list[SQLQueryResult] = []
    rows_affected = 0
    try:
        cursor = connection.cursor()
        cursor.timeout = max(1, int(query_timeout_seconds))
        for batch in batches:
            cursor.execute(batch)
            while True:
                if cursor.description:
                    columns = tuple(
                        _format_cell(column[0]) for column in cursor.description
                    )
                    preview_rows: list[tuple[str, ...]] = []
                    total_rows = 0
                    while fetched_rows := cursor.fetchmany(500):
                        for row in fetched_rows:
                            total_rows += 1
                            if len(preview_rows) < MAX_PREVIEW_ROWS:
                                preview_rows.append(
                                    tuple(_format_cell(value) for value in row)
                                )
                    result_sets.append(
                        SQLQueryResult(columns, tuple(preview_rows), total_rows)
                    )
                elif cursor.rowcount > 0:
                    rows_affected += cursor.rowcount
                if not cursor.nextset():
                    break
        cursor.close()
    finally:
        connection.close()

    return SQLServerExecutionReport(len(batches), rows_affected, tuple(result_sets))
