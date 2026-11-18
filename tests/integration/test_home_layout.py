import asyncio
from pathlib import Path

from textual.widgets import Button, Label, Select, Static

from src.tui import ToolboxTUI
from src.views.bash import Bash
from src.version import APP_VERSION, CHANGELOG
from src.utils.update_manager import UpdatePlan


def test_home_splits_guidance_and_update_log_and_shows_current_version(
    monkeypatch,
) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    monkeypatch.setattr("src.tui.check_for_update", lambda current_version: "0.6.0")
    app = ToolboxTUI()
    update_steps: list[str] = []

    class SuccessfulUpdater:
        def prepare(self) -> UpdatePlan:
            update_steps.append("prepare")
            return UpdatePlan(Path.cwd(), "master")

        def fetch(self, plan: UpdatePlan) -> None:
            update_steps.append("fetch")

        def pull(self, plan: UpdatePlan) -> None:
            update_steps.append("pull")

        def sync(self, plan: UpdatePlan) -> None:
            update_steps.append("sync")

    monkeypatch.setattr("src.tui.ToolboxUpdater", SuccessfulUpdater)

    async def check_home() -> None:
        async with app.run_test(size=(160, 45)) as pilot:
            guidance = app.query_one("#home-guidance")
            update_log = app.query_one("#home-update-log")

            assert abs(guidance.region.width - 3 * update_log.region.width) <= 2
            assert guidance.region.width > update_log.region.width
            assert guidance.region.x < update_log.region.x
            version_select = app.query_one("#home-version-select", Select)
            changelog = app.query_one("#home-changelog", Static)
            update_notice = app.query_one("#home-update-notice", Static)
            update_button = app.query_one("#home-update", Button)
            await pilot.pause(0.1)

            assert update_notice.display is True
            assert "New release v0.6.0 is available" in str(update_notice.content)
            assert "button below" in str(update_notice.content)
            assert update_button.display is True
            assert update_notice.region.y < version_select.region.y
            assert version_select.value == APP_VERSION
            assert f"Version {APP_VERSION} Log:" in str(changelog.content)
            assert f"v{APP_VERSION}" in str(app.query_one("#version", Label).content)

            pending_version = "0.6.0"
            assert pending_version in CHANGELOG
            version_select.value = pending_version
            await pilot.pause()

            assert f"Version {pending_version} Log:" in str(changelog.content)
            assert CHANGELOG[pending_version]["added"][0] in str(changelog.content)

            await pilot.click("#home-update")
            await pilot.pause(0.2)
            assert app._update_in_progress is True
            update_dialog = app.screen
            assert "Update complete" in str(
                update_dialog.query_one("#toolbox-update-status", Static).content
            )
            assert update_steps == ["prepare", "fetch", "pull", "sync"]
            await pilot.click("#toolbox-update-action")
            await pilot.pause()
            assert app.is_running is False

    asyncio.run(check_home())
