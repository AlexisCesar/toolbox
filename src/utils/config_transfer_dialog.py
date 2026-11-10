"""Dialogs for exporting and importing selected Toolbox configuration sections."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from src.utils.config import CONFIG_TRANSFER_SECTIONS, Config, config
from src.utils.logger import Logger


@dataclass(frozen=True)
class ConfigurationTransferResult:
    """Summary of a completed configuration transfer."""

    operation: Literal["export", "import"]
    path: Path
    sections: tuple[str, ...]


class ConfigTransferDialog(ModalScreen[ConfigurationTransferResult | None]):
    """Select configuration sections and transfer them to or from a JSON file."""

    def __init__(
        self,
        operation: Literal["export", "import"],
        logger: Logger,
        configuration: Config = config,
    ) -> None:
        super().__init__()
        self.operation = operation
        self.logger = logger
        self.configuration = configuration
        self._loaded_sections: dict[str, object] = {}
        self._overwrite_confirmed_path: Path | None = None

    def compose(self) -> ComposeResult:
        title = "Export configuration" if self.operation == "export" else "Import configuration"
        description = (
            "Choose the settings to save in a Toolbox JSON file."
            if self.operation == "export"
            else "Load a Toolbox JSON file, then choose which settings to apply."
        )
        with Vertical(id="config-transfer-dialog"):
            yield Label(title, id="config-transfer-title")
            yield Static(description, id="config-transfer-description")
            yield Label("File path", classes="config-transfer-label")
            yield Input(
                value=(str(Path.cwd() / "toolbox-settings.json") if self.operation == "export" else ""),
                placeholder="Enter the JSON file path",
                id="config-transfer-path",
            )
            if self.operation == "import":
                yield Static("Load the file to see its available settings.", id="config-transfer-hint")
            yield Label("Settings to transfer", classes="config-transfer-label")
            with VerticalScroll(id="config-transfer-sections"):
                for section, label in CONFIG_TRANSFER_SECTIONS.items():
                    yield Checkbox(
                        label,
                        value=self.operation == "export",
                        disabled=self.operation == "import",
                        id=f"config-transfer-{section}",
                    )
            yield Static("", id="config-transfer-error")
            with Horizontal(id="config-transfer-buttons"):
                if self.operation == "import":
                    yield Button("Load file", id="config-transfer-load", variant="primary")
                    yield Button("Import selected", id="config-transfer-submit", variant="success", disabled=True)
                else:
                    yield Button("Export", id="config-transfer-submit", variant="success")
                yield Button("Cancel", id="config-transfer-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "config-transfer-cancel":
            self.dismiss(None)
        elif event.button.id == "config-transfer-load":
            self.load_import_file()
        elif event.button.id == "config-transfer-submit":
            if self.operation == "export":
                self.export_selected_sections()
            else:
                self.import_selected_sections()

    def load_import_file(self) -> None:
        path_text = self.query_one("#config-transfer-path", Input).value.strip()
        if not path_text:
            self._show_error("Enter the path to a Toolbox JSON export.", warning=True)
            return
        try:
            self._loaded_sections = self.configuration.read_configuration_export(path_text)
        except (OSError, ValueError) as error:
            self.logger.error(f"Could not load configuration export: {error}")
            self._show_error(str(error))
            return

        for section in CONFIG_TRANSFER_SECTIONS:
            checkbox = self.query_one(f"#config-transfer-{section}", Checkbox)
            available = section in self._loaded_sections
            checkbox.disabled = not available
            checkbox.value = available
        names = [CONFIG_TRANSFER_SECTIONS[name] for name in self._loaded_sections]
        self.query_one("#config-transfer-hint", Static).update(
            f"Loaded {len(names)} setting group(s): {', '.join(names)}."
        )
        self.query_one("#config-transfer-path", Input).disabled = True
        self.query_one("#config-transfer-submit", Button).disabled = False
        self.query_one("#config-transfer-error", Static).update("")

    def export_selected_sections(self) -> None:
        path_text = self.query_one("#config-transfer-path", Input).value.strip()
        selected = self.selected_sections()
        if not path_text:
            self._show_error("Enter a destination path for the JSON export.", warning=True)
            return
        if not selected:
            self._show_error("Select at least one setting group to export.", warning=True)
            return

        destination = Path(path_text).expanduser()
        if destination.exists() and self._overwrite_confirmed_path != destination:
            self._overwrite_confirmed_path = destination
            self.query_one("#config-transfer-submit", Button).label = "Confirm overwrite"
            self._show_error("That file already exists. Select Export again to replace it.", warning=True)
            return

        try:
            written_path = self.configuration.export_configuration(destination, selected)
        except (OSError, ValueError) as error:
            self.logger.error(f"Could not export configuration: {error}")
            self._show_error(str(error))
            return
        self.dismiss(ConfigurationTransferResult("export", written_path, selected))

    def import_selected_sections(self) -> None:
        selected = self.selected_sections()
        if not selected:
            self._show_error("Select at least one setting group to import.", warning=True)
            return
        try:
            imported = self.configuration.import_configuration_sections(
                self._loaded_sections,
                selected,
            )
        except (OSError, ValueError) as error:
            self.logger.error(f"Could not import configuration: {error}")
            self._show_error(str(error))
            return
        path = Path(self.query_one("#config-transfer-path", Input).value.strip()).expanduser()
        self.dismiss(ConfigurationTransferResult("import", path, imported))

    def selected_sections(self) -> tuple[str, ...]:
        return tuple(
            section
            for section in CONFIG_TRANSFER_SECTIONS
            if self.query_one(f"#config-transfer-{section}", Checkbox).value
        )

    def _show_error(self, message: str, *, warning: bool = False) -> None:
        if warning:
            self.logger.warn(message)
        self.query_one("#config-transfer-error", Static).update(message)
