from src.utils.logger import Logger
from src.utils.config import config
from pathlib import Path
import platform
import shlex
import subprocess


class ScriptRunner:

    def __init__(self, logger: Logger, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger
        
    
    def run(self, script_path: str, external_terminal: bool = False, parameters: str = "") -> None:
        """Run a script based on its file extension."""
        script_path = Path(script_path)
        if not script_path.exists():
            self.logger.error(f"Script {script_path} does not exist.")
            return
        if script_path.suffix.lower() == ".py":
            self.logger.info(f"Executing Python 🐍 script: {script_path.name}")
            if external_terminal:
                self.run_in_external_terminal(["python", script_path])
            else:
                self.run_subprocess(["python", script_path, *shlex.split(parameters)])
        elif script_path.suffix.lower() == ".ps1":
            self.logger.info(f"Executing Powershell 📜 script: {script_path.name}")
            if external_terminal:
                self.run_in_external_terminal(["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path])
            else:
                self.run_subprocess(["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path, *shlex.split(parameters)])
        elif script_path.suffix.lower() == ".sh":
            self.logger.info(f"Executing Shell 🐚 script: {script_path.name}")
            if external_terminal:
                self.run_in_external_terminal(["bash", script_path])
            else:
                self.run_subprocess(["bash", script_path, *shlex.split(parameters)])
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
            self.logger.warn("The script was probably waiting for user input. In this case you should use the 'Run - External Terminal' option. " + 
                             "If that's not the case, consider increasing the timeout in config.toml.")
        except Exception as e:
            self.logger.error(f"Failed to execute script: {e}")
    
    
    def run_in_external_terminal(self, command: list) -> None:
        """Run a script in an external terminal."""
        system = platform.system()

        if system == "Windows":
            command_str = subprocess.list2cmdline(command)

            subprocess.Popen([
                "cmd",
                "/c",
                "start",
                "cmd",
                "/k",
                command_str,
            ])

        elif system == "Linux":
            command_str = " ".join(shlex.quote(str(arg)) for arg in command)

            subprocess.Popen([
                "x-terminal-emulator",
                "-e",
                "bash",
                "-c",
                f"{command_str}; exec bash",
            ])

        elif system == "Darwin":
            # TODO: Implement macOS support
            raise NotImplementedError("macOS is not supported yet.")

        else:
            raise RuntimeError(f"Unsupported operating system: {system}")