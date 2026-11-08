from collections.abc import MutableMapping
from pathlib import Path
import os

import tomllib
import tomlkit

from src.utils.gamification import (
    DEFAULT_GAMIFICATION_SETTINGS,
    DEFAULT_TITLE_CODE,
    available_titles,
    level_for_experience,
    title_for_code,
)


SCRIPT_EXTENSIONS = {".py", ".sh", ".sql", ".ps1", ".bat", ".cmd"}


def normalize_directory_path(path: str) -> str:
    """Use forward slashes for directory paths entered in settings."""
    return path.replace("\\", "/")


def iter_script_files(scripts_dir: Path, depth: int):
    """Yield supported script files up to the configured subdirectory depth."""
    scripts_dir = Path(scripts_dir)
    max_depth = max(0, min(int(depth), Config.MAX_SCRIPTS_DEPTH))
    for directory, subdirectories, filenames in os.walk(scripts_dir):
        relative_directory = Path(directory).relative_to(scripts_dir)
        if len(relative_directory.parts) >= max_depth:
            subdirectories.clear()
        for filename in filenames:
            file_path = Path(directory) / filename
            if file_path.suffix.lower() in SCRIPT_EXTENSIONS:
                yield file_path


class Config:

    MAX_SCRIPTS_DEPTH = 5

    def __init__(
        self,
        default_path: Path | None = None,
        override_path: Path | None = None,
    ) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.default_path = default_path or project_root / "config.toml"
        self.config_path = override_path or project_root / "config.override.toml"
        self._create_override_if_missing()
        with self.config_path.open("rb") as config_file:
            self._data = tomllib.load(config_file)
        self.gamification_defaults_added = False
        self.gamification_migration_error: str | None = None
        self._ensure_gamification_defaults()

    def _ensure_gamification_defaults(self) -> None:
        """Add missing gamification fields to existing user override files."""
        defaults = DEFAULT_GAMIFICATION_SETTINGS
        settings = self._data.get("gamification")
        if not isinstance(settings, dict):
            settings = {}
            self._data["gamification"] = settings

        missing_keys = [key for key in defaults if key not in settings]
        if not missing_keys:
            return
        for key in missing_keys:
            settings[key] = defaults[key]

        try:
            with self.config_path.open("r", encoding="utf-8") as config_file:
                document = tomlkit.parse(config_file.read())
            table = document.get("gamification")
            if not isinstance(table, MutableMapping):
                table = tomlkit.table()
                document["gamification"] = table
            for key in missing_keys:
                table.setdefault(key, defaults[key])
            with self.config_path.open("w", encoding="utf-8") as config_file:
                config_file.write(tomlkit.dumps(document))
        except OSError as error:
            self.gamification_migration_error = str(error)
            return

        self.gamification_defaults_added = True

    def _create_override_if_missing(self) -> None:
        """Copy the checked-in defaults once, without replacing user settings."""
        if self.config_path.exists():
            return
        try:
            defaults = self.default_path.read_bytes()
            with self.config_path.open("xb") as override_file:
                try:
                    override_file.write(defaults)
                except OSError:
                    self.config_path.unlink(missing_ok=True)
                    raise
        except FileExistsError:
            return
        except OSError as error:
            raise ConfigInitializationError(
                f"Could not create the Toolbox configuration file at "
                f"'{self.config_path}': {error}. Check that the project folder "
                "is writable, then try again."
            ) from error

    @property
    def scripts_dir(self) -> Path:
        return Path(self._data["paths"]["scripts"])

    @property
    def logs(self) -> list[dict[str, str]]:
        """Return the configured log folders."""
        return [
            {"name": str(entry["name"]), "location": str(entry["location"])}
            for entry in self._data.get("logs", [])
        ]

    @property
    def services(self) -> list[dict[str, object]]:
        """Return configured health checks, preserving entries with older schemas."""
        return [dict(entry) for entry in self._data.get("services", []) if isinstance(entry, dict)]

    @property
    def notes_dir(self) -> Path:
        return Path(self._data["paths"]["notes"])

    @property
    def projects_dir(self) -> Path:
        return Path(self._data["paths"]["projects"])

    @property
    def theme(self) -> str:
        return self._data["ui"]["theme"]

    @property
    def todo_startup_notification(self) -> bool:
        """Whether to notify about pending TODO items when the app starts."""
        return bool(self._data["ui"].get("todo_startup_notification", True))

    @property
    def enable_all_seasonal_themes(self) -> bool:
        """Whether seasonal themes are available outside their calendar periods."""
        return bool(self._data["ui"].get("enable_all_seasonal_themes", False))

    @property
    def script_timeout(self) -> float:
        return float(self._data["scripts"]["timeout"])

    @property
    def scripts_depth(self) -> int:
        """Maximum subdirectory depth to search for scripts (0 to 5)."""
        try:
            depth = int(self._data["scripts"].get("depth", 0))
        except (TypeError, ValueError):
            return 0
        return max(0, min(depth, self.MAX_SCRIPTS_DEPTH))

    @property
    def experience_is_valid(self) -> bool:
        """Whether the configured gamification XP is a nonnegative integer."""
        gamification = self._data.get("gamification", {})
        experience = (
            gamification.get("experience", 0)
            if isinstance(gamification, dict)
            else 0
        )
        return (
            isinstance(experience, int)
            and not isinstance(experience, bool)
            and experience >= 0
        )

    @property
    def experience(self) -> int:
        """Return configured XP, using zero for malformed or negative values."""
        if not self.experience_is_valid:
            return 0
        gamification = self._data.get("gamification", {})
        return int(gamification.get("experience", 0))

    @property
    def level(self) -> int:
        """Calculate the current level from configured experience."""
        return level_for_experience(self.experience)

    @property
    def selected_title_is_valid(self) -> bool:
        """Whether the configured title code exists and is currently unlocked."""
        gamification = self._data.get("gamification", {})
        code = (
            gamification.get("selected_title", DEFAULT_TITLE_CODE)
            if isinstance(gamification, dict)
            else None
        )
        return title_for_code(code, self.level) is not None

    @property
    def selected_title_code(self) -> str:
        """Return a valid unlocked title code, falling back to Newbie."""
        gamification = self._data.get("gamification", {})
        code = (
            gamification.get("selected_title", DEFAULT_TITLE_CODE)
            if isinstance(gamification, dict)
            else None
        )
        title = title_for_code(code, self.level)
        return title.code if title is not None else DEFAULT_TITLE_CODE

    @property
    def selected_title_name(self) -> str:
        """Return the configured unlocked title name, defaulting to Newbie."""
        selected_code = self.selected_title_code
        for title in available_titles(self.level):
            if title.code == selected_code:
                return title.name
        return "Newbie"

    @property
    def last_started_date(self) -> str:
        gamification = self._data.get("gamification", {})
        value = (
            gamification.get("last_started_date", "")
            if isinstance(gamification, dict)
            else ""
        )
        return value if isinstance(value, str) else ""

    @property
    def daily_exp_received(self) -> bool:
        gamification = self._data.get("gamification", {})
        value = (
            gamification.get("daily_exp_received", False)
            if isinstance(gamification, dict)
            else False
        )
        return value is True

    @property
    def streak_days(self) -> int:
        gamification = self._data.get("gamification", {})
        value = gamification.get("streak_days", 0) if isinstance(gamification, dict) else 0
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return 0
        return value

    @property
    def first_theme_change_rewarded(self) -> bool:
        gamification = self._data.get("gamification", {})
        value = (
            gamification.get("first_theme_change_rewarded", False)
            if isinstance(gamification, dict)
            else False
        )
        return value is True
    
    def update(self, section: str, key: str, value):
        if section == "gamification":
            self.update_gamification(**{key: value})
            return

        with self.config_path.open("r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

        if section not in doc:
            doc[section] = tomlkit.table()
        doc[section][key] = value

        with self.config_path.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        if not isinstance(self._data.get(section), dict):
            self._data[section] = {}
        self._data[section][key] = value

    def update_gamification(self, **changes: object) -> None:
        """Persist gamification values together in the user override file."""
        unknown_keys = set(changes) - set(DEFAULT_GAMIFICATION_SETTINGS)
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            raise ValueError(f"Unknown gamification setting(s): {names}")
        self._validate_gamification_changes(changes)

        with self.config_path.open("r", encoding="utf-8") as config_file:
            document = tomlkit.parse(config_file.read())
        table = document.get("gamification")
        if not isinstance(table, MutableMapping):
            table = tomlkit.table()
            document["gamification"] = table
        for key, default in DEFAULT_GAMIFICATION_SETTINGS.items():
            table.setdefault(key, default)
        for key, value in changes.items():
            table[key] = value

        with self.config_path.open("w", encoding="utf-8") as config_file:
            config_file.write(tomlkit.dumps(document))

        settings = self._data.get("gamification")
        if not isinstance(settings, dict):
            settings = {}
        self._data["gamification"] = {
            **DEFAULT_GAMIFICATION_SETTINGS,
            **settings,
            **changes,
        }

    @staticmethod
    def _validate_gamification_changes(changes: dict[str, object]) -> None:
        if "experience" in changes:
            experience = changes["experience"]
            if (
                not isinstance(experience, int)
                or isinstance(experience, bool)
                or experience < 0
            ):
                raise ValueError("Gamification experience must be a nonnegative integer.")
        if "streak_days" in changes:
            streak_days = changes["streak_days"]
            if (
                not isinstance(streak_days, int)
                or isinstance(streak_days, bool)
                or streak_days < 0
            ):
                raise ValueError("Gamification streak must be a nonnegative integer.")
        for key in ("daily_exp_received", "first_theme_change_rewarded"):
            if key in changes and not isinstance(changes[key], bool):
                raise ValueError(f"Gamification setting '{key}' must be boolean.")
        for key in ("selected_title", "last_started_date"):
            if key in changes and not isinstance(changes[key], str):
                raise ValueError(f"Gamification setting '{key}' must be text.")

    def update_logs(self, entries: list[dict[str, str]]) -> None:
        """Replace configured log folders and persist them as TOML array tables."""
        normalized_entries = [
            {"name": str(entry["name"]), "location": str(entry["location"])}
            for entry in entries
        ]
        with self.config_path.open("r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

        log_tables = tomlkit.aot()
        for entry in normalized_entries:
            log_table = tomlkit.table()
            log_table["name"] = entry["name"]
            log_table["location"] = entry["location"]
            log_tables.append(log_table)
        doc["logs"] = log_tables

        with self.config_path.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        self._data["logs"] = normalized_entries

    def update_services(self, entries: list[dict[str, object]]) -> None:
        """Replace configured health checks and persist them as TOML array tables."""
        normalized_entries = [dict(entry) for entry in entries]
        with self.config_path.open("r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

        service_tables = tomlkit.aot()
        for entry in normalized_entries:
            service_table = tomlkit.table()
            for key, value in entry.items():
                service_table[key] = value
            service_tables.append(service_table)
        doc["services"] = service_tables

        with self.config_path.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        self._data["services"] = normalized_entries


class ConfigInitializationError(OSError):
    """Raised when the user-specific configuration cannot be initialized."""


config = Config()
