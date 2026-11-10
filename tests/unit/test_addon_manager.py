import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.utils.addon_manager import (
    ADDON_MANIFEST,
    AddonError,
    AddonManager,
    parse_addon_manifest,
    validate_repository_url,
)


def manifest(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "api_version": 1,
        "id": "pomodoro",
        "name": "Pomodoro",
        "version": "1.0.0",
        "icon": "⏱️",
        "command": ["python", "addon.py"],
    }
    value.update(changes)
    return value


def write_manifest(directory: Path, **changes: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ADDON_MANIFEST
    path.write_text(json.dumps(manifest(**changes)), encoding="utf-8")
    return path


def test_parse_addon_manifest_requires_version_and_safe_id() -> None:
    data = parse_addon_manifest(manifest())

    assert data.id == "pomodoro"
    assert data.name == "Pomodoro"
    assert data.icon == "⏱️"
    assert data.command == ("python", "addon.py")
    assert data.refresh_interval_seconds is None

    refreshed = parse_addon_manifest(manifest(refresh_interval_seconds=2))
    assert refreshed.refresh_interval_seconds == 2

    with pytest.raises(AddonError, match="API version"):
        parse_addon_manifest(manifest(api_version=2))
    with pytest.raises(AddonError, match="API version"):
        parse_addon_manifest(manifest(api_version=True))
    with pytest.raises(AddonError, match="Addon id"):
        parse_addon_manifest(manifest(id="../escape"))
    with pytest.raises(AddonError, match="command"):
        parse_addon_manifest(manifest(command=[]))
    with pytest.raises(AddonError, match="refresh interval"):
        parse_addon_manifest(manifest(refresh_interval_seconds=0))
    with pytest.raises(AddonError, match="refresh interval"):
        parse_addon_manifest(manifest(refresh_interval_seconds=True))


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/example/pomodoro.git",
        "ssh://git@github.com/example/pomodoro.git",
        "git@github.com:example/pomodoro.git",
    ],
)
def test_validate_repository_url_accepts_https_and_ssh(url: str) -> None:
    assert validate_repository_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "file:///tmp/addon",
        "http://github.com/example/addon.git",
        "https://user:token@github.com/example/addon.git",
        "https://github.com/example/addon.git?token=secret",
    ],
)
def test_validate_repository_url_rejects_unsafe_or_ambiguous_urls(url: str) -> None:
    with pytest.raises(AddonError):
        validate_repository_url(url)


def test_install_clones_validates_and_prevents_duplicate_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = AddonManager(tmp_path / "addons")

    def fake_git(command: list[str], **kwargs: object) -> SimpleNamespace:
        checkout = Path(command[-1])
        write_manifest(checkout)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_git)

    installed = manager.install("https://github.com/example/pomodoro.git")

    assert installed.id == "pomodoro"
    assert (installed.path / ADDON_MANIFEST).is_file()
    assert [addon.id for addon in manager.list_installed()] == ["pomodoro"]
    with pytest.raises(AddonError, match="already installed"):
        manager.install("https://github.com/example/another.git")


def test_install_rejects_missing_or_invalid_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = AddonManager(tmp_path / "addons")

    def fake_git(command: list[str], **kwargs: object) -> SimpleNamespace:
        Path(command[-1]).mkdir(parents=True)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_git)

    with pytest.raises(AddonError, match=ADDON_MANIFEST):
        manager.install("https://github.com/example/no-manifest.git")
    assert manager.list_installed() == []


def test_remove_deletes_only_the_selected_addon_directory(tmp_path: Path) -> None:
    manager = AddonManager(tmp_path / "addons")
    addon_path = manager.addons_dir / "pomodoro"
    write_manifest(addon_path)

    manager.remove("pomodoro")

    assert not addon_path.exists()
    with pytest.raises(AddonError, match="invalid"):
        manager.remove("../outside")


def test_invalid_installed_manifest_remains_visible_for_removal(tmp_path: Path) -> None:
    manager = AddonManager(tmp_path / "addons")
    bad_addon = manager.addons_dir / "broken"
    bad_addon.mkdir(parents=True)
    (bad_addon / ADDON_MANIFEST).write_text("not json", encoding="utf-8")

    installed = manager.list_installed()

    assert len(installed) == 1
    assert installed[0].id == "broken"
    assert not installed[0].available
    manager.remove("broken")
    assert not bad_addon.exists()


def test_request_passes_json_lines_and_validates_addon_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = AddonManager(tmp_path / "addons")
    addon_path = manager.addons_dir / "pomodoro"
    write_manifest(addon_path)
    received: dict[str, object] = {}

    def fake_process(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert kwargs["encoding"] == "utf-8"
        request = json.loads(str(kwargs["input"]))
        received.update(request)
        response = {
            "protocol": 1,
            "id": request["id"],
            "view": {
                "title": "Pomodoro",
                "body": "Ready.",
                "state": {"remaining_seconds": 1500},
                "actions": [{"id": "start", "label": "Start"}],
            },
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(response),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_process)

    response = manager.request("pomodoro", "view")

    assert received["protocol"] == 1
    assert received["method"] == "view"
    assert received["state"] is None
    assert response.body == "Ready."
    assert response.state == {"remaining_seconds": 1500}
    assert response.actions[0].id == "start"

    manager.request("pomodoro", "refresh", state={"remaining_seconds": 1499})
    assert received["method"] == "refresh"
    assert received["state"] == {"remaining_seconds": 1499}


def test_request_rejects_response_for_another_request_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = AddonManager(tmp_path / "addons")
    write_manifest(manager.addons_dir / "pomodoro")

    def fake_process(command: list[str], **kwargs: object) -> SimpleNamespace:
        response = {
            "protocol": 1,
            "id": "wrong-id",
            "view": {"title": "Pomodoro", "body": "", "state": None},
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_process)

    with pytest.raises(AddonError, match="request id"):
        manager.request("pomodoro", "view")
