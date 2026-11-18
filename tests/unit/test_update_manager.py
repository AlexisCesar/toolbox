from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.utils.update_manager import ToolboxUpdater, ToolboxUpdateError, UpdatePlan


def command_result(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def make_installation(path: Path) -> Path:
    path.mkdir()
    for filename in ("main.py", "pyproject.toml", "uv.lock"):
        (path / filename).touch()
    return path


def preflight_results(
    root: Path,
    *,
    branch: str = "master",
    upstream: str | None = None,
    status: str = "",
) -> list[SimpleNamespace]:
    return [
        command_result(stdout=f"{root}\n"),
        command_result(stdout=f"{branch}\n"),
        command_result(stdout=f"{upstream or f'origin/{branch}'}\n"),
        command_result(stdout="https://github.com/AlexisCesar/toolbox.git\n"),
        command_result(stdout=status),
    ]


def test_update_runs_only_expected_fast_forward_commands_from_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_installation(tmp_path / "toolbox")
    monkeypatch.setattr(Path, "cwd", lambda: root)
    results = preflight_results(root, branch="develop") + [
        command_result(),  # fetch
        command_result(),  # clean check before pull
        command_result(),  # pull
        command_result(),  # uv sync
    ]

    with patch("src.utils.update_manager.subprocess.run", side_effect=results) as run:
        updater = ToolboxUpdater()
        plan = updater.prepare()
        updater.fetch(plan)
        updater.pull(plan)
        updater.sync(plan)

    assert plan == UpdatePlan(root, "develop")
    assert [call.args[0] for call in run.call_args_list] == [
        ["git", "rev-parse", "--show-toplevel"],
        ["git", "branch", "--show-current"],
        [
            "git",
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        ],
        ["git", "remote", "get-url", "origin"],
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        ["git", "fetch", "origin"],
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        ["git", "pull", "--ff-only", "origin", "develop"],
        ["uv", "sync"],
    ]
    assert all(call.kwargs["cwd"] == root for call in run.call_args_list)
    assert all("shell" not in call.kwargs for call in run.call_args_list)


def test_update_rejects_a_directory_inside_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_installation(tmp_path / "toolbox")
    nested = root / "src"
    nested.mkdir()
    monkeypatch.setattr(Path, "cwd", lambda: nested)

    with patch(
        "src.utils.update_manager.subprocess.run",
        return_value=command_result(stdout=f"{root}\n"),
    ):
        with pytest.raises(ToolboxUpdateError, match="root of its Git repository"):
            ToolboxUpdater().prepare()


def test_update_rejects_a_dirty_working_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_installation(tmp_path / "toolbox")
    monkeypatch.setattr(Path, "cwd", lambda: root)
    results = preflight_results(root, status=" M src/tui.py\n")

    with patch("src.utils.update_manager.subprocess.run", side_effect=results) as run:
        with pytest.raises(ToolboxUpdateError, match="local changes"):
            ToolboxUpdater().prepare()

    assert len(run.call_args_list) == 5


def test_update_rejects_an_upstream_that_does_not_match_the_current_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_installation(tmp_path / "toolbox")
    monkeypatch.setattr(Path, "cwd", lambda: root)
    results = preflight_results(root, branch="develop", upstream="origin/master")

    with patch("src.utils.update_manager.subprocess.run", side_effect=results):
        with pytest.raises(ToolboxUpdateError, match="origin/develop"):
            ToolboxUpdater().prepare()


def test_failed_pull_is_reported_as_potentially_changing_the_checkout(
    tmp_path: Path,
) -> None:
    root = make_installation(tmp_path / "toolbox")
    plan = UpdatePlan(root, "master")

    with patch(
        "src.utils.update_manager.subprocess.run",
        side_effect=[
            command_result(),
            command_result(stderr="fatal: Not possible to fast-forward, aborting.", returncode=1),
        ],
    ):
        with pytest.raises(ToolboxUpdateError) as caught:
            ToolboxUpdater().pull(plan)

    assert caught.value.stage == "pull"
    assert caught.value.checkout_may_have_changed is True
    assert "ff-only" not in str(caught.value)


def test_failed_uv_sync_does_not_attempt_repository_repair(tmp_path: Path) -> None:
    plan = UpdatePlan(make_installation(tmp_path / "toolbox"), "master")

    with patch(
        "src.utils.update_manager.subprocess.run",
        return_value=command_result(stderr="dependency resolution failed", returncode=1),
    ) as run:
        with pytest.raises(ToolboxUpdateError) as caught:
            ToolboxUpdater().sync(plan)

    assert caught.value.stage == "dependency sync"
    assert caught.value.checkout_may_have_changed is True
    assert [call.args[0] for call in run.call_args_list] == [["uv", "sync"]]
