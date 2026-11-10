import asyncio
import json

from textual.widgets import Button, DataTable, Input, Label, ListView, Static

from src.tui import ToolboxTUI
from src.utils.addon_manager import ADDON_MANIFEST, AddonManager, AddonViewState
from src.utils.confirm_dialog import ConfirmDialog
from src.views.bash import Bash


def test_sidebar_opens_addon_tab_and_shows_invalid_install_for_removal(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    manager = AddonManager(tmp_path / "addons")
    (manager.addons_dir / "broken").mkdir(parents=True)
    monkeypatch.setattr("src.tui.AddonManager", lambda: manager)
    app = ToolboxTUI()

    async def check_addon_navigation() -> None:
        async with app.run_test(size=(140, 45)) as pilot:
            sidebar = app.query_one("#sidebar-list", ListView)
            assert len(sidebar.children) == 15
            assert "Unavailable Addon (broken)" in str(
                sidebar.children[12].query_one(Label).content
            )

            app.action_select_view(12)
            await pilot.pause()

            assert app.query_one("#main-content-switcher").current == "addon-view"
            status = app.query_one("#addon-view-status", Static)
            assert "toolbox-addon.json" in str(status.content)

    asyncio.run(check_addon_navigation())


def test_install_and_remove_addon_refreshes_sidebar(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    manager = AddonManager(tmp_path / "addons")

    def fake_install(repository_url: str):
        assert repository_url == "https://example.test/pomodoro.git"
        addon_path = manager.addons_dir / "pomodoro"
        addon_path.mkdir(parents=True)
        (addon_path / ADDON_MANIFEST).write_text(
            json.dumps(
                {
                    "api_version": 1,
                    "id": "pomodoro",
                    "name": "Pomodoro",
                    "version": "1.0.0",
                    "icon": "⏱️",
                    "command": ["python", "addon.py"],
                }
            ),
            encoding="utf-8",
        )
        return manager.list_installed()[0]

    monkeypatch.setattr(manager, "install", fake_install)
    monkeypatch.setattr("src.tui.AddonManager", lambda: manager)
    app = ToolboxTUI()

    async def check_install_and_remove() -> None:
        async with app.run_test(size=(140, 45)) as pilot:
            app.action_select_view(11)
            await pilot.pause()
            app.query_one("#addons-repository-url", Input).value = (
                "https://example.test/pomodoro.git"
            )
            await pilot.click("#addons-install")
            await pilot.pause(0.3)

            assert "Installed Pomodoro" in str(app.query_one("#addons-status", Static).content)
            sidebar = app.query_one("#sidebar-list", ListView)
            assert len(sidebar.children) == 15
            assert "Pomodoro" in str(sidebar.children[12].query_one(Label).content)

            table = app.query_one("#addons-table", DataTable)
            table.focus()
            table.move_cursor(row=0, column=0)
            await pilot.pause()
            remove_button = app.query_one("#addons-remove", Button)
            assert not remove_button.disabled
            await pilot.click("#addons-remove")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmDialog)
            await pilot.click("#dialog-confirm-yes")
            await pilot.pause(0.3)

            assert len(sidebar.children) == 14
            assert manager.list_installed() == []

    asyncio.run(check_install_and_remove())


def test_addon_refresh_runs_while_tab_is_open_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    manager = AddonManager(tmp_path / "addons")
    addon_path = manager.addons_dir / "monitor"
    addon_path.mkdir(parents=True)
    (addon_path / ADDON_MANIFEST).write_text(
        json.dumps(
            {
                "api_version": 1,
                "id": "monitor",
                "name": "System Monitor",
                "version": "1.0.0",
                "command": ["python", "addon.py"],
                "refresh_interval_seconds": 1,
            }
        ),
        encoding="utf-8",
    )
    requests: list[str] = []

    def fake_request(addon_id: str, method: str, *, state=None, action=None):
        requests.append(method)
        return AddonViewState("System Monitor", "Updated", state or {}, ())

    monkeypatch.setattr(manager, "request", fake_request)
    monkeypatch.setattr("src.tui.AddonManager", lambda: manager)
    app = ToolboxTUI()

    async def check_refresh_lifecycle() -> None:
        async with app.run_test(size=(140, 45)) as pilot:
            app.action_select_view(12)
            await pilot.pause(1.2)
            assert requests[0] == "view"
            assert "refresh" in requests

            app.action_select_view(11)
            refresh_count = requests.count("refresh")
            await pilot.pause(1.2)
            assert requests.count("refresh") == refresh_count

    asyncio.run(check_refresh_lifecycle())
