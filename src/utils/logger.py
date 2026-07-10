from datetime import datetime
from textual.widgets import Log, RichLog


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
        log_level_style = {
            "INFO": "blue",
            "WARN": "yellow",
            "ERROR": "red",
        }.get(level, "white")
        
        log.write(f"[bold {log_level_style}][{level} - {time}] {message}")