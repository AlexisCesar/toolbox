from pathlib import Path
import os

import tomllib
import tomlkit


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
    
    def update(self, section: str, key: str, value):
        with self.config_path.open("r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

        doc[section][key] = value

        with self.config_path.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        self._data[section][key] = value

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
