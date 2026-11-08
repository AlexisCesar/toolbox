from datetime import date
from pathlib import Path

from src.utils.config import Config, config
from src.utils.seasonal_theme import (
    CHRISTMAS_THEME,
    HALLOWEEN_THEME,
    available_themes,
    is_theme_available,
)
from src.views import home as home_module


def test_halloween_theme_is_available_from_october_first_through_november_tenth() -> None:
    assert is_theme_available(HALLOWEEN_THEME, date(2026, 10, 1), force_all=False)
    assert is_theme_available(HALLOWEEN_THEME, date(2026, 11, 10), force_all=False)
    assert not is_theme_available(HALLOWEEN_THEME, date(2026, 9, 30), force_all=False)
    assert not is_theme_available(HALLOWEEN_THEME, date(2026, 11, 11), force_all=False)


def test_christmas_theme_is_available_throughout_december() -> None:
    assert is_theme_available(CHRISTMAS_THEME, date(2026, 12, 1), force_all=False)
    assert is_theme_available(CHRISTMAS_THEME, date(2026, 12, 31), force_all=False)
    assert not is_theme_available(CHRISTMAS_THEME, date(2026, 11, 30), force_all=False)
    assert not is_theme_available(CHRISTMAS_THEME, date(2027, 1, 1), force_all=False)


def test_home_includes_christmas_theme_tip_during_december(monkeypatch) -> None:
    monkeypatch.setattr(home_module, "is_halloween_season", lambda: False)
    monkeypatch.setattr(home_module, "is_christmas_season", lambda: True)

    instructions = home_module.Home().instructions()

    assert "The Christmas theme is available in Settings throughout December." in instructions
    assert "The Halloween theme is available" not in instructions


def test_home_changelog_omits_empty_sections_and_escapes_markup() -> None:
    rendered = home_module.format_changelog(
        "1.2.3",
        {
            "1.2.3": {
                "date": "2026-11-07",
                "added": ["Added a [quick] action."],
                "changed": [],
                "fixed": ["Fixed a display issue."],
            }
        },
    )

    assert "Version 1.2.3 Update Log:" in rendered
    assert "Added:" in rendered
    assert "Added a \\[quick] action." in rendered
    assert "Changed:" not in rendered
    assert "Fixed:" in rendered


def test_release_version_matches_project_metadata() -> None:
    import tomllib

    from src.version import APP_VERSION, CHANGELOG

    project_file = Path(__file__).parents[2] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))
    lock_file = Path(__file__).parents[2] / "uv.lock"
    lock = tomllib.loads(lock_file.read_text(encoding="utf-8"))
    locked_project = next(
        package for package in lock["package"] if package["name"] == "toolbox"
    )

    assert project["project"]["version"] == APP_VERSION
    assert locked_project["version"] == APP_VERSION
    assert APP_VERSION in CHANGELOG


def test_manual_override_makes_all_seasonal_themes_available_year_round() -> None:
    today = date(2026, 6, 15)

    assert is_theme_available(HALLOWEEN_THEME, today, force_all=True)
    assert is_theme_available(CHRISTMAS_THEME, today, force_all=True)
    assert available_themes(["textual-dark"], today, force_all=True) == [
        "textual-dark",
        HALLOWEEN_THEME,
        CHRISTMAS_THEME,
    ]


def test_manual_override_defaults_to_disabled_when_missing_from_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "config.toml").write_text(
        '[ui]\ntheme = "textual-dark"\n',
        encoding="utf-8",
    )
    assert Config(
        tmp_path / "config.toml", tmp_path / "config.override.toml"
    ).enable_all_seasonal_themes is False


def test_enabled_config_override_makes_both_themes_available(monkeypatch) -> None:
    monkeypatch.setattr(
        config,
        "_data",
        {"ui": {"enable_all_seasonal_themes": True}},
    )

    assert available_themes(["textual-dark"], date(2026, 6, 15)) == [
        "textual-dark",
        HALLOWEEN_THEME,
        CHRISTMAS_THEME,
    ]


def test_manual_override_reads_boolean_from_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "config.toml").write_text(
        '[ui]\ntheme = "textual-dark"\nenable_all_seasonal_themes = true\n',
        encoding="utf-8",
    )
    assert Config(
        tmp_path / "config.toml", tmp_path / "config.override.toml"
    ).enable_all_seasonal_themes is True
