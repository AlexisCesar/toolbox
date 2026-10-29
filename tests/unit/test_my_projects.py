from pathlib import Path
from unittest.mock import MagicMock

from src.views import my_projects as my_projects_module
from src.views.my_projects import (
    MyProjects,
    ProjectSnapshot,
    find_vscode_executable,
    load_project_snapshot,
)


def test_solution_projects_offer_both_editors_and_folders_offer_vscode_only(
    tmp_path: Path, monkeypatch
) -> None:
    solution_project = tmp_path / "with-solution"
    solution_project.mkdir()
    (solution_project / "example.sln").touch()
    folder_project = tmp_path / "without-solution"
    folder_project.mkdir()

    monkeypatch.setattr(my_projects_module, "find_vscode_executable", lambda: "code")
    monkeypatch.setattr(
        my_projects_module,
        "find_visual_studio_executable",
        lambda: "devenv.exe",
    )
    snapshot = load_project_snapshot(tmp_path)

    assert [row[3] for row in snapshot.rows] == [
        "▶ Open with Visual Studio",
        "▶ Open in VS Code",
        "▶ Open in VS Code",
    ]
    assert [row[0] for row in snapshot.rows] == [
        "with-solution",
        "with-solution",
        "without-solution",
    ]
    assert snapshot.vscode_executable == "code"
    assert snapshot.visual_studio_executable == "devenv.exe"


def test_missing_editors_are_shown_instead_of_open_actions(
    tmp_path: Path, monkeypatch
) -> None:
    solution_project = tmp_path / "with-solution"
    solution_project.mkdir()
    (solution_project / "example.sln").touch()
    folder_project = tmp_path / "without-solution"
    folder_project.mkdir()

    monkeypatch.setattr(my_projects_module, "find_vscode_executable", lambda: None)
    monkeypatch.setattr(
        my_projects_module,
        "find_visual_studio_executable",
        lambda: None,
    )
    snapshot = load_project_snapshot(tmp_path)

    assert [row[3] for row in snapshot.rows] == [
        "Visual Studio not found",
        "VSCode not found",
        "VSCode not found",
    ]


def test_vscode_detection_supports_insiders_command(monkeypatch) -> None:
    monkeypatch.setattr(
        my_projects_module.shutil,
        "which",
        lambda command: "code-insiders" if command == "code-insiders" else None,
    )

    assert find_vscode_executable() == "code-insiders"


def test_missing_projects_directory_returns_warning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(my_projects_module, "find_vscode_executable", lambda: None)
    monkeypatch.setattr(my_projects_module, "find_visual_studio_executable", lambda: None)

    snapshot = load_project_snapshot(tmp_path / "missing")

    assert snapshot.rows == ()
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
        rows=(("demo", "demo.sln", "🏗️ Visual Studio Solution", "▶ Open in VS Code"),),
        vscode_executable="code",
        visual_studio_executable="devenv.exe",
        warning="non-fatal warning",
    )

    projects._apply_snapshot(snapshot)

    assert projects.rows == list(snapshot.rows)
    assert projects.vscode_executable == "code"
    assert projects.visual_studio_executable == "devenv.exe"
    table.add_row.assert_called_once_with(
        "\ndemo\n",
        "\ndemo.sln\n",
        "\n🏗️ Visual Studio Solution\n",
        "\n▶ Open in VS Code\n",
        height=3,
    )
    projects.logger.warn.assert_called_once_with("non-fatal warning")


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
