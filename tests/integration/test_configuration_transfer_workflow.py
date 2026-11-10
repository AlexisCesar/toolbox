import asyncio
import json
from pathlib import Path

from textual.widgets import Checkbox, Input

from src.tui import ToolboxTUI
from src.utils.config import Config
from src.utils.config_transfer_dialog import ConfigTransferDialog
from src.views.bash import Bash
from src.views import settings as settings_module


DEFAULT_CONFIG = """\
[paths]
scripts = "./scripts"
notes = "./notes"
projects = "./projects"

[ui]
theme = "textual-dark"

[scripts]
timeout = 3
depth = 1

[[logs]]
name = "Shared logs"
location = "./shared-logs"

[[services]]
name = "Shared check"
type = "http"
target = "https://example.com/health"
interval = 10
"""


def test_settings_can_export_and_import_selected_configuration_groups(
    tmp_path: Path,
    monkeypatch,
) -> None:
    defaults = tmp_path / "config.toml"
    defaults.write_text(DEFAULT_CONFIG, encoding="utf-8")
    configuration = Config(defaults, tmp_path / "config.override.toml")
    monkeypatch.setattr(Bash, "start_session", lambda self: None)
    monkeypatch.setattr(settings_module, "config", configuration)
    export_path = tmp_path / "shared-settings.json"

    async def run_workflow() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=(140, 45)) as pilot:
            app.action_select_settings()
            await pilot.pause()
            app.query_one("#settings-config-export")
            app.query_one("#settings-config-import")
            assert await pilot.click("#settings-config-export")
            await pilot.pause()
            assert isinstance(app.screen, ConfigTransferDialog)
            app.screen.query_one("#config-transfer-path", Input).value = str(export_path)
            for section in ("paths", "scripts", "ui", "calendar", "gamification"):
                app.screen.query_one(f"#config-transfer-{section}", Checkbox).value = False
            await pilot.click("#config-transfer-submit")
            await pilot.pause()

            payload = json.loads(export_path.read_text(encoding="utf-8"))
            assert set(payload["sections"]) == {"logs", "services"}
            assert payload["sections"]["logs"] == configuration.logs

            configuration.update_logs([])
            configuration.update_services([])
            assert await pilot.click("#settings-config-import")
            await pilot.pause()
            assert isinstance(app.screen, ConfigTransferDialog)
            app.screen.query_one("#config-transfer-path", Input).value = str(export_path)
            await pilot.click("#config-transfer-load")
            await pilot.pause()
            assert not app.screen.query_one("#config-transfer-logs", Checkbox).disabled
            assert not app.screen.query_one("#config-transfer-services", Checkbox).disabled
            app.screen.query_one("#config-transfer-services", Checkbox).value = False
            await pilot.click("#config-transfer-submit")
            await pilot.pause()

            assert configuration.logs == payload["sections"]["logs"]
            assert configuration.services == []

    asyncio.run(run_workflow())
