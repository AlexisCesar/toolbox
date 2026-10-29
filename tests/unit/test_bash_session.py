from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.utils import bash_session
from src.utils.bash_session import BashSession, find_bash


def test_bash_override_supports_paths_with_spaces(tmp_path, monkeypatch) -> None:
    executable = tmp_path / "custom bash"
    executable.write_text("")
    monkeypatch.setenv("TOOLBOX_BASH", str(executable))
    assert find_bash() == executable.resolve()


def test_invalid_override_reports_the_configuration_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TOOLBOX_BASH", str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError, match="TOOLBOX_BASH"):
        find_bash()


def test_unix_finds_bash_on_path(tmp_path, monkeypatch) -> None:
    executable = tmp_path / "bash"
    executable.write_text("")
    monkeypatch.delenv("TOOLBOX_BASH", raising=False)
    monkeypatch.setattr(bash_session.sys, "platform", "linux")
    monkeypatch.setattr(bash_session.shutil, "which", lambda _: str(executable))
    assert find_bash() == executable.resolve()


def test_windows_detects_git_bash_without_path_entry(tmp_path, monkeypatch) -> None:
    executable = tmp_path / "Git" / "bin" / "bash.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("")
    monkeypatch.delenv("TOOLBOX_BASH", raising=False)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(bash_session.sys, "platform", "win32")
    monkeypatch.setattr(bash_session.shutil, "which", lambda _: None)
    assert find_bash() == executable.resolve()


def test_windows_does_not_use_the_legacy_wsl_launcher(tmp_path, monkeypatch) -> None:
    root = tmp_path / "Windows"
    executable = root / "System32" / "bash.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("")
    monkeypatch.delenv("TOOLBOX_BASH", raising=False)
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("SystemRoot", str(root))
    monkeypatch.setattr(bash_session.sys, "platform", "win32")
    monkeypatch.setattr(
        bash_session.shutil, "which", lambda name: str(executable) if name == "bash" else None
    )
    with pytest.raises(FileNotFoundError, match="Git for Windows"):
        find_bash()


def test_no_bash_has_actionable_message(monkeypatch) -> None:
    monkeypatch.delenv("TOOLBOX_BASH", raising=False)
    monkeypatch.setattr(bash_session.sys, "platform", "darwin")
    monkeypatch.setattr(bash_session.shutil, "which", lambda _: None)
    with pytest.raises(FileNotFoundError, match="Install Bash"):
        find_bash()


def test_session_streams_output_sends_input_and_cleans_up(monkeypatch, tmp_path) -> None:
    process = MagicMock()
    process.read.side_effect = ["first chunk", EOFError()]
    monkeypatch.setattr(bash_session, "find_bash", lambda: Path("bash"))
    spawn = MagicMock(return_value=process)
    monkeypatch.setattr(bash_session, "spawn_bash", spawn)
    waits = []

    def select_readers(readers, _writers, _errors, timeout):
        waits.append((readers, timeout))
        return [readers[0]], [], []

    monkeypatch.setattr(bash_session.select, "select", select_readers)
    close = MagicMock()
    monkeypatch.setattr(BashSession, "_close_process", close)
    session = BashSession(tmp_path, 20, 80)
    session.write("pwd\r")
    session.resize(0, 0)
    started, output = [], []

    session.run(started.append, output.append)

    assert started == [Path("bash")]
    assert output == ["first chunk"]
    spawn.assert_called_once_with(Path("bash"), tmp_path, 20, 80)
    process.write.assert_called_once_with("pwd\r")
    process.setwinsize.assert_called_once_with(1, 1)
    assert len(waits) == 2
    assert all(len(readers) == 2 for readers, _ in waits)
    assert all(timeout == bash_session.SELECT_TIMEOUT_SECONDS for _, timeout in waits)
    close.assert_called_once_with(process)
    assert session.finished.is_set()


def test_session_marks_itself_finished_when_startup_fails(monkeypatch, tmp_path) -> None:
    def fail():
        raise FileNotFoundError("No bash")

    monkeypatch.setattr(bash_session, "find_bash", fail)
    session = BashSession(tmp_path, 20, 80)
    with pytest.raises(FileNotFoundError):
        session.run(lambda _: None, lambda _: None)
    assert session.finished.is_set()


def test_stopping_before_worker_starts_does_not_spawn(monkeypatch, tmp_path) -> None:
    spawn = MagicMock()
    monkeypatch.setattr(bash_session, "spawn_bash", spawn)
    session = BashSession(tmp_path, 20, 80)
    session.stop()
    session.run(lambda _: None, lambda _: None)
    spawn.assert_not_called()
    assert session.finished.is_set()


def test_large_paste_is_chunked_to_allow_output_to_be_drained(tmp_path) -> None:
    session = BashSession(tmp_path, 20, 80)
    process = MagicMock()
    text = "á" * 2000
    session.write(text)
    session._apply_operations(process)
    first_batch = [call.args[0] for call in process.write.call_args_list]
    assert len("".join(first_batch)) < len(text)
    session._apply_operations(process)
    chunks = [call.args[0] for call in process.write.call_args_list]
    assert "".join(chunks) == text
    assert all(len(chunk) <= 256 for chunk in chunks)


def test_windows_cleanup_closes_sockets_after_stopping_process_tree(monkeypatch) -> None:
    process = MagicMock(pid=123)
    monkeypatch.setattr(bash_session.sys, "platform", "win32")
    monkeypatch.setattr(bash_session.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(bash_session.subprocess, "run", run)
    BashSession._close_process(process)
    assert run.call_args.args[0] == ["taskkill", "/PID", "123", "/T", "/F"]
    process.close.assert_called_once_with(force=True)


def test_windows_cleanup_closes_the_pty_even_if_taskkill_fails(monkeypatch) -> None:
    process = MagicMock(pid=123)
    monkeypatch.setattr(bash_session.sys, "platform", "win32")
    monkeypatch.setattr(bash_session.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(
        bash_session.subprocess, "run", MagicMock(side_effect=OSError("taskkill failed"))
    )
    with pytest.raises(OSError, match="taskkill failed"):
        BashSession._close_process(process)
    process.close.assert_called_once_with(force=True)
