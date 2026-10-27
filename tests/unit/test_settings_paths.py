from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.utils.confirm_dialog import ConfirmResult
from src.views import settings as settings_module
from src.views.settings import Settings
from textual.app import App


@pytest.mark.parametrize(
    ("callback_name", "config_key"),
    [
        ("change_scripts_dir", "scripts"),
        ("change_notes_dir", "notes"),
        ("change_projects_dir", "projects"),
    ],
)
def test_directory_setting_normalizes_then_validates_and_persists(
    callback_name: str,
    config_key: str,
    tmp_path: Path,
    monkeypatch,
) -> None:
    selected_path = str(tmp_path / "selected folder")
    windows_style_path = selected_path.replace("/", "\\")
    normalized_path = selected_path.replace("\\", "/")
    settings = Settings(logger=MagicMock())
    settings.validate_directory = MagicMock(return_value=True)
    settings.update_fields = MagicMock()
    update = MagicMock()
    monkeypatch.setattr(settings_module.config, "update", update)

    getattr(settings, callback_name)(
        ConfirmResult(confirmed=True, parameters=windows_style_path)
    )

    settings.validate_directory.assert_called_once_with(normalized_path)
    update.assert_called_once_with("paths", config_key, normalized_path)
    settings.update_fields.assert_called_once_with()
    settings.logger.info.assert_any_call(
        f"Updating {config_key} path to \"{normalized_path}\"."
    )


@pytest.mark.parametrize(
    ("callback_name", "config_key"),
    [
        ("change_scripts_dir", "scripts"),
        ("change_notes_dir", "notes"),
        ("change_projects_dir", "projects"),
    ],
)
def test_invalid_directory_does_not_change_config(
    callback_name: str,
    config_key: str,
    monkeypatch,
) -> None:
    selected_path = r"C:\missing\folder"
    normalized_path = "C:/missing/folder"
    settings = Settings(logger=MagicMock())
    settings.validate_directory = MagicMock(return_value=False)
    update = MagicMock()
    monkeypatch.setattr(settings_module.config, "update", update)

    getattr(settings, callback_name)(
        ConfirmResult(confirmed=True, parameters=selected_path)
    )

    settings.validate_directory.assert_called_once_with(normalized_path)
    update.assert_not_called()
    settings.logger.error.assert_called_once_with(
        f'"{normalized_path}" is an invalid path.'
    )


@pytest.mark.parametrize(
    "callback_name",
    ["change_scripts_dir", "change_notes_dir", "change_projects_dir"],
)
@pytest.mark.parametrize(
    "result",
    [
        ConfirmResult(confirmed=False, parameters=r"C:\ignored"),
        ConfirmResult(confirmed=True, parameters=""),
    ],
)
def test_cancelled_or_empty_directory_selection_keeps_existing_path(
    callback_name: str,
    result: ConfirmResult,
    monkeypatch,
) -> None:
    settings = Settings(logger=MagicMock())
    settings.validate_directory = MagicMock(return_value=True)
    update = MagicMock()
    monkeypatch.setattr(settings_module.config, "update", update)

    getattr(settings, callback_name)(result)

    settings.validate_directory.assert_not_called()
    update.assert_not_called()


def test_path_change_button_opens_directory_input_dialog() -> None:
    settings = Settings(logger=MagicMock())
    app = App()
    app.push_screen = MagicMock()
    settings._parent = app
    event = MagicMock()
    event.button.id = "settings-directories-notes-change-button"

    settings.on_button_pressed(event)

    app.push_screen.assert_called_once()
    dialog = app.push_screen.call_args.args[0]
    assert dialog.message == "Change notes directory:"
    assert dialog.askParameters is True
    assert dialog.confirmButtonText == "Save"
    assert dialog.cancelButtonText == "Cancel"
    callback = app.push_screen.call_args.kwargs["callback"]
    callback(ConfirmResult(confirmed=False, parameters=""))
