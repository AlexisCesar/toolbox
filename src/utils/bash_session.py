"""Persistent Bash sessions backed by a native pseudoterminal."""

import os
from pathlib import Path
from queue import Empty, Queue
import select
import shutil
import subprocess
import sys
from threading import Event
from typing import Callable


def find_bash() -> Path:
    """Find Bash, preferring Git Bash over Windows' legacy WSL launcher."""
    configured = os.environ.get("TOOLBOX_BASH")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        raise FileNotFoundError(f"TOOLBOX_BASH does not point to a file: {candidate}")

    candidates: list[Path] = []
    if sys.platform == "win32":
        git = shutil.which("git")
        if git:
            candidates.append(Path(git).parent.parent / "bin" / "bash.exe")
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            root = os.environ.get(variable)
            if root:
                base = Path(root) / "Programs" if variable == "LOCALAPPDATA" else Path(root)
                candidates.append(base / "Git" / "bin" / "bash.exe")

    executable = shutil.which("bash")
    if executable:
        candidate = Path(executable)
        windows_root = Path(os.environ.get("SystemRoot", "C:/Windows"))
        if sys.platform != "win32" or not candidate.is_relative_to(windows_root):
            candidates.append(candidate)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "Bash was not found. Install Bash (Git for Windows on Windows), "
        "or set TOOLBOX_BASH to the full path of the Bash executable."
    )


def spawn_bash(executable: Path, cwd: Path, rows: int, columns: int):
    """Use ConPTY on Windows and a POSIX PTY on Linux/macOS."""
    environment = dict(os.environ, TERM="xterm-256color", CHERE_INVOKING="1")
    command = [str(executable), "--login", "-i"]
    if sys.platform == "win32":
        from winpty import PtyProcess
    else:
        from ptyprocess import PtyProcessUnicode as PtyProcess
    return PtyProcess.spawn(
        command, cwd=str(cwd), env=environment, dimensions=(rows, columns)
    )


class BashSession:
    """Own all PTY I/O in one worker; the UI only queues input and resizing."""

    def __init__(self, cwd: Path, rows: int, columns: int) -> None:
        self.cwd = cwd
        self.rows = max(1, rows)
        self.columns = max(1, columns)
        self._operations: Queue[tuple[str, object]] = Queue()
        self._stop = Event()
        self.finished = Event()

    def write(self, text: str) -> None:
        # Small writes let the worker drain echoed output during large pastes.
        for offset in range(0, len(text), 256):
            self._operations.put(("write", text[offset:offset + 256]))

    def resize(self, rows: int, columns: int) -> None:
        self._operations.put(("resize", (max(1, rows), max(1, columns))))

    def stop(self) -> None:
        self._stop.set()

    def run(
        self, on_started: Callable[[Path], None], on_output: Callable[[str], None]
    ) -> None:
        """Stream output until Bash exits or the owner requests shutdown."""
        process = None
        try:
            if self._stop.is_set():
                return
            executable = find_bash()
            process = spawn_bash(executable, self.cwd, self.rows, self.columns)
            on_started(executable)
            while not self._stop.is_set():
                self._apply_operations(process)
                reader = process.fileobj if sys.platform == "win32" else process.fd
                ready, _, _ = select.select([reader], [], [], 0.05)
                if ready:
                    on_output(process.read(65536))
                elif not self._is_alive(process):
                    break
        except EOFError:
            pass  # EOF is the normal way an interactive shell ends.
        finally:
            try:
                if process is not None:
                    self._close_process(process)
            finally:
                self.finished.set()

    def _apply_operations(self, process) -> None:
        # Bound each batch so a large paste cannot starve output or shutdown.
        for _ in range(4):
            try:
                operation, value = self._operations.get_nowait()
            except Empty:
                return
            if operation == "resize":
                process.setwinsize(*value)
            else:
                process.write(value)

    @staticmethod
    def _is_alive(process) -> bool:
        # pywinpty.isalive() changes `closed`, which would skip socket cleanup.
        return process.pty.isalive() if sys.platform == "win32" else process.isalive()

    @classmethod
    def _close_process(cls, process) -> None:
        try:
            if sys.platform == "win32" and cls._is_alive(process):
                result = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5,
                )
                if result.returncode and cls._is_alive(process):
                    raise OSError("Could not stop the Bash process tree.")
        finally:
            process.close(force=True)
