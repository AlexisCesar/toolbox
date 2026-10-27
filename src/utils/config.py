from pathlib import Path
import os

import tomllib
import tomlkit


SCRIPT_EXTENSIONS = {".py", ".sh", ".sql", ".ps1", ".bat", ".cmd"}


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

    def __init__(self):
        with open("config.toml", "rb") as f:
            self._data = tomllib.load(f)

    @property
    def scripts_dir(self) -> Path:
        return Path(self._data["paths"]["scripts"])

    @property
    def logs_dir(self) -> Path:
        return Path(self._data["paths"]["logs"])

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
        self._data[section][key] = value

        with open("config.toml", "r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

        doc[section][key] = value

        with open("config.toml", "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))


config = Config()
