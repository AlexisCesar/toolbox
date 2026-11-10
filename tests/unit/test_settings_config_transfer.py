from unittest.mock import MagicMock

import pytest
from textual.app import App

from src.utils.config_transfer_dialog import ConfigTransferDialog
from src.views.home import Home
from src.views.settings import Settings


@pytest.mark.parametrize(
    ("button_id", "operation"),
    [
        ("settings-config-export", "export"),
        ("settings-config-import", "import"),
    ],
)
def test_settings_transfer_button_opens_the_matching_dialog(
    button_id: str,
    operation: str,
) -> None:
    settings = Settings(logger=MagicMock())
    app = App()
    app.push_screen = MagicMock()
    settings._parent = app
    event = MagicMock()
    event.button.id = button_id

    settings.on_button_pressed(event)

    app.push_screen.assert_called_once()
    dialog = app.push_screen.call_args.args[0]
    assert isinstance(dialog, ConfigTransferDialog)
    assert dialog.operation == operation


def test_home_guidance_explains_how_to_transfer_settings() -> None:
    instructions = Home().instructions()

    assert "Settings → Configuration" in instructions
    assert "private subscription URL" in instructions
