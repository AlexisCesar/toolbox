from datetime import date, timedelta

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.gamification import (
    DEFAULT_GAMIFICATION_SETTINGS,
    FIRST_THEME_CHANGE_EXP,
    TITLES,
)


def make_app(monkeypatch, **settings: object) -> ToolboxTUI:
    stored_settings = {**DEFAULT_GAMIFICATION_SETTINGS, **settings}
    monkeypatch.setitem(config._data, "gamification", stored_settings)

    def save_settings(**changes: object) -> None:
        stored_settings.update(changes)

    monkeypatch.setattr(config, "update_gamification", save_settings)
    return ToolboxTUI()


def test_experience_award_updates_level_and_selects_newly_unlocked_title(monkeypatch) -> None:
    app = make_app(monkeypatch)

    assert app.award_experience(100)

    assert config.experience == 100
    assert config.level == 1
    assert config.selected_title_code == TITLES[1].code
    assert config.selected_title_name == "Digital Wanderer"


def test_daily_login_award_tracks_streak_and_pays_only_once(monkeypatch) -> None:
    today = date(2026, 11, 7)
    app = make_app(
        monkeypatch,
        last_started_date=(today - timedelta(days=1)).isoformat(),
        daily_exp_received=True,
        streak_days=2,
    )

    assert app.claim_daily_login(today) == (300, 3)
    assert app.claim_daily_login(today) == (0, 3)
    assert config.experience == 300
    assert config.last_started_date == today.isoformat()
    assert config.daily_exp_received
    assert config.streak_days == 3
    assert config.selected_title_name == "Code Seeker"


def test_daily_login_resets_streak_after_a_missed_day(monkeypatch) -> None:
    today = date(2026, 11, 7)
    app = make_app(
        monkeypatch,
        last_started_date=(today - timedelta(days=2)).isoformat(),
        daily_exp_received=True,
        streak_days=8,
    )

    assert app.claim_daily_login(today) == (100, 1)
    assert config.streak_days == 1


def test_first_theme_change_bonus_is_persistent_and_one_time(monkeypatch) -> None:
    app = make_app(monkeypatch)

    assert app.award_first_theme_change()
    assert not app.award_first_theme_change()
    assert config.experience == FIRST_THEME_CHANGE_EXP
    assert config.first_theme_change_rewarded
