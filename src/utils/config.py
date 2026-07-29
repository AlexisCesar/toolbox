from pathlib import Path

import tomllib
import tomlkit


class Config:

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
    def theme(self) -> str:
        return self._data["ui"]["theme"]

    @property
    def script_timeout(self) -> float:
        return float(self._data["scripts"]["timeout"])
    
    def update(self, section: str, key: str, value):
        self._data[section][key] = value

        with open("config.toml", "r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

        doc[section][key] = value

        with open("config.toml", "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))


config = Config()