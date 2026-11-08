import re
from types import SimpleNamespace

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.gamification import TITLES, experience_for_level


class FakeLabel:
    def __init__(self) -> None:
        self.content = ""

    def update(self, content: str) -> None:
        self.content = content


class FakeProfileButton:
    def __init__(self) -> None:
        self.label = None
        self.tooltip = ""
        self.refresh_calls: list[dict[str, bool]] = []

    def refresh(self, **kwargs: bool) -> None:
        self.refresh_calls.append(kwargs)


class RecordingLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def test_profile_tooltip_labels_experience_before_selection_hint(monkeypatch) -> None:
    monkeypatch.setitem(config._data["gamification"], "experience", 41512)

    assert ToolboxTUI()._profile_tooltip() == (
        "Current EXP: 41512\nClick to select an unlocked title"
    )


def test_profile_status_relayouts_when_a_longer_title_is_selected(monkeypatch) -> None:
    ghost_title = next(title for title in TITLES if title.name == "Ghost in the Shell")
    monkeypatch.setitem(config._data["gamification"], "experience", experience_for_level(100))
    monkeypatch.setitem(
        config._data["gamification"], "selected_title", ghost_title.code
    )
    app = ToolboxTUI()
    profile_button = FakeProfileButton()
    app._profile_status_button = profile_button

    app._update_profile_status()

    assert profile_button.label.plain == "Level 100 - Ghost in the Shell"
    assert profile_button.refresh_calls == [{"layout": True}]


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
