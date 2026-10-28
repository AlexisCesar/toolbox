import asyncio
from pathlib import Path

from textual.widgets import Button, Input, ListItem, TextArea

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.log_config_dialog import LogConfigDialog
from src.utils.log_dialogs import LogFileDialog, LogFilesDialog


def test_log_folder_opens_supported_file_at_the_latest_line(
    tmp_path: Path,
    monkeypatch,
) -> None:
    log_folder = tmp_path / "application logs"
    log_folder.mkdir()
    (log_folder / "application.log").write_text("older entry\nlatest entry", encoding="utf-8")
    (log_folder / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nimage")
    monkeypatch.setitem(
        config._data,
        "logs",
        [{"name": "Application X v2", "location": str(log_folder)}],
    )

    async def run_workflow() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("l")
            await pilot.pause()
            await pilot.click("#logs-open-0")
            await pilot.pause()

            assert isinstance(app.screen, LogFilesDialog)
            assert len(app.screen.files) == 2
            file_list = app.screen.query_one("#log-files-list")
            assert [path.name for path in app.screen.files] == [
                "image.png",
                "application.log",
            ]
            assert app.screen.query_one("#log-files-open", Button).variant == "success"
            assert app.screen.query_one("#log-files-close", Button).variant == "primary"
            await pilot.click(ListItem, offset=(2, 1))
            await pilot.pause()
            assert isinstance(app.screen, LogFilesDialog)
            assert app.query_one("#main-content-switcher").current == "logs-view"
            file_list.index = 0
            await pilot.click("#log-files-open")
            await pilot.pause(0.1)
            assert isinstance(app.screen, LogFilesDialog)
            assert "appears to be binary" in str(
                app.screen.query_one("#log-files-status").content
            )

            file_list.index = 1
            await pilot.click("#log-files-open")
            await pilot.pause(0.1)

            assert isinstance(app.screen, LogFileDialog)
            assert app.screen.query_one("#log-file-close", Button).variant == "primary"
            viewer = app.screen.query_one("#log-file-content", TextArea)
            assert viewer.text == "older entry\nlatest entry"
            assert viewer.cursor_location == (1, len("latest entry"))
            await pilot.click("#log-file-close", offset=(1, 1))
            await pilot.pause()
            assert app.screen.id == "_default"
            assert app.query_one("#main-content-switcher").current == "logs-view"

    asyncio.run(run_workflow())


def test_settings_can_add_edit_and_remove_log_folders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_folder = tmp_path / "first"
    second_folder = tmp_path / "second"
    first_folder.mkdir()
    second_folder.mkdir()
    monkeypatch.setitem(config._data, "logs", [])
    monkeypatch.setattr(
        config,
        "update_logs",
        lambda entries: config._data.__setitem__("logs", entries),
    )

    async def run_workflow() -> None:
        app = ToolboxTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("e")
            await pilot.pause()

            add_button = app.query_one("#settings-logs-add")
            assert add_button.visible, add_button.region
            assert await pilot.click("#settings-logs-add", offset=(1, 1))
            await pilot.pause()
            assert isinstance(app.screen, LogConfigDialog)
            app.screen.query_one("#log-config-name", Input).value = "Initial name"
            app.screen.query_one("#log-config-location", Input).value = str(first_folder)
            await pilot.click("#log-config-save", offset=(1, 1))
            await pilot.pause()
            assert config.logs == [
                {"name": "Initial name", "location": str(first_folder).replace("\\", "/")}
            ]

            await pilot.click("#settings-logs-edit", offset=(1, 1))
            await pilot.pause()
            app.screen.query_one("#log-config-name", Input).value = "Updated name"
            app.screen.query_one("#log-config-location", Input).value = str(second_folder)
            await pilot.click("#log-config-save", offset=(1, 1))
            await pilot.pause()
            assert config.logs == [
                {"name": "Updated name", "location": str(second_folder).replace("\\", "/")}
            ]

            await pilot.click("#settings-logs-remove", offset=(1, 1))
            await pilot.pause()
            await pilot.click("#dialog-confirm-yes", offset=(1, 1))
            await pilot.pause()
            assert config.logs == []

    asyncio.run(run_workflow())
