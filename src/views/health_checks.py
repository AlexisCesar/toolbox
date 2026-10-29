import asyncio
import socket
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Label, Static

from src.utils.config import config
from src.utils.logger import Logger
from src.utils.seasonal_theme import HALLOWEEN_THEME


REQUEST_TIMEOUT = 5
HEALTHY_HTTP_STATUSES = range(200, 400)


class HealthChecks(Static):
    """Run configured HTTP and TCP checks while this view is visible."""

    def __init__(self, logger: Logger, **kwargs) -> None:
        super().__init__(**kwargs)
        self.logger = logger
        self._checks: list[tuple[int, dict[str, object]]] = []
        self._active = False
        self._timer = None
        self._pending: set[int] = set()
        self._workers = {}
        self._next_due: dict[int, float] = {}
        self._last_result: dict[int, bool] = {}

    def compose(self) -> ComposeResult:
        yield Label("Health Checks", id="health-checks-title")
        yield Label(
            "HTTP endpoints and TCP connections are checked while this screen is open.",
            id="health-checks-subtitle",
        )
        yield VerticalScroll(id="health-checks-entries")

    async def on_mount(self) -> None:
        await self.refresh_checks()

    async def on_show(self) -> None:
        self._active = True
        await self.refresh_checks()
        self._timer = self.set_interval(0.5, self.schedule_due_checks)
        self.schedule_due_checks()

    def on_hide(self) -> None:
        self._active = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        for worker in self._workers.values():
            worker.cancel()
        self._workers.clear()
        self._pending.clear()

    async def refresh_checks(self) -> None:
        entries_container = self.query_one("#health-checks-entries", VerticalScroll)
        await entries_container.remove_children()
        self._checks = []
        self._next_due.clear()

        for index, entry in enumerate(config.services):
            if not self._is_supported(entry):
                self.logger.warn(
                    f"Ignoring invalid health check configuration at services[{index}]."
                )
                continue
            self._checks.append((index, entry))
            self._next_due[index] = 0

        if not self._checks:
            await entries_container.mount(
                Static(
                    "No HTTP or TCP health checks configured. Add them in Settings.",
                    id="health-checks-empty",
                )
            )
            return

        rows = []
        for index, entry in self._checks:
            label = "HTTP" if entry["type"] == "http" else "TCP"
            rows.append(
                Horizontal(
                    Static("[dim]?[/dim]", id=f"health-status-{index}", classes="health-status"),
                    Label(str(entry["name"]), classes="health-check-name"),
                    Label(f"{label} · {entry['target']}", classes="health-check-target"),
                    Static("Waiting for first check", id=f"health-detail-{index}", classes="health-check-detail"),
                    Button("Check now", id=f"health-check-now-{index}", variant="primary"),
                    classes="health-check-entry",
                )
            )
        await entries_container.mount(*rows)

    def schedule_due_checks(self) -> None:
        if not self._active:
            return
        now = time.monotonic()
        for index, entry in self._checks:
            if index in self._pending or now < self._next_due.get(index, 0):
                continue
            self.start_check(index, entry)

    def start_check(self, index: int, entry: dict[str, object]) -> None:
        if not self._active or index in self._pending:
            return
        self._pending.add(index)
        self.query_one(f"#health-status-{index}", Static).update("[yellow]\u23F3 CHECKING[/yellow]")
        self.query_one(f"#health-detail-{index}", Static).update("Checking…")
        button = self.query_one(f"#health-check-now-{index}", Button)
        button.disabled = True
        self._workers[index] = self.run_worker(
            self.perform_check(index, entry),
            name=f"health-check-{index}",
            group=f"health-check-{index}",
            exclusive=True,
        )

    def _down_status(self) -> str:
        """Render a failed check with seasonal iconography when enabled."""
        if getattr(self.app, "theme", None) == HALLOWEEN_THEME:
            return "[red]\U0001FAA6 DOWN[/red]"
        return "[red]\u2716 DOWN[/red]"

    async def perform_check(self, index: int, entry: dict[str, object]) -> None:
        try:
            is_healthy, message, duration = await asyncio.to_thread(check_service, entry)
            if not self._active:
                return
            status = "[green]\u25CF UP[/green]" if is_healthy else self._down_status()
            self.query_one(f"#health-status-{index}", Static).update(status)
            checked_at = datetime.now().strftime("%H:%M:%S")
            self.query_one(f"#health-detail-{index}", Static).update(
                f"{message} · {duration * 1000:.0f} ms · {checked_at}"
            )
            previous = self._last_result.get(index)
            if previous is None or previous != is_healthy:
                log_message = f"Health check '{entry['name']}' {'recovered' if is_healthy and previous is False else 'is healthy' if is_healthy else 'failed'}: {message}"
                (self.logger.info if is_healthy else self.logger.warn)(log_message)
            self._last_result[index] = is_healthy
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.logger.error(f"Health check '{entry.get('name', index)}' failed unexpectedly: {error}")
            if self._active:
                self.query_one(f"#health-status-{index}", Static).update(self._down_status())
                self.query_one(f"#health-detail-{index}", Static).update(str(error))
        finally:
            self._pending.discard(index)
            self._workers.pop(index, None)
            if self._active:
                self.query_one(f"#health-check-now-{index}", Button).disabled = False
                self._next_due[index] = time.monotonic() + int(entry["interval"])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if not button_id.startswith("health-check-now-"):
            return
        try:
            index = int(button_id.removeprefix("health-check-now-"))
            entry = next(entry for check_index, entry in self._checks if check_index == index)
        except (ValueError, StopIteration):
            self.logger.warn("The selected health check is no longer available.")
            return
        self.start_check(index, entry)

    @staticmethod
    def _is_supported(entry: dict[str, object]) -> bool:
        try:
            check_type = str(entry["type"])
            if not str(entry["name"]).strip() or check_type not in {"http", "tcp"}:
                return False
            interval = int(entry["interval"])
            if interval not in {5, 10, 15, 30, 60}:
                return False
            target = str(entry["target"]).strip()
            if check_type == "http":
                parsed = urlsplit(target)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    return False
                return parsed.port is None or 1 <= parsed.port <= 65535
            parsed = urlsplit(f"//{target}")
            return (
                bool(parsed.hostname)
                and parsed.port is not None
                and 1 <= parsed.port <= 65535
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
        except (KeyError, TypeError, ValueError):
            return False


def check_service(entry: dict[str, object]) -> tuple[bool, str, float]:
    """Perform one synchronous HTTP or TCP check with a bounded timeout."""
    started = time.monotonic()
    check_type = str(entry["type"])
    target = str(entry["target"])
    try:
        if check_type == "http":
            request = Request(target, headers={"User-Agent": "Toolbox-HealthCheck/1.0"})
            try:
                with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    code = response.status
            except HTTPError as error:
                code = error.code
                if error.fp is not None:
                    error.close()
            healthy = code in HEALTHY_HTTP_STATUSES
            message = f"HTTP {code}"
        elif check_type == "tcp":
            parsed = urlsplit(f"//{target}")
            host = parsed.hostname
            port = parsed.port
            if not host or port is None or not 1 <= port <= 65535:
                raise ValueError("TCP target must be a hostname and port, such as localhost:5432")
            with socket.create_connection((host, port), timeout=REQUEST_TIMEOUT):
                pass
            healthy = True
            message = "Connection accepted"
        else:
            raise ValueError(f"Unsupported health check type: {check_type}")
    except (OSError, URLError, ValueError) as error:
        healthy = False
        message = str(error) or error.__class__.__name__

    return healthy, message, time.monotonic() - started
