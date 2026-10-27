from pathlib import Path

from src.utils.script_runner import ScriptRunner


class RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def system(self, message: str) -> None:
        self.events.append(("system", message))

    def warn(self, message: str) -> None:
        self.events.append(("warn", message))

    def error(self, message: str) -> None:
        self.events.append(("error", message))

    def separator(self) -> None:
        self.events.append(("separator", ""))


def test_batch_file_is_listed_as_a_script(tmp_path: Path) -> None:
    from src.utils.config import iter_script_files

    batch_file = tmp_path / "run.BAT"
    batch_file.write_text("echo hello", encoding="utf-8")

    assert list(iter_script_files(tmp_path, 0)) == [batch_file]


def test_batch_script_runs_through_cmd_with_parameters(tmp_path, monkeypatch) -> None:
    script = tmp_path / "hello.bat"
    script.write_text("echo hello", encoding="utf-8")
    logger = RecordingLogger()
    runner = ScriptRunner(logger)
    commands = []
    runner.run_subprocess = commands.append
    monkeypatch.setattr("src.utils.script_runner.platform.system", lambda: "Windows")

    runner.run(str(script), parameters='--name "Jane Doe"')

    assert commands == [["cmd", "/c", str(script), "--name", '"Jane Doe"']]


def test_batch_script_reports_unsupported_platform(tmp_path, monkeypatch) -> None:
    script = tmp_path / "hello.bat"
    script.write_text("echo hello", encoding="utf-8")
    logger = RecordingLogger()
    runner = ScriptRunner(logger)
    monkeypatch.setattr("src.utils.script_runner.platform.system", lambda: "Linux")

    runner.run(str(script))

    assert ("warn", "Windows batch scripts cannot run on Linux: hello.bat") in logger.events
