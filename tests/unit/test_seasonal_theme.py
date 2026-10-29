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
    monkeypatch.chdir(tmp_path)

    assert Config().enable_all_seasonal_themes is False


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
    monkeypatch.chdir(tmp_path)

    assert Config().enable_all_seasonal_themes is True
