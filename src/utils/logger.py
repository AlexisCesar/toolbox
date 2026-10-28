from datetime import datetime
import random

from textual.widgets import Log, RichLog
from src.utils.seasonal_theme import CHRISTMAS_THEME, HALLOWEEN_THEME


HALLOWEEN_LOG_EMOJIS = (
    "🎃", "👻", "🕸️", "🕷️", "🦇", "💀", "☠️", "🐈‍⬛", "🧛", "🧟", "🍬", "🍭", "⚰️", "🪦",
)
CHRISTMAS_LOG_EMOJIS = (
    "🎄", "🎅", "🤶", "🧝", "🦌", "🛷", "🎁", "🎀", "🧦", "🔔", "🕯️", "☃️", "⛄",
    "❄️", "🍪", "🥛", "🥂", "🌟", "✨", "👼", "⛪", "❤️", "💚",
)


class Logger:

    def __init__(self, app):
        self.app = app

    def info(self, message: str):
        self._write("INFO", message)

    def warn(self, message: str):
        self._write("WARN", message)

    def error(self, message: str):
        self._write("ERROR", message)

    def system(self, message: str):
        self._write("SYSTEM", message)

    def separator(self):
        self._write("SYSTEM", "=" * 40)

    def _write(self, level: str, message: str):
        log = self.app.query_one("#log", RichLog)
        time = datetime.now().strftime("%H:%M:%S")
        emoji = ""
        if self.app.theme == HALLOWEEN_THEME:
            emoji = f"{random.choice(HALLOWEEN_LOG_EMOJIS)} "
        elif self.app.theme == CHRISTMAS_THEME:
            emoji = f"{random.choice(CHRISTMAS_LOG_EMOJIS)} "
        log_level_style = {
            "INFO": "blue",
            "WARN": "yellow",
            "ERROR": "red",
        }.get(level, "gray")
        
        log.write(f"{emoji}[bold {log_level_style}][{level} - {time}] {message}")
