import asyncio
from pathlib import Path
from threading import Event

import pytest
from textual import events
from textual.widgets import Button, ContentSwitcher, Static

from src.tui import ToolboxTUI
from src.utils import bash_session
from src.utils.bash_session import BashSession, find_bash
from src.utils.bash_terminal import BashTerminal
from src.views.bash import Bash


async def wait_until(predicate, timeout: float = 10) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, "Bash did not respond in time"
        await asyncio.sleep(0.02)


class FakeSession:
    def __init__(self, cwd: Path, rows: int, columns: int) -> None:
        self.finished = Event()
        self.stopped = Event()
        self.writes: list[str] = []
        self.sizes: list[tuple[int, int]] = []

    def run(self, on_started, on_output) -> None:
        try:
            on_started(Path("fake-bash"))
            on_output("ready $ ")
            self.stopped.wait(15)
        finally:
            self.finished.set()

    def write(self, text: str) -> None:
        self.writes.append(text)

    def resize(self, rows: int, columns: int) -> None:
        self.sizes.append((rows, columns))

    def stop(self) -> None:
        self.stopped.set()


def test_bash_navigation_input_restart_and_shutdown(monkeypatch) -> None:
    monkeypatch.setattr("src.views.bash.BashSession", FakeSession)

    async def workflow() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            bash = app.query_one(Bash)
            assert bash.session is None
            await pilot.press("b")
            await pilot.pause()
            await wait_until(lambda: "Running:" in str(app.query_one("#bash-status", Static).content))
            terminal = app.query_one(BashTerminal)
            assert terminal.has_focus
            first_session = bash.session
            switcher = app.query_one(ContentSwitcher)
            await pilot.press("q", "h", "s", "b", "tab", "up", "ctrl+c")
            assert switcher.current == "bash-view"
            assert first_session.writes == ["q", "h", "s", "b", "\t", "\x1b[A", "\x03"]
            await pilot.press("ctrl+g")
            assert app.query_one("#sidebar-list").has_focus
            await pilot.press("h")
            assert switcher.current == "home-view"
            assert not first_session.stopped.is_set()
            await pilot.press("b")
            await pilot.pause()
            assert bash.session is first_session
            assert terminal.has_focus
            await pilot.resize_terminal(100, 35)
            await pilot.pause()
            assert first_session.sizes[-1] == (
                terminal.content_size.height, terminal.content_size.width
            )
            assert terminal.content_size.height >= 3
            assert terminal.region.right <= app.query_one("#main-panel").region.right
            await pilot.click("#bash-stop")
            await wait_until(lambda: bash.session is None)
            assert first_session.finished.is_set()
            assert not app.query_one("#bash-start", Button).disabled
            await pilot.press("ctrl+g", "h", "b")
            await pilot.pause()
            assert bash.session is None
            await pilot.click("#bash-start")
            await pilot.pause()
            second_session = bash.session
            assert second_session is not first_session
        assert second_session.stopped.is_set()
        assert second_session.finished.is_set()

    asyncio.run(workflow())


@pytest.mark.parametrize("size", [(80, 24), (100, 35)])
def test_bash_fits_the_main_panel_at_typical_terminal_sizes(monkeypatch, size) -> None:
    monkeypatch.setattr("src.views.bash.BashSession", FakeSession)

    async def workflow() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=size) as pilot:
            await pilot.press("b")
            await pilot.pause()
            terminal = app.query_one(BashTerminal)
            panel = app.query_one(ContentSwitcher)
            assert terminal.content_size.height >= 3
            assert terminal.region.bottom <= panel.content_region.bottom

    asyncio.run(workflow())


def test_bash_startup_error_is_visible_and_can_be_retried(monkeypatch) -> None:
    class UnavailableSession(FakeSession):
        def run(self, on_started, on_output) -> None:
            self.finished.set()
            raise FileNotFoundError("Bash was not found. Install Bash.")

    monkeypatch.setattr("src.views.bash.BashSession", UnavailableSession)

    async def workflow() -> None:
        app = ToolboxTUI()
        async with app.run_test() as pilot:
            await pilot.press("b")
            await pilot.pause()
            await wait_until(lambda: app.query_one(Bash).session is None)
            assert "Install Bash" in str(app.query_one("#bash-status", Static).content)
            assert not app.query_one("#bash-start", Button).disabled
            assert app.query_one("#bash-stop", Button).disabled
            assert "Bash session failed" in "".join(
                line.text for line in app.query_one("#log").lines
            )

    asyncio.run(workflow())


def test_real_bash_preserves_state_handles_input_interrupt_and_exit(tmp_path, monkeypatch) -> None:
    try:
        executable = find_bash()
    except FileNotFoundError as error:
        pytest.skip(str(error))
    monkeypatch.setenv("TOOLBOX_BASH", str(executable))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HISTFILE", "")
    processes = []
    original_spawn = bash_session.spawn_bash

    def record_spawn(*args):
        process = original_spawn(*args)
        processes.append(process)
        return process

    monkeypatch.setattr(bash_session, "spawn_bash", record_spawn)

    async def workflow() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.press("b")
            terminal = app.query_one(BashTerminal)
            bash = app.query_one(Bash)
            await wait_until(lambda: "Running:" in str(app.query_one("#bash-status", Static).content))
            session = bash.session

            def has_line(text: str) -> bool:
                return any(line.strip() == text for line in terminal.terminal_screen.display)

            async def command(text: str) -> None:
                terminal.post_message(events.Paste(text))
                await pilot.press("enter")

            await command("export TOOLBOX_VALUE=persistent_value; cd /; printf '\\nSETUP_DONE\\n'")
            await wait_until(lambda: has_line("SETUP_DONE"))
            await command("printf '\\nVALUE:%s\\nDIR:%s\\n' \"$TOOLBOX_VALUE\" \"$PWD\"")
            await wait_until(lambda: has_line("VALUE:persistent_value") and has_line("DIR:/"))
            await command("read -r answer; printf '\\nREPLY:%s\\n' \"$answer\"")
            await command("interactive_reply")
            await wait_until(lambda: has_line("REPLY:interactive_reply"))
            await command("sleep 30")
            await asyncio.sleep(0.3)
            await pilot.press("ctrl+c")
            await command("printf '\\nINTERRUPTED_OK\\n'")
            await wait_until(lambda: has_line("INTERRUPTED_OK"))
            assert bash.session is session
            await command("exit")
            await wait_until(lambda: bash.session is None)
            assert session.finished.is_set()
            assert not BashSession._is_alive(processes[0])
            await pilot.click("#bash-start")
            await wait_until(lambda: len(processes) == 2)
            await command("sleep 30")
            await asyncio.sleep(0.3)
            await pilot.click("#bash-stop")
            await wait_until(lambda: bash.session is None)
            assert not BashSession._is_alive(processes[1])
            await pilot.click("#bash-start")
            await wait_until(lambda: len(processes) == 3)
            await command("sleep 30")
            await asyncio.sleep(0.3)
        assert not BashSession._is_alive(processes[2])

    asyncio.run(workflow())
