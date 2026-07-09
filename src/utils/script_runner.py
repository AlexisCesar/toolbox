from src.utils.logger import Logger
from src.utils.config import config
from pathlib import Path
import subprocess


class ScriptRunner:

    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        
    
    def run(self, script_path: str) -> None:
        """Run a script based on its file extension."""
        script_path = Path(script_path)
        if not script_path.exists():
            self.logger.error(f"Script {script_path} does not exist.")
            return
        self.logger.separator()
        if script_path.suffix.lower() == ".py":
            self.logger.info(f"Executing Python 🐍 script: {script_path.name}")
            self.run_subprocess(["python", script_path])
        elif script_path.suffix.lower() == ".ps1":
            self.logger.info(f"Executing Powershell 📜 script: {script_path.name}")
            self.run_subprocess(["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path])
        else:
            self.logger.warn(f"Unsupported script type for file: {script_path.name}")
        self.logger.separator()


    def run_subprocess(self, command: list) -> None:
        """Run a subprocess command."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=config.script_timeout)
            if result.returncode == 0:
                self.logger.info(f"Script output:\n{result.stdout}")
            else:
                self.logger.error(f"Script errors:\n{result.stderr}")
        except subprocess.TimeoutExpired:
            self.logger.error(f"Script execution timed out. Timeout is set to {config.script_timeout} seconds.")
            self.logger.info("The script was probably waiting for user input, which is not supported yet." + 
                             "\nIf that's not the case, consider increasing the timeout in config.toml if necessary.")
        except Exception as e:
            self.logger.error(f"Failed to execute script: {e}")