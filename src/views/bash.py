"""Embedded, persistent Bash view."""

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Label, Static

from src.utils.bash_session import BashSession
from src.utils.bash_terminal import BashTerminal
from src.utils.logger import Logger


class Bash(Static):
    def __init__(self, logger: Logger, **kwargs) -> None:
        super().__init__(**kwargs)
        self.logger = logger
        self.session: BashSession | None = None
        self._opened = False
        self._session_error: str | None = None

    class SessionEvent(Message):
        def __init__(self, session: BashSession, kind: str, text: str = "") -> None:
            super().__init__()
            self.session = session
            self.kind = kind
            self.text = text

    def compose(self) -> ComposeResult:
        with Horizontal(id="bash-controls"):
            yield Label("Bash", id="bash-title")
            yield Button("New session", id="bash-start", variant="success")
            yield Button("Stop session", id="bash-stop", variant="error", disabled=True)
        yield Static(
            "Ctrl+C: interrupt · Tab: complete · ↑/↓: history · "
            "Shift+PgUp/PgDn: scroll · Ctrl+G: sidebar",
            id="bash-subtitle",
        )
        yield Static("Open Bash to start a session.", id="bash-status", markup=False)
        yield BashTerminal(id="bash-terminal")

    def on_show(self) -> None:
        if not self._opened:
            self._opened = True
            self.start_session()
        else:
            self.call_after_refresh(self.query_one(BashTerminal).focus)

    def start_session(self) -> None:
        if self.session is not None:
            return
        self._session_error = None
        terminal = self.query_one(BashTerminal)
        terminal.reset_terminal()
        session = BashSession(
            Path.cwd(), terminal.terminal_screen.lines, terminal.terminal_screen.columns
        )
        self.session = session
        self.query_one("#bash-start", Button).disabled = True
        self.query_one("#bash-stop", Button).disabled = False
        self.query_one("#bash-status", Static).update("Starting Bash…")
        self.run_worker(
            lambda: self._run_session(session), thread=True,
            name="bash-session", group="bash-session", exit_on_error=False,
        )
        self.call_after_refresh(terminal.focus)

    def _run_session(self, session: BashSession) -> None:
        try:
            session.run(
                lambda path: self.post_message(self.SessionEvent(session, "started", str(path))),
                lambda text: self.post_message(self.SessionEvent(session, "output", text)),
            )
        except Exception as error:
            self.post_message(self.SessionEvent(session, "error", str(error)))
        finally:
            self.post_message(self.SessionEvent(session, "stopped"))

    def on_bash_session_event(self, event: SessionEvent) -> None:
        if event.session is not self.session:
            return
        status = self.query_one("#bash-status", Static)
        if event.kind == "started":
            status.update(f"Running: {event.text}")
            self.logger.info(f"Bash session started: {event.text}")
        elif event.kind == "output":
            self.query_one(BashTerminal).feed(event.text)
        elif event.kind == "error":
            self._session_error = event.text
            status.update(event.text)
            self.logger.error(f"Bash session failed: {event.text}")
        elif event.kind == "stopped":
            # Keep startup and I/O errors visible after the worker finishes.
            if self._session_error is None:
                status.update("Session ended. Select New session to start again.")
            self.session = None
            self.query_one("#bash-start", Button).disabled = False
            self.query_one("#bash-stop", Button).disabled = True
            self.logger.info("Bash session ended.")

    def on_bash_terminal_input(self, event: BashTerminal.Input) -> None:
        if self.session is not None and event.text:
            self.session.write(event.text)

    def on_bash_terminal_resized(self, event: BashTerminal.Resized) -> None:
        if self.session is not None:
            self.session.resize(event.rows, event.columns)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bash-start":
            self.start_session()
        elif event.button.id == "bash-stop" and self.session is not None:
            self.query_one("#bash-status", Static).update("Stopping Bash…")
            event.button.disabled = True
            self.session.stop()

    async def on_unmount(self) -> None:
        if self.session is not None:
            self.session.stop()
            finished = await asyncio.to_thread(self.session.finished.wait, 6)
            if not finished:
                self.logger.warn("Timed out waiting for the Bash session to stop.")
