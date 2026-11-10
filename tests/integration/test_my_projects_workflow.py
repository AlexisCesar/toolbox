import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from textual.coordinate import Coordinate
from textual.widgets import DataTable, Select

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.project_editor_dialog import EditorOption, ProjectEditorDialog
from src.views import my_projects as my_projects_module


def test_project_open_action_shows_installed_editor_choices(tmp_path: Path, monkeypatch) -> None:
    projects_dir = tmp_path / "projects"
    solution_dir = projects_dir / "demo"
    solution_dir.mkdir(parents=True)
    (solution_dir / "demo.sln").touch()
    monkeypatch.setitem(config._data["paths"], "projects", str(projects_dir))
    monkeypatch.setattr(
        my_projects_module,
        "find_installed_editors",
        lambda: (
            EditorOption("visual-studio", "Visual Studio", "devenv.exe"),
            EditorOption("vscode", "Visual Studio Code", "code"),
            EditorOption("rider", "JetBrains Rider", "rider64.exe"),
        ),
    )
    popen = MagicMock()
    monkeypatch.setattr(my_projects_module.subprocess, "Popen", popen)
    app = ToolboxTUI()

    async def check_workflow() -> None:
        async with app.run_test(size=(140, 45)) as pilot:
            app.action_select_view(9)
            table = app.query_one("#projects-datatable", DataTable)
            for _ in range(40):
                if table.row_count == 1:
                    break
                await pilot.pause(0.05)

            assert table.row_count == 1
            assert str(table.get_row_at(0)[3]).strip() == "▶ Open"
            coordinate = Coordinate(0, 3)
            table.post_message(
                DataTable.CellSelected(
                    table,
                    table.get_cell_at(coordinate),
                    coordinate,
                    table.coordinate_to_cell_key(coordinate),
                )
            )
            await pilot.pause()

            assert isinstance(app.screen, ProjectEditorDialog)
            dialog = app.screen
            assert [editor.name for editor in dialog.editors] == [
                "Visual Studio",
                "Visual Studio Code",
                "JetBrains Rider",
            ]
            for _ in range(40):
                if dialog.query_one(Select).value == "visual-studio":
                    break
                await pilot.pause(0.05)
            assert dialog.query_one(Select).value == "visual-studio"
            await pilot.click("#project-editor-open")
            await pilot.pause()

            popen.assert_called_once_with(["devenv.exe", str(solution_dir / "demo.sln")])

    asyncio.run(check_workflow())
