from pathlib import Path
from unittest.mock import MagicMock

from src.views import my_projects as my_projects_module
from src.utils.project_editor_dialog import EditorOption, ProjectEditorDialog
from src.views.my_projects import (
    MyProjects,
    ProjectSnapshot,
    find_installed_editors,
    find_vscode_executable,
    load_project_snapshot,
)


def test_projects_have_one_open_action_and_snapshot_includes_installed_editors(
    tmp_path: Path, monkeypatch
) -> None:
    solution_project = tmp_path / "with-solution"
    solution_project.mkdir()
    (solution_project / "example.sln").touch()
    folder_project = tmp_path / "without-solution"
    folder_project.mkdir()

    monkeypatch.setattr(
        my_projects_module,
        "find_installed_editors",
        lambda: (
            EditorOption("visual-studio", "Visual Studio", "devenv.exe"),
            EditorOption("vscode", "Visual Studio Code", "code"),
            EditorOption("rider", "JetBrains Rider", "rider64.exe"),
        ),
    )
    snapshot = load_project_snapshot(tmp_path)

    assert [row[3] for row in snapshot.rows] == [
        "▶ Open",
        "▶ Open",
    ]
    assert [row[0] for row in snapshot.rows] == [
        "with-solution",
        "without-solution",
    ]
    assert [editor.name for editor in snapshot.editors] == [
        "Visual Studio",
        "Visual Studio Code",
        "JetBrains Rider",
    ]


def test_open_action_remains_single_when_no_editors_are_detected(
    tmp_path: Path, monkeypatch
) -> None:
    solution_project = tmp_path / "with-solution"
    solution_project.mkdir()
    (solution_project / "example.sln").touch()
    folder_project = tmp_path / "without-solution"
    folder_project.mkdir()

    monkeypatch.setattr(
        my_projects_module,
        "find_installed_editors",
        lambda: (),
    )
    snapshot = load_project_snapshot(tmp_path)

    assert [row[3] for row in snapshot.rows] == ["▶ Open", "▶ Open"]
    assert snapshot.editors == ()


def test_vscode_detection_supports_insiders_command(monkeypatch) -> None:
    monkeypatch.setattr(
        my_projects_module.shutil,
        "which",
        lambda command: "code-insiders" if command == "code-insiders" else None,
    )

    assert find_vscode_executable() == "code-insiders"


def test_installed_editors_includes_rider_found_on_path(monkeypatch) -> None:
    monkeypatch.setattr(my_projects_module, "find_vscode_executable", lambda: None)
    monkeypatch.setattr(my_projects_module, "find_visual_studio_executable", lambda: None)
    monkeypatch.setattr(
        my_projects_module,
        "_find_editor_executable",
        lambda editor_id, _commands: "rider" if editor_id == "rider" else None,
    )

    assert find_installed_editors() == (
        EditorOption("rider", "JetBrains Rider", "rider"),
    )


def test_installed_editors_detects_devin_desktop_launcher(monkeypatch) -> None:
    monkeypatch.setattr(my_projects_module, "find_vscode_executable", lambda: None)
    monkeypatch.setattr(my_projects_module, "find_visual_studio_executable", lambda: None)
    monkeypatch.setattr(
        my_projects_module,
        "_find_editor_executable",
        lambda editor_id, _commands: "windsurf" if editor_id == "devin" else None,
    )

    assert find_installed_editors() == (
        EditorOption("devin", "Devin Desktop", "windsurf"),
    )


def test_missing_projects_directory_returns_warning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(my_projects_module, "find_installed_editors", lambda: ())

    snapshot = load_project_snapshot(tmp_path / "missing")

    assert snapshot.rows == ()
    assert snapshot.editors == ()
    assert snapshot.warning == "Projects directory does not exist. Configure it in Settings."


def test_refresh_projects_schedules_a_textual_worker() -> None:
    projects = MyProjects(logger=MagicMock())
    projects.query_one = MagicMock()
    projects.run_worker = MagicMock()

    projects.refresh_projects()

    worker_coro = projects.run_worker.call_args.args[0]
    assert worker_coro.cr_code.co_name == "_load_projects"
    assert projects.run_worker.call_args.kwargs == {
        "name": "refresh-projects",
        "group": "my-projects-refresh",
        "exclusive": True,
    }
    worker_coro.close()


def test_applied_snapshot_updates_rows_and_table() -> None:
    projects = MyProjects(logger=MagicMock())
    table = MagicMock()
    projects.query_one = MagicMock(return_value=table)
    snapshot = ProjectSnapshot(
        rows=(("demo", "demo.sln", "🏗️ Visual Studio Solution", "▶ Open"),),
        editors=(
            EditorOption("vscode", "Visual Studio Code", "code"),
            EditorOption("visual-studio", "Visual Studio", "devenv.exe"),
        ),
        warning="non-fatal warning",
    )

    projects._apply_snapshot(snapshot)

    assert projects.rows == list(snapshot.rows)
    assert projects.editors == snapshot.editors
    table.add_row.assert_called_once_with(
        "\ndemo\n",
        "\ndemo.sln\n",
        "\n🏗️ Visual Studio Solution\n",
        "\n▶ Open\n",
        height=3,
    )
    projects.logger.warn.assert_called_once_with("non-fatal warning")


def test_project_editor_dialog_dismisses_with_a_valid_selection() -> None:
    dialog = ProjectEditorDialog(
        (EditorOption("rider", "JetBrains Rider", "rider64.exe"),),
        Path("example.sln"),
    )
    select = MagicMock(value="rider")
    dialog.query_one = MagicMock(return_value=select)
    dialog.dismiss = MagicMock()

    dialog.open_selection()

    dialog.dismiss.assert_called_once_with("rider")


def test_solution_aware_editors_open_solution_and_other_editors_open_folder(
    tmp_path: Path,
) -> None:
    folder_path = tmp_path / "demo"
    solution_path = folder_path / "demo.sln"
    projects = MyProjects(logger=MagicMock())
    projects.editors = (
        EditorOption("visual-studio", "Visual Studio", "devenv.exe"),
        EditorOption("rider", "JetBrains Rider", "rider64.exe"),
        EditorOption("vscode", "Visual Studio Code", "code"),
    )
    projects._open_with = MagicMock()

    projects.open_project_with_editor("visual-studio", folder_path, solution_path)
    projects.open_project_with_editor("rider", folder_path, solution_path)
    projects.open_project_with_editor("vscode", folder_path, solution_path)

    assert [call.args[1] for call in projects._open_with.call_args_list] == [
        solution_path,
        solution_path,
        folder_path,
    ]


def test_open_with_logs_and_launches_application(tmp_path: Path, monkeypatch) -> None:
    projects = MyProjects(logger=MagicMock())
    popen = MagicMock()
    monkeypatch.setattr(my_projects_module.subprocess, "Popen", popen)
    path = tmp_path / "example.sln"
    projects._open_with("devenv.exe", path, "Visual Studio")

    popen.assert_called_once_with(["devenv.exe", str(path)])
    projects.logger.info.assert_called_once()


def test_open_with_logs_launch_error(tmp_path: Path, monkeypatch) -> None:
    projects = MyProjects(logger=MagicMock())

    def fail_to_open(_args):
        raise OSError("application unavailable")

    monkeypatch.setattr(my_projects_module.subprocess, "Popen", fail_to_open)
    path = tmp_path / "example.sln"
    projects._open_with("devenv.exe", path, "Visual Studio")

    projects.logger.error.assert_called_once()
