import random
from datetime import datetime

from textual.widgets import RichLog
from src.utils.seasonal_theme import CHRISTMAS_THEME, HALLOWEEN_THEME


HALLOWEEN_LOG_EMOJIS = (
    "\U0001F383", "\U0001F47B",
    "\U0001F987", "\U0001F480",
    "\U0001F9DB", "\U0001F9DF", "\U0001F36C", "\U0001F36D", "\U0001FAA6",
)
CHRISTMAS_LOG_EMOJIS = (
    "\U0001F384", "\U0001F385", "\U0001F936", "\U0001F9DD", "\U0001F98C", "\U0001F6F7",
    "\U0001F381", "\U0001F380", "\U0001F9E6", "\U0001F514", "\U0001F36A", "\U0001F95B",
    "\U0001F942", "\U0001F31F", "\U0001F49A",
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
