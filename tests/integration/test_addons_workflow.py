import asyncio
import json

from textual.coordinate import Coordinate
from textual.widgets import Button, DataTable, Input, Label, ListView, Static

from src.tui import ToolboxTUI
from src.utils.addon_manager import (
    ADDON_MANIFEST,
    AddonAction,
    AddonManager,
    AddonNotification,
    AddonViewState,
)
from src.utils.confirm_dialog import ConfirmDialog
from src.utils.recommended_addons import (
    RecommendedAddon,
    RecommendedAddonsResult,
)
from src.utils.recommended_addons_dialog import RecommendedAddonsDialog
from src.views.addon_view import AddonView
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
            assert "Updated" in str(app.query_one("#addon-view-body", Static).content)

            app.action_select_view(11)
            refresh_count = requests.count("refresh")
            await pilot.pause(1.2)
            assert requests.count("refresh") == refresh_count

    asyncio.run(check_refresh_lifecycle())


def test_structured_addon_layout_renders_widgets_actions_and_toasts(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    manager = AddonManager(tmp_path / "addons")
    addon_path = manager.addons_dir / "dashboard"
    addon_path.mkdir(parents=True)
    (addon_path / ADDON_MANIFEST).write_text(
        json.dumps(
            {
                "api_version": 1,
                "id": "dashboard",
                "name": "Dashboard",
                "version": "1.0.0",
                "command": ["python", "addon.py"],
            }
        ),
        encoding="utf-8",
    )
    response = AddonViewState(
        "Dashboard",
        "",
        None,
        (AddonAction("refresh", "Refresh"),),
        layout=(
            {
                "type": "row",
                "children": (
                    {
                        "type": "panel",
                        "title": "System",
                        "children": (
                            {"type": "text", "content": "Ready", "color": "green"},
                            {"type": "button", "action": "refresh", "label": "Refresh here"},
                        ),
                    },
                    {
                        "type": "panel",
                        "title": "Tools",
                        "children": (
                            {
                                "type": "table",
                                "columns": ("Tool", "Version"),
                                "rows": (("Python", "3.12"),),
                            },
                        ),
                    },
                ),
            },
            {"type": "button", "action": "refresh", "label": "Refresh now"},
            {"type": "button", "action": "refresh", "label": "Refresh again"},
        ),
        notifications=(
            AddonNotification("Dashboard", "Loaded successfully.", "information", 3),
        ),
    )
    requests: list[str] = []

    def fake_request(addon_id: str, method: str, *, state=None, action=None):
        requests.append(method)
        if method == "action":
            return AddonViewState(
                response.title,
                response.body,
                response.state,
                response.actions,
                response.layout,
            )
        return response

    monkeypatch.setattr(manager, "request", fake_request)
    monkeypatch.setattr("src.tui.AddonManager", lambda: manager)
    app = ToolboxTUI()
    notifications: list[tuple[str, dict[str, object]]] = []

    def capture_notification(_view, message, **kwargs) -> None:
        notifications.append((message, kwargs))

    monkeypatch.setattr(
        AddonView,
        "notify",
        capture_notification,
    )

    async def check_structured_addon() -> None:
        async with app.run_test(size=(140, 45)) as pilot:
            app.action_select_view(12)
            await pilot.pause(0.2)

            table = app.query_one("#addon-layout-table-1", DataTable)
            assert table.row_count == 1
            assert str(table.get_cell_at(Coordinate(0, 0))) == "Python"
            assert len(app.query(".addon-layout-panel")) == 2
            layout_buttons = list(app.query("#addon-view-layout Button"))
            assert len(layout_buttons) == 3
            assert len({button.id for button in layout_buttons}) == 3
            assert app.query_one("#addon-view-body", Static).display is False
            for _ in range(10):
                if notifications:
                    break
                await pilot.pause(0.05)
            assert len(notifications) == 1
            assert notifications[0][0] == "Loaded successfully."
            assert notifications[0][1]["severity"] == "information"
            assert notifications[0][1]["markup"] is False

            await pilot.click("#addon-action-0")
            await pilot.pause(0.2)
            assert requests == ["view", "action"]

    asyncio.run(check_structured_addon())


def test_recommended_addons_dialog_lists_entries_and_copies_repository(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    manager = AddonManager(tmp_path / "addons")
    monkeypatch.setattr("src.tui.AddonManager", lambda: manager)
    addon = RecommendedAddon(
        "Environment Report",
        "https://github.com/AlexisCesar/toolbox-environment-report",
        "General information about the system.",
        "Development",
    )
    monkeypatch.setattr(
        "src.utils.recommended_addons.RecommendedAddonsCatalog.load",
        lambda _catalog: RecommendedAddonsResult((addon,), from_cache=True),
    )
    copied: list[str] = []
    monkeypatch.setattr(
        "src.utils.recommended_addons_dialog.pyperclip.copy",
        copied.append,
    )
    app = ToolboxTUI()

    async def check_recommendations() -> None:
        async with app.run_test(size=(110, 40)) as pilot:
            app.action_select_view(11)
            await pilot.pause()
            await pilot.click("#addons-recommended")
            await pilot.pause(0.2)

            assert isinstance(app.screen, RecommendedAddonsDialog)
            dialog = app.screen
            card = dialog.query_one("#recommended-addon-card-0")
            assert "Environment Report" in str(card.query_one(".recommended-addon-name").content)
            assert "Development" in str(card.query_one(".recommended-addon-category").content)
            assert "General information" in str(
                card.query_one(".recommended-addon-description").content
            )
            assert "github.com/AlexisCesar/toolbox-environment-report" in str(
                card.query_one(".recommended-addon-repository").render()
            )

            await pilot.click("#recommended-addon-copy-0")
            await pilot.pause()
            assert copied == [addon.repository]
            assert "Copied the Environment Report repository URL to the clipboard." in str(
                dialog.query_one("#recommended-addons-status", Static).content
            )

            await pilot.click("#recommended-addons-close")
            await pilot.pause()
            assert not isinstance(app.screen, RecommendedAddonsDialog)

    asyncio.run(check_recommendations())
