import re
from types import SimpleNamespace

from src.tui import ToolboxTUI


class FakeLabel:
    def __init__(self) -> None:
        self.content = ""

    def update(self, content: str) -> None:
        self.content = content


class RecordingLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def test_runtime_status_displays_clock_cpu_and_resident_memory() -> None:
    app = ToolboxTUI()
    label = FakeLabel()
    app._runtime_status_label = label
    app._process = SimpleNamespace(
        cpu_percent=lambda: 12.34,
        memory_info=lambda: SimpleNamespace(rss=64 * 1024 * 1024),
    )

    app._update_runtime_status()

    assert re.fullmatch(
        r"\d{2}:\d{2}:\d{2}  CPU 12\.3%  RAM 64\.0 MB",
        label.content,
    )


def test_runtime_status_logs_metrics_errors_once() -> None:
    app = ToolboxTUI()
    label = FakeLabel()
    logger = RecordingLogger()

    def fail_to_read_cpu() -> float:
        raise OSError("metrics unavailable")

    app._runtime_status_label = label
    app._runtime_metrics_warning_logged = False
    app._process = SimpleNamespace(cpu_percent=fail_to_read_cpu)
    app.logger = logger

    app._update_runtime_status()
    app._update_runtime_status()

    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}  CPU --  RAM --", label.content)
    assert logger.warnings == [
        "Could not read TUI resource usage: metrics unavailable"
    ]
