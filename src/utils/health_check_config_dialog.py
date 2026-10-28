from dataclasses import dataclass
from urllib.parse import urlsplit

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from src.utils.logger import Logger


CHECK_INTERVALS = (5, 10, 15, 30, 60)


@dataclass
class HealthCheckConfig:
    name: str
    check_type: str
    target: str
    interval: int


class HealthCheckConfigDialog(ModalScreen[HealthCheckConfig | None]):
    """Collect and validate an HTTP or TCP health check."""

    def __init__(self, logger: Logger, initial: HealthCheckConfig | None = None) -> None:
        super().__init__()
        self.logger = logger
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="health-config-dialog"):
            yield Static(
                "Edit health check" if self.initial else "Add health check",
                id="health-config-title",
            )
            yield Static("Name", classes="health-config-label")
            yield Input(
                value=self.initial.name if self.initial else "",
                placeholder="Payments API",
                id="health-config-name",
            )
            yield Static("Type", classes="health-config-label")
            yield Select(
                (("HTTP endpoint", "http"), ("TCP connection", "tcp")),
                value=self.initial.check_type if self.initial else "http",
                id="health-config-type",
                allow_blank=False,
            )
            yield Static("URL (HTTP) or host:port (TCP)", classes="health-config-label")
            yield Input(
                value=self.initial.target if self.initial else "",
                placeholder="https://example.com/health or localhost:5432",
                id="health-config-target",
            )
            yield Static("Check interval", classes="health-config-label")
            yield Select(
                ((f"{interval}s", interval) for interval in CHECK_INTERVALS),
                value=self.initial.interval if self.initial else 5,
                id="health-config-interval",
                allow_blank=False,
            )
            yield Static("", id="health-config-error")
            with Horizontal(id="health-config-buttons"):
                yield Button("Save", variant="success", id="health-config-save")
                yield Button("Cancel", id="health-config-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "health-config-cancel":
            self.dismiss(None)
        elif event.button.id == "health-config-save":
            self.save_health_check()

    def save_health_check(self) -> None:
        name = self.query_one("#health-config-name", Input).value.strip()
        check_type = self.query_one("#health-config-type", Select).value
        target = self.query_one("#health-config-target", Input).value.strip()
        interval = self.query_one("#health-config-interval", Select).value
        error_message = self.query_one("#health-config-error", Static)

        if not name:
            self._show_error(error_message, "Enter a name for this health check.")
            return
        if check_type not in {"http", "tcp"}:
            self._show_error(error_message, "Choose a supported check type.")
            return
        if not self._valid_target(str(check_type), target):
            example = "a valid http:// or https:// URL" if check_type == "http" else "a host and port, such as localhost:5432"
            self._show_error(error_message, f"Enter {example}.")
            return
        if interval not in CHECK_INTERVALS:
            self._show_error(error_message, "Choose an interval from 5 to 60 seconds.")
            return

        self.dismiss(
            HealthCheckConfig(
                name=name,
                check_type=str(check_type),
                target=target,
                interval=int(interval),
            )
        )

    def _show_error(self, widget: Static, message: str) -> None:
        self.logger.warn(message)
        widget.update(message)

    @staticmethod
    def _valid_target(check_type: str, target: str) -> bool:
        if check_type == "http":
            try:
                parsed = urlsplit(target)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    return False
                return parsed.port is None or 1 <= parsed.port <= 65535
            except ValueError:
                return False

        try:
            parsed = urlsplit(f"//{target}")
            return (
                bool(parsed.hostname)
                and parsed.port is not None
                and 1 <= parsed.port <= 65535
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            return False
