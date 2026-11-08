import asyncio

from textual.widgets import Label, Static

from src.tui import ToolboxTUI
from src.views.bash import Bash
from src.version import APP_VERSION


def test_home_splits_guidance_and_update_log_and_shows_current_version(
    monkeypatch,
) -> None:
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    app = ToolboxTUI()

    async def check_home() -> None:
        async with app.run_test(size=(160, 45)):
            guidance = app.query_one("#home-guidance")
            update_log = app.query_one("#home-update-log")

            assert abs(guidance.region.width - update_log.region.width) <= 1
            assert guidance.region.x < update_log.region.x
            app.query_one("#home-changelog", Static)
            assert f"v{APP_VERSION}" in str(app.query_one("#version", Label).content)

    asyncio.run(check_home())
