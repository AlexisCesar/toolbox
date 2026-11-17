"""Modal dialog for browsing Toolbox's recommended Addons."""

from __future__ import annotations

import asyncio

import pyperclip
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from src.utils.logger import Logger
from src.utils.recommended_addons import (
    RecommendedAddon,
    RecommendedAddonsCatalog,
    RecommendedAddonsError,
    RecommendedAddonsResult,
)


class RecommendedAddonsDialog(ModalScreen[None]):
    """Display the recommended Addons catalog and copy repository URLs."""

    def __init__(
        self,
        catalog: RecommendedAddonsCatalog,
        logger: Logger,
    ) -> None:
        super().__init__()
        self.catalog = catalog
        self.logger = logger
        self._addons: tuple[RecommendedAddon, ...] = ()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Recommended Addons", id="recommended-addons-title"),
            Static("Loading recommendations…", id="recommended-addons-status", markup=False),
            VerticalScroll(id="recommended-addons-list"),
            Horizontal(
                Button("Close", variant="primary", id="recommended-addons-close"),
                id="recommended-addons-actions",
            ),
            id="recommended-addons-dialog",
        )

    def on_mount(self) -> None:
        self.run_worker(
            self._load_catalog(),
            group="recommended-addons-load",
            exclusive=True,
        )

    async def _load_catalog(self) -> None:
        try:
            result = await asyncio.to_thread(self.catalog.load)
        except RecommendedAddonsError as error:
            self.logger.error(f"Could not load recommended Addons: {error}")
            self.query_one("#recommended-addons-status", Static).update(
                "Could not load recommendations. Check your network connection and try again later."
            )
            return

        self._addons = result.addons
        status = self.query_one("#recommended-addons-status", Static)
        if result.stale:
            status.update("Showing the saved list because GitHub could not be reached.")
            self.logger.warn(result.warning or "Showing stale recommended Addons cache.")
        elif result.from_cache:
            status.update("Loaded from local cache. The list refreshes every 24 hours.")
            self.logger.info("Loaded recommended Addons from the local cache.")
        else:
            status.update("Loaded from GitHub. The list is cached for 24 hours.")
            self.logger.info("Loaded recommended Addons from GitHub.")

        if result.warning and not result.stale:
            self.logger.warn(result.warning)
        if not self._addons:
            status.update("There are no recommended Addons yet.")
            return

        cards = [self._create_addon_card(index, addon) for index, addon in enumerate(self._addons)]
        await self.query_one("#recommended-addons-list", VerticalScroll).mount(*cards)

    @staticmethod
    def _create_addon_card(index: int, addon: RecommendedAddon) -> Vertical:
        repository = Text(addon.repository, style=f"link {addon.repository} underline")
        return Vertical(
            Static(addon.name, classes="recommended-addon-name", markup=False),
            Static(f"Category: {addon.category}", classes="recommended-addon-category", markup=False),
            Static(addon.description, classes="recommended-addon-description", markup=False),
            Horizontal(
                Static(
                    repository,
                    classes="recommended-addon-repository",
                    markup=False,
                ),
                Button("Copy repository", id=f"recommended-addon-copy-{index}"),
                classes="recommended-addon-link-row",
            ),
            classes="recommended-addon-card",
            id=f"recommended-addon-card-{index}",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "recommended-addons-close":
            event.stop()
            self.dismiss()
            return
        if not button_id.startswith("recommended-addon-copy-"):
            return
        event.stop()
        try:
            index = int(button_id.removeprefix("recommended-addon-copy-"))
            addon = self._addons[index]
            pyperclip.copy(addon.repository)
        except (IndexError, ValueError):
            self.logger.error("Could not identify the recommended Addon to copy.")
            return
        except (OSError, pyperclip.PyperclipException) as error:
            self.logger.error(f"Could not copy a recommended Addon repository URL: {error}")
            self.query_one("#recommended-addons-status", Static).update(
                "Could not copy the repository URL to the clipboard."
            )
            self.app.notify(
                "Could not copy the repository URL to the clipboard.",
                title="Recommended Addons",
                severity="error",
            )
            return

        self.logger.info(f"Copied the {addon.name} repository URL to the clipboard.")
        self.query_one("#recommended-addons-status", Static).update(
            f"Copied the {addon.name} repository URL to the clipboard."
        )
        self.app.notify(
            f"{addon.name} repository URL copied to the clipboard.",
            title="Recommended Addons",
            severity="information",
        )
