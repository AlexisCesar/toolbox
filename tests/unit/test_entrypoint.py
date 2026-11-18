import sys
import tomllib
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import main


ROOT = Path(__file__).resolve().parents[2]


def test_project_registers_toolbox_console_command() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    scripts = project["project"]["scripts"]
    assert scripts["toolbox"] == "main:main"
    assert scripts["toolboxtui"] == "main:main"


def test_main_entrypoint_runs_the_tui(monkeypatch) -> None:
    app = MagicMock()
    tui_module = ModuleType("src.tui")
    tui_module.ToolboxTUI = MagicMock(return_value=app)
    monkeypatch.setitem(sys.modules, "src.tui", tui_module)

    main.main()

    tui_module.ToolboxTUI.assert_called_once_with()
    app.run.assert_called_once_with()
