from pathlib import Path

import tomllib
import pytest

from src.utils.config import Config


def test_update_logs_persists_toml_array_tables(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text(
        '[paths]\nscripts = "./scripts"\nnotes = "./notes"\nprojects = "./projects"\n\n'
        '[ui]\ntheme = "textual-dark"\n',
        encoding="utf-8",
    )
    default_content = default_file.read_text(encoding="utf-8")
    override_file = tmp_path / "config.override.toml"
    test_config = Config(default_file, override_file)
    entries = [
        {"name": "Application X v2", "location": r"C:\dev\logs"},
        {"name": "Network app", "location": r"\\server\share\app-logs"},
    ]

    test_config.update_logs(entries)

    parsed = tomllib.loads(override_file.read_text(encoding="utf-8"))
    assert parsed["logs"] == entries
    assert test_config.logs == entries
    assert default_file.read_text(encoding="utf-8") == default_content


def test_update_logs_can_clear_all_entries(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[paths]\nscripts = "./scripts"\nnotes = "./notes"\nprojects = "./projects"\n\n'
        '[ui]\ntheme = "textual-dark"\n\n'
        '[[logs]]\nname = "Old"\nlocation = "./logs"\n',
        encoding="utf-8",
    )
    override_file = tmp_path / "config.override.toml"
    test_config = Config(config_file, override_file)

    test_config.update_logs([])

    parsed = tomllib.loads(override_file.read_text(encoding="utf-8"))
    assert parsed.get("logs", []) == []
    assert test_config.logs == []


def test_existing_override_is_preserved_and_not_reinitialized(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text('[ui]\ntheme = "default"\n', encoding="utf-8")
    override_file = tmp_path / "config.override.toml"
    override_file.write_text('[ui]\ntheme = "user-choice"\n', encoding="utf-8")

    test_config = Config(default_file, override_file)

    assert test_config.theme == "user-choice"
    assert override_file.read_text(encoding="utf-8") == '[ui]\ntheme = "user-choice"\n'
    assert default_file.read_text(encoding="utf-8") == '[ui]\ntheme = "default"\n'


def test_missing_override_is_copied_from_defaults(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text('[ui]\ntheme = "starter"\n', encoding="utf-8")
    override_file = tmp_path / "config.override.toml"

    test_config = Config(default_file, override_file)

    assert test_config.theme == "starter"
    assert override_file.read_text(encoding="utf-8") == default_file.read_text(encoding="utf-8")


def test_override_creation_failure_has_actionable_error(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text('[ui]\ntheme = "starter"\n', encoding="utf-8")

    with pytest.raises(OSError, match="Check that the project folder is writable"):
        Config(default_file, tmp_path / "missing" / "config.override.toml")
