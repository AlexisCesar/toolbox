from pathlib import Path
import tomllib


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


config = Config()