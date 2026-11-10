import json
from pathlib import Path

import pytest
import tomllib

from src.utils.config import Config


DEFAULT_CONFIG = """\
[paths]
scripts = "./scripts"
notes = "./notes"
projects = "./projects"

[ui]
theme = "textual-dark"

[scripts]
timeout = 3
depth = 1

[[logs]]
name = "Initial logs"
location = "./logs"

[[services]]
name = "Initial check"
type = "http"
target = "https://example.com"
interval = 5
"""


def make_config(tmp_path: Path) -> Config:
    defaults = tmp_path / "config.toml"
    defaults.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return Config(defaults, tmp_path / "config.override.toml")


def test_export_writes_only_selected_sections(tmp_path: Path) -> None:
    configuration = make_config(tmp_path)
    destination = tmp_path / "transfer.json"

    written_path = configuration.export_configuration(destination, ("logs", "services"))

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert written_path == destination
    assert payload["format"] == "toolbox-config"
    assert payload["version"] == 1
    assert set(payload["sections"]) == {"logs", "services"}
    assert payload["sections"]["logs"] == configuration.logs
    assert payload["sections"]["services"] == configuration.services


def test_import_replaces_only_selected_sections_and_persists_toml(tmp_path: Path) -> None:
    configuration = make_config(tmp_path)
    original_services = configuration.services
    imported_logs = [{"name": "Shared logs", "location": r"\server\share\logs"}]
    imported_services = [
        {"name": "Shared check", "type": "tcp", "target": "localhost:5432", "interval": 10}
    ]

    imported = configuration.import_configuration_sections(
        {"logs": imported_logs, "services": imported_services},
        ("logs",),
    )

    saved = tomllib.loads(configuration.config_path.read_text(encoding="utf-8"))
    assert imported == ("logs",)
    assert configuration.logs == imported_logs
    assert configuration.services == original_services
    assert saved["logs"] == imported_logs
    assert saved["services"] == original_services


def test_importing_gamification_fills_missing_defaults(tmp_path: Path) -> None:
    configuration = make_config(tmp_path)
    configuration.import_configuration_sections(
        {"gamification": {"experience": 40}},
        ("gamification",),
    )

    saved = tomllib.loads(configuration.config_path.read_text(encoding="utf-8"))
    assert saved["gamification"]["experience"] == 40
    assert saved["gamification"]["streak_days"] == 0
    assert configuration.experience == 40


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"format": "other", "version": 1, "sections": {"logs": []}}, "not a Toolbox"),
        ({"format": "toolbox-config", "version": 99, "sections": {}}, "version is not supported"),
        (
            {"format": "toolbox-config", "version": 1, "sections": {"logs": ["invalid"]}},
            "list of TOML-compatible objects",
        ),
    ],
)
def test_read_export_rejects_unknown_or_invalid_content(
    tmp_path: Path,
    payload: dict[str, object],
    message: str,
) -> None:
    configuration = make_config(tmp_path)
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        configuration.read_configuration_export(source)


def test_read_export_rejects_invalid_json(tmp_path: Path) -> None:
    configuration = make_config(tmp_path)
    source = tmp_path / "invalid.json"
    source.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        configuration.read_configuration_export(source)


def test_read_export_rejects_non_https_calendar_urls(tmp_path: Path) -> None:
    configuration = make_config(tmp_path)
    source = tmp_path / "invalid-calendar.json"
    source.write_text(
        json.dumps(
            {
                "format": "toolbox-config",
                "version": 1,
                "sections": {"calendar": {"url": "file:///private/data.ics"}},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="valid HTTPS subscription URL"):
        configuration.read_configuration_export(source)


@pytest.mark.parametrize(
    "selected",
    [(), ("unknown",)],
)
def test_export_rejects_empty_or_unknown_selection(
    tmp_path: Path,
    selected: tuple[str, ...],
) -> None:
    configuration = make_config(tmp_path)

    with pytest.raises(ValueError):
        configuration.export_configuration(tmp_path / "transfer.json", selected)


def test_export_does_not_overwrite_a_toml_configuration_file(tmp_path: Path) -> None:
    configuration = make_config(tmp_path)
    original = configuration.config_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="configuration is not overwritten"):
        configuration.export_configuration(configuration.config_path, ("logs",))

    assert configuration.config_path.read_text(encoding="utf-8") == original


def test_import_rejects_unselected_or_invalid_section_without_changes(tmp_path: Path) -> None:
    configuration = make_config(tmp_path)
    initial_logs = configuration.logs

    with pytest.raises(ValueError, match="does not contain 'logs'"):
        configuration.import_configuration_sections({"services": []}, ("logs",))
    with pytest.raises(ValueError, match="text name and location"):
        configuration.import_configuration_sections(
            {"logs": [{"name": "Missing location"}]},
            ("logs",),
        )

    assert configuration.logs == initial_logs
