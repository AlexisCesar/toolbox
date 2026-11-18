"""Modal progress and result screen for updating Toolbox."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from src.utils.logger import Logger
from src.utils.update_manager import ToolboxUpdater, ToolboxUpdateError


class UpdateDialog(ModalScreen[None]):
    """Run the update steps while keeping the rest of the application blocked."""

    BINDINGS = [
        ("escape", "ignore_key", ""),
        ("q", "ignore_key", ""),
    ]

    def __init__(self, updater: ToolboxUpdater, logger: Logger) -> None:
        super().__init__()
        self.updater = updater
        self.logger = logger
        self._busy = True
        self._can_return_to_app = False

    def compose(self) -> ComposeResult:
        with Vertical(id="toolbox-update-dialog"):
            yield Static("Update Toolbox", id="toolbox-update-title")
            yield Static(
                "Checking this Toolbox installation…",
                id="toolbox-update-status",
                markup=False,
            )
            yield Static("", id="toolbox-update-error", markup=False)
            with Horizontal(id="toolbox-update-actions"):
                yield Button(
                    "Updating…",
                    variant="primary",
                    id="toolbox-update-action",
                    disabled=True,
                )

    def on_mount(self) -> None:
        self.logger.info("Started the Toolbox update.")
        self.run_worker(
            self._perform_update(),
            group="toolbox-update",
            exclusive=True,
        )

    async def _perform_update(self) -> None:
        try:
            plan = await asyncio.to_thread(self.updater.prepare)
            self.query_one("#toolbox-update-status", Static).update(
                f"Fetching updates for branch '{plan.branch}'…"
            )
            self.logger.info(f"Fetching origin/{plan.branch} for the Toolbox update.")
            await asyncio.to_thread(self.updater.fetch, plan)

            self.query_one("#toolbox-update-status", Static).update(
                f"Applying fast-forward updates from origin/{plan.branch}…"
            )
            await asyncio.to_thread(self.updater.pull, plan)

            self.query_one("#toolbox-update-status", Static).update(
                "Synchronizing dependencies with uv…"
            )
            await asyncio.to_thread(self.updater.sync, plan)
        except ToolboxUpdateError as error:
            self.logger.error(f"Toolbox update failed during {error.stage}: {error}")
            self._busy = False
            self._can_return_to_app = not error.checkout_may_have_changed
            status = self.query_one("#toolbox-update-status", Static)
            if self._can_return_to_app:
                status.update(
                    "The update did not change the checkout. "
                    "Review the error and try again later."
                )
                action_text = "Return to Toolbox"
            else:
                status.update(
                    "The update may have changed files or dependencies. Close Toolbox and inspect the installation."
                )
                action_text = "Close Toolbox"
            self.query_one("#toolbox-update-error", Static).update(str(error))
            self._set_action(action_text, disabled=False)
            return

        self._busy = False
        self.logger.info("Toolbox update completed successfully.")
        self.query_one("#toolbox-update-status", Static).update(
            "Update complete. Restart Toolbox to finish applying the changes."
        )
        self._set_action("Restart Toolbox", disabled=False)

    def _set_action(self, label: str, *, disabled: bool) -> None:
        action = self.query_one("#toolbox-update-action", Button)
        action.label = label
        action.disabled = disabled

    def action_ignore_key(self) -> None:
        """Keep the progress and result screen open until its action is chosen."""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "toolbox-update-action" or self._busy:
            return
        event.stop()
        if self._can_return_to_app:
            self.dismiss()
            return
        self.app.exit()
