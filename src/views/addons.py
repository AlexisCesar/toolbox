"""Install and remove third-party Addons from Git repositories."""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Awaitable, Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Label, Static

from src.utils.addon_manager import AddonError, AddonManager, InstalledAddon
from src.utils.confirm_dialog import ConfirmDialog, ConfirmResult
from src.utils.logger import Logger


class Addons(Static):
    """Manage Addons installed from Git repositories."""

    def __init__(
        self,
        manager: AddonManager,
        logger: Logger,
        on_change: Callable[[], Awaitable[None]],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.manager = manager
        self.logger = logger
        self.on_change = on_change
        self._installed: list[InstalledAddon] = []
        self._selected_id: str | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="addons-container"):
            yield Label("Addons", id="addons-title")
            yield Static(
                "Install and manage external Toolbox Addons. An Addon runs as your user and can access your files and network. Install only repositories you trust.",
                id="addons-description",
                markup=False,
            )
            with Horizontal(id="addons-install-row"):
                yield Input(
                    placeholder="https://github.com/owner/addon.git",
                    id="addons-repository-url",
                )
                yield Button("Install", variant="primary", id="addons-install")
                yield Button("ⓘ Developer guide", id="addons-help")
            yield Static("Enter a Git repository URL to install an Addon.", id="addons-status", markup=False)
            yield DataTable(id="addons-table", cursor_type="row", zebra_stripes=True)
            with Horizontal(id="addons-actions"):
                yield Button("Remove selected", variant="error", id="addons-remove", disabled=True)
                yield Button("Refresh list", id="addons-refresh")

    def on_mount(self) -> None:
        table = self.query_one("#addons-table", DataTable)
        table.add_columns("Name", "ID", "Version", "Status")
        self.refresh_list()

    def on_show(self) -> None:
        self.refresh_list()

    def refresh_list(self) -> None:
        """Refresh installed Addons and retain a selection when possible."""
        table = self.query_one("#addons-table", DataTable)
        try:
            self._installed = self.manager.list_installed()
        except AddonError as error:
            self.logger.error(f"Could not list installed Addons: {error}")
            self.query_one("#addons-status", Static).update(str(error))
            return

        table.clear()
        known_ids = {addon.id for addon in self._installed}
        if self._selected_id not in known_ids:
            self._selected_id = None
        for addon in self._installed:
            status = "Installed" if addon.available else "Unavailable"
            table.add_row(
                Text(addon.name),
                addon.id,
                addon.version,
                status,
                key=addon.id,
            )
        self._update_remove_button()
        if not self._installed:
            self.query_one("#addons-status", Static).update(
                "No Addons installed. Add a repository URL above to get started."
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "addons-table" or event.row_key.value is None:
            return
        self._selected_id = str(event.row_key.value)
        self._update_remove_button()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "addons-install":
            event.stop()
            self._start_install()
        elif button_id == "addons-remove":
            event.stop()
            self._confirm_remove()
        elif button_id == "addons-refresh":
            event.stop()
            self.refresh_list()
        elif button_id == "addons-help":
            event.stop()
            self.run_worker(self._open_developer_guide(), group="addons-guide", exclusive=True)

    async def _open_developer_guide(self) -> None:
        try:
            opened = await asyncio.to_thread(
                webbrowser.open,
                "https://github.com/AlexisCesar/toolbox#readme",
            )
        except webbrowser.Error as error:
            self.logger.warn(f"Could not open the Addon developer guide: {error}")
            self.query_one("#addons-status", Static).update(
                "Could not open the developer guide. See the Addons section in the Toolbox README."
            )
        else:
            if opened:
                self.logger.info("Opened the Addon developer guide in a browser.")
            else:
                self.query_one("#addons-status", Static).update(
                    "Could not open a browser. See the Addons section in the Toolbox README."
                )

    def _start_install(self) -> None:
        url = self.query_one("#addons-repository-url", Input).value.strip()
        if not url:
            self.query_one("#addons-status", Static).update("Enter a Git repository URL first.")
            return
        self.query_one("#addons-install", Button).disabled = True
        self.query_one("#addons-status", Static).update("Cloning and validating the repository…")
        self.run_worker(self._install(url), group="addons-install", exclusive=True)

    async def _install(self, url: str) -> None:
        try:
            addon = await asyncio.to_thread(self.manager.install, url)
        except AddonError as error:
            self.logger.warn(f"Addon installation failed: {error}")
            self.query_one("#addons-status", Static).update(str(error))
        else:
            self.logger.info(f"Installed Addon {addon.id} ({addon.version}).")
            self.query_one("#addons-repository-url", Input).value = ""
            self.query_one("#addons-status", Static).update(
                f"Installed {addon.name} ({addon.version})."
            )
            self.refresh_list()
            await self.on_change()
        finally:
            self.query_one("#addons-install", Button).disabled = False

    def _confirm_remove(self) -> None:
        addon = self._selected_addon()
        if addon is None:
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Remove Addon '{addon.name}'? Its files will be deleted.",
                confirmButtonText="Remove",
                cancelButtonText="Keep",
            ),
            lambda result: self._remove_confirmed(addon.id, result),
        )

    def _remove_confirmed(self, addon_id: str, result: ConfirmResult | None) -> None:
        if result is None or not result.confirmed:
            return
        self.query_one("#addons-remove", Button).disabled = True
        self.query_one("#addons-status", Static).update("Removing Addon files…")
        self.run_worker(self._remove(addon_id), group="addons-remove", exclusive=True)

    async def _remove(self, addon_id: str) -> None:
        try:
            await asyncio.to_thread(self.manager.remove, addon_id)
        except AddonError as error:
            self.logger.error(f"Could not remove Addon {addon_id}: {error}")
            self.query_one("#addons-status", Static).update(str(error))
        else:
            self.logger.info(f"Removed Addon {addon_id}.")
            self._selected_id = None
            self.query_one("#addons-status", Static).update(f"Removed Addon {addon_id}.")
            self.refresh_list()
            await self.on_change()

    def _selected_addon(self) -> InstalledAddon | None:
        return next(
            (addon for addon in self._installed if addon.id == self._selected_id),
            None,
        )

    def _update_remove_button(self) -> None:
        self.query_one("#addons-remove", Button).disabled = self._selected_addon() is None
