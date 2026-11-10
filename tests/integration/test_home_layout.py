import asyncio

from textual.widgets import Label, Select, Static

from src.tui import ToolboxTUI
from src.views.bash import Bash
from src.version import APP_VERSION, CHANGELOG


def test_home_splits_guidance_and_update_log_and_shows_current_version(
    monkeypatch,
) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    monkeypatch.setattr("src.tui.check_for_update", lambda current_version: "0.4.0")
    app = ToolboxTUI()

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
            await pilot.pause(0.1)

            assert update_notice.display is True
            assert "New release v0.4.0 is available" in str(update_notice.content)
            assert "master branch" in str(update_notice.content)
            assert update_notice.region.y < version_select.region.y
            assert version_select.value == APP_VERSION
            assert f"Version {APP_VERSION} Log:" in str(changelog.content)
            assert f"v{APP_VERSION}" in str(app.query_one("#version", Label).content)

            pending_version = "0.4.0"
            assert pending_version in CHANGELOG
            version_select.value = pending_version
            await pilot.pause()

            assert f"Version {pending_version} Log:" in str(changelog.content)
            assert CHANGELOG[pending_version]["added"][0] in str(changelog.content)

    asyncio.run(check_home())
