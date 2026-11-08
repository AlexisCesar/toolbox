"""Level progression and unlockable titles for the Toolbox profile."""

from dataclasses import dataclass
from datetime import date, timedelta

from rich.style import Style
from rich.text import Text


MAX_LEVEL = 9999
DEFAULT_TITLE_CODE = "8f72c4a1-6b39-4d05-ae17-92c0f53b684e"
DAILY_LOGIN_BASE_EXP = 100
SCRIPT_RUN_EXP = 20
NOTE_OPEN_EXP = 10
LOG_OPEN_EXP = 10
TODO_COMPLETION_BASE_EXP = 25
TODO_PRIORITY_MULTIPLIER = {"low": 1, "medium": 2, "high": 3}
FIRST_THEME_CHANGE_EXP = 50

DEFAULT_GAMIFICATION_SETTINGS: dict[str, object] = {
    "experience": 0,
    "selected_title": DEFAULT_TITLE_CODE,
    "last_started_date": "",
    "daily_exp_received": False,
    "streak_days": 0,
    "first_theme_change_rewarded": False,
}


@dataclass(frozen=True)
class Title:
    """A title unlocked at a specific level and stored by its opaque code."""

    level: int
    name: str
    code: str


TITLES = (
    Title(0, "Newbie", DEFAULT_TITLE_CODE),
    Title(1, "Digital Wanderer", "c1a95e37-2d84-4f60-bb13-7e5a0c92d648"),
    Title(2, "Code Seeker", "5d3b8a26-f1c7-49e0-9a54-6b2d71c8430f"),
    Title(5, "Byte Tamer", "e40c7b19-8a53-4d26-bf91-3c6e2a75d804"),
    Title(10, "Netrunner", "2b7e4d91-c603-48af-85d2-1a9c6f30e754"),
    Title(20, "Terminal Wizard", "a63f0c82-5e19-47d4-9b30-8f2c61e7a549"),
    Title(30, "Root Access", "7c1e9a54-3b82-46d0-a5f7-2e8c13b9640a"),
    Title(40, "Bug Slayer", "d9a42f60-1c75-4e83-bb06-5f2a8c71e349"),
    Title(50, "Cybernetic Master", "4e8b2c17-9d63-40a5-8f31-c6a27e5b904d"),
    Title(60, "Supreme Intelligence", "b35d7f02-6a91-4c48-9e23-1f8a5d70c634"),
    Title(70, "Beyond the Matrix", "6a0f3d85-c214-47b9-ae62-9c1e5f38d704"),
    Title(80, "Infinite Loop", "f27c1a69-4d83-40e5-b916-3a7c2d8f5041"),
    Title(90, "Kernel Overlord", "19e6b4c2-7a50-43df-8c21-d5f9036b7a48"),
    Title(100, "Ghost in the Shell", "83c5d1a7-2f49-46be-901d-7a3c8e5f2164"),
    Title(1000, "The Source", "0d7a3e91-b5c2-4f68-9a14-e3c7f0268b5d"),
)

TITLES_BY_CODE = {title.code: title for title in TITLES}

RANK_COLORS: dict[int, str] = {
    0: "#8B929C",
    10: "#35B6A4",
    20: "#3B9EFF",
    30: "#5865F2",
    40: "#9B59E8",
    50: "#D34BCE",
    60: "#E34B91",
    70: "#F04455",
    80: "#FF8A32",
    90: "#FFD43B",
    100: "#F5F5FF",
    1000: "#00FF41",
}


def experience_for_level(level: int) -> int:
    """Return the cumulative experience required to reach ``level``.

    The first level costs 100 XP, and each following level costs 100 XP more
    than the previous one. The cumulative threshold is the sum of that
    arithmetic progression, leaving a meaningful curve through level 9999.
    """
    bounded_level = max(0, min(int(level), MAX_LEVEL))
    return 50 * bounded_level * (bounded_level + 1)


def level_for_experience(experience: int) -> int:
    """Calculate the user's level from XP, capped at ``MAX_LEVEL``."""
    experience = max(0, int(experience))
    low, high = 0, MAX_LEVEL
    while low < high:
        midpoint = (low + high + 1) // 2
        if experience_for_level(midpoint) <= experience:
            low = midpoint
        else:
            high = midpoint - 1
    return low


def available_titles(level: int) -> tuple[Title, ...]:
    """Return unlocked titles in ascending unlock-level order."""
    bounded_level = max(0, min(int(level), MAX_LEVEL))
    unlocked = (title for title in TITLES if title.level <= bounded_level)
    return tuple(sorted(unlocked, key=lambda title: title.level))


def title_for_code(code: object, level: int) -> Title | None:
    """Return the title for a valid, unlocked code, if one exists."""
    if not isinstance(code, str):
        return None
    title = TITLES_BY_CODE.get(code)
    if title is None or title.level > max(0, min(int(level), MAX_LEVEL)):
        return None
    return title


def rank_color(level: int) -> str:
    """Choose the configured color for the highest rank threshold reached."""
    bounded_level = max(0, min(int(level), MAX_LEVEL))
    threshold = max(rank for rank in RANK_COLORS if rank <= bounded_level)
    return RANK_COLORS[threshold]


def render_title_label(prefix: str, title: Title) -> Text:
    """Render a neutral prefix followed by the title's rank color."""
    label = Text(prefix)
    color = rank_color(title.level)
    label.append(title.name, style=Style(color=color, bold=True))
    return label


def calculate_streak(
    last_started_date: str,
    previous_streak: int,
    today: date,
) -> int:
    """Continue a consecutive-day streak or restart it at one day."""
    try:
        previous_date = date.fromisoformat(last_started_date)
    except (TypeError, ValueError):
        return 1

    streak = max(1, previous_streak)
    if previous_date == today:
        return streak
    if previous_date == today - timedelta(days=1):
        return streak + 1
    return 1
