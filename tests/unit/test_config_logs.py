from pathlib import Path

import tomllib

from src.utils.config import Config


def test_update_logs_persists_toml_array_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "config.toml").write_text(
        '[paths]\nscripts = "./scripts"\nnotes = "./notes"\nprojects = "./projects"\n\n'
        '[ui]\ntheme = "textual-dark"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    test_config = Config()
    entries = [
        {"name": "Application X v2", "location": r"C:\dev\logs"},
        {"name": "Network app", "location": r"\\server\share\app-logs"},
    ]

    test_config.update_logs(entries)

    parsed = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert parsed["logs"] == entries
    assert test_config.logs == entries


def test_update_logs_can_clear_all_entries(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[paths]\nscripts = "./scripts"\nnotes = "./notes"\nprojects = "./projects"\n\n'
        '[ui]\ntheme = "textual-dark"\n\n'
        '[[logs]]\nname = "Old"\nlocation = "./logs"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    test_config = Config()

    test_config.update_logs([])

    parsed = tomllib.loads(config_file.read_text(encoding="utf-8"))
    assert parsed.get("logs", []) == []
    assert test_config.logs == []
