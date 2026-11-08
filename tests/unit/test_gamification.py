from pathlib import Path
import tomllib
from datetime import date, timedelta

from src.utils.config import Config
from src.utils.gamification import (
    DAILY_LOGIN_BASE_EXP,
    DEFAULT_GAMIFICATION_SETTINGS,
    DEFAULT_TITLE_CODE,
    MAX_LEVEL,
    RANK_COLORS,
    TITLES,
    available_titles,
    calculate_streak,
    experience_for_level,
    level_for_experience,
    rank_color,
    render_title_label,
    title_for_code,
)


def test_progression_calculates_level_from_experience() -> None:
    assert level_for_experience(0) == 0
    assert experience_for_level(1) == 100
    assert experience_for_level(10) == 5500
    assert level_for_experience(experience_for_level(1) - 1) == 0
    assert level_for_experience(experience_for_level(51)) == 51


def test_progression_stops_at_level_cap() -> None:
    assert experience_for_level(MAX_LEVEL + 1) == experience_for_level(MAX_LEVEL)
    assert level_for_experience(experience_for_level(MAX_LEVEL) * 2) == MAX_LEVEL


def test_available_titles_are_ordered_and_limited_to_current_level() -> None:
    titles = available_titles(20)

    assert [title.level for title in titles] == [0, 1, 2, 5, 10, 20]
    assert titles[-1].name == "Terminal Wizard"
    assert all(title.level <= 20 for title in titles)


def test_title_codes_are_unique_and_locked_codes_are_rejected() -> None:
    codes = [title.code for title in TITLES]

    assert len(codes) == len(set(codes))
    assert title_for_code(DEFAULT_TITLE_CODE, 0).name == "Newbie"
    assert title_for_code(TITLES[-1].code, 999) is None
    assert title_for_code("not-a-title-code", MAX_LEVEL) is None


def test_rank_colors_use_highest_configured_threshold() -> None:
    assert rank_color(0) == RANK_COLORS[0]
    assert rank_color(59) == RANK_COLORS[50]
    assert rank_color(999) == RANK_COLORS[100]
    assert rank_color(1000) == "#00FF41"


def test_streak_continues_for_consecutive_days_and_resets_after_a_gap() -> None:
    today = date(2026, 11, 7)

    assert calculate_streak("", 0, today) == 1
    assert calculate_streak(today.isoformat(), 4, today) == 4
    assert calculate_streak((today - timedelta(days=1)).isoformat(), 4, today) == 5
    assert calculate_streak((today - timedelta(days=2)).isoformat(), 4, today) == 1
    assert calculate_streak("not-a-date", 4, today) == 1


def test_daily_experience_scales_with_streak() -> None:
    assert DAILY_LOGIN_BASE_EXP * 1 == 100
    assert DAILY_LOGIN_BASE_EXP * 5 == 500


def test_title_label_color_comes_from_title_even_at_a_higher_user_level() -> None:
    title = next(title for title in TITLES if title.name == "Ghost in the Shell")

    label = render_title_label("Level 1000 - ", title)

    assert label.plain == "Level 1000 - Ghost in the Shell"
    assert label.spans[0].start == len("Level 1000 - ")
    assert label.spans[0].style.color.get_truecolor().hex == "#f5f5ff"


def test_config_defaults_invalid_experience_and_title_to_newbie(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text(
        '[gamification]\nexperience = -12\nselected_title = "invalid-code"\n',
        encoding="utf-8",
    )
    test_config = Config(default_file, tmp_path / "config.override.toml")

    assert not test_config.experience_is_valid
    assert test_config.experience == 0
    assert not test_config.selected_title_is_valid
    assert test_config.selected_title_code == DEFAULT_TITLE_CODE
    assert test_config.selected_title_name == "Newbie"


def test_config_rejects_a_valid_but_locked_title_code(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text(
        f'[gamification]\nexperience = 0\nselected_title = "{TITLES[-1].code}"\n',
        encoding="utf-8",
    )
    test_config = Config(default_file, tmp_path / "config.override.toml")

    assert not test_config.selected_title_is_valid
    assert test_config.selected_title_name == "Newbie"


def test_config_migration_adds_missing_gamification_keys(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text('[ui]\ntheme = "default"\n', encoding="utf-8")
    override_file = tmp_path / "config.override.toml"
    override_file.write_text(
        '[ui]\ntheme = "user-choice"\n\n[gamification]\nexperience = 300\n',
        encoding="utf-8",
    )

    test_config = Config(default_file, override_file)

    assert test_config.gamification_defaults_added
    assert test_config.experience == 300
    assert test_config.selected_title_code == DEFAULT_TITLE_CODE
    saved = tomllib.loads(override_file.read_text(encoding="utf-8"))
    assert saved["ui"]["theme"] == "user-choice"
    assert saved["gamification"] == {
        **DEFAULT_GAMIFICATION_SETTINGS,
        "experience": 300,
    }


def test_saving_a_title_persists_both_gamification_values(tmp_path: Path) -> None:
    default_file = tmp_path / "config.toml"
    default_file.write_text('[ui]\ntheme = "default"\n', encoding="utf-8")
    override_file = tmp_path / "config.override.toml"
    test_config = Config(default_file, override_file)

    test_config.update("gamification", "selected_title", DEFAULT_TITLE_CODE)

    saved = override_file.read_text(encoding="utf-8")
    assert "experience = 0" in saved
    assert f'selected_title = "{DEFAULT_TITLE_CODE}"' in saved
    assert test_config.experience == 0
