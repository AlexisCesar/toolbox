from datetime import date

from src.utils.config import config


HALLOWEEN_THEME = "halloween"
CHRISTMAS_THEME = "christmas"
DEFAULT_THEME = "textual-dark"
SEASONAL_THEMES = (HALLOWEEN_THEME, CHRISTMAS_THEME)


def is_halloween_season(today: date | None = None) -> bool:
    """Return whether Halloween theme selection is available on the given date."""
    current_date = today or date.today()
    return (current_date.month, current_date.day) >= (10, 1) and (
        current_date.month,
        current_date.day,
    ) <= (11, 10)


def is_christmas_season(today: date | None = None) -> bool:
    """Return whether Christmas theme selection is available in December."""
    current_date = today or date.today()
    return current_date.month == 12


def is_theme_available(
    theme_name: str,
    today: date | None = None,
    *,
    force_all: bool | None = None,
) -> bool:
    """Return whether a seasonal theme may be selected on the given date."""
    if theme_name not in SEASONAL_THEMES:
        return True
    if force_all is None:
        force_all = config.enable_all_seasonal_themes
    if force_all:
        return True
    if theme_name == HALLOWEEN_THEME:
        return is_halloween_season(today)
    return is_christmas_season(today)


def available_themes(
    themes: list[str],
    today: date | None = None,
    *,
    force_all: bool | None = None,
) -> list[str]:
    """Return regular themes and each seasonal theme currently selectable."""
    return [
        *themes,
        *(
            theme_name
            for theme_name in SEASONAL_THEMES
            if is_theme_available(theme_name, today, force_all=force_all)
        ),
    ]
