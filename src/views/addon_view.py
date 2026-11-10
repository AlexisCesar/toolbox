"""Render one Addon using the versioned JSON Lines host contract."""

from __future__ import annotations

import asyncio
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Label, Static

from src.utils.addon_manager import (
    AddonAction,
    AddonError,
    AddonManager,
    AddonViewState,
    InstalledAddon,
)
from src.utils.logger import Logger


class AddonView(Static):
    """Display a trusted Addon's text view and its declared actions."""

    def __init__(self, manager: AddonManager, logger: Logger, **kwargs) -> None:
        super().__init__(**kwargs)
        self.manager = manager
        self.logger = logger
        self._addon: InstalledAddon | None = None
        self._states: dict[str, dict[str, Any] | None] = {}
        self._actions: list[AddonAction] = []
        self._sequence = 0
        self._refresh_timer = None
        self._request_running = False

    @property
    def addon_id(self) -> str | None:
        """Return the id of the Addon currently selected in this view."""
        return self._addon.id if self._addon is not None else None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="addon-view-container"):
            yield Label("Addon", id="addon-view-title")
            yield Static("Select an Addon from the sidebar.", id="addon-view-status", markup=False)
            yield Static("", id="addon-view-body", markup=False)
            yield Horizontal(id="addon-view-actions")

    def load_addon(self, addon: InstalledAddon) -> None:
        """Request an Addon's first view when its sidebar item is selected."""
        self._stop_refresh_timer()
        self._request_running = False
        self._addon = addon
        self._sequence += 1
        self.query_one("#addon-view-title", Label).update(Text(addon.name))
        self.query_one("#addon-view-body", Static).update("")
        if not addon.available:
            self._show_error(addon.error or "This Addon is unavailable.")
            return
        self.query_one("#addon-view-status", Static).update("Loading Addon…")
        self._start_request("view", None, None, self._sequence)
        self._start_refresh_timer()

    def on_show(self) -> None:
        """Resume optional polling when the Addon's tab becomes visible."""
        self._start_refresh_timer()

    def on_hide(self) -> None:
        """Stop polling and ignore responses after leaving the Addon's tab."""
        self._stop_refresh_timer()
        if self._addon is not None:
            self._sequence += 1
            self._request_running = False

    def on_unmount(self) -> None:
        """Stop any Addon refresh timer when the view is removed."""
        self._stop_refresh_timer()

    def _start_request(
        self,
        method: str,
        action: str | None,
        state: dict[str, Any] | None,
        sequence: int,
    ) -> None:
        self._request_running = True
        self.run_worker(
            self._request(method, action, state, sequence),
            group="addon-view-request",
            exclusive=True,
        )

    def _start_refresh_timer(self) -> None:
        addon = self._addon
        if (
            addon is not None
            and addon.available
            and addon.refresh_interval_seconds is not None
            and self._refresh_timer is None
        ):
            self._refresh_timer = self.set_interval(
                addon.refresh_interval_seconds,
                self._refresh_current_view,
            )

    def _stop_refresh_timer(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

    def _refresh_current_view(self) -> None:
        addon = self._addon
        if addon is None or not addon.available or self._request_running:
            return
        self._start_request(
            "refresh",
            None,
            self._states.get(addon.id),
            self._sequence,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id is None or not event.button.id.startswith("addon-action-"):
            return
        event.stop()
        try:
            action_index = int(event.button.id.removeprefix("addon-action-"))
            action = self._actions[action_index]
        except (ValueError, IndexError):
            self.logger.warn("Ignored an Addon action that is no longer available.")
            return
        if self._addon is None or not self._addon.available:
            return
        if self._request_running:
            return
        self._start_request(
            "action",
            action.id,
            self._states.get(self._addon.id),
            self._sequence,
        )

    async def _request(
        self,
        method: str,
        action: str | None,
        state: dict[str, Any] | None,
        sequence: int,
    ) -> None:
        addon = self._addon
        if addon is None:
            return
        if method != "refresh":
            self._set_actions_disabled(True)
            self.query_one("#addon-view-status", Static).update(
                "Running Addon…" if method == "action" else "Loading Addon…"
            )
        try:
            response = await asyncio.to_thread(
                self.manager.request,
                addon.id,
                method,
                state=state,
                action=action,
            )
        except AddonError as error:
            if sequence == self._sequence and self._addon is not None and self._addon.id == addon.id:
                self.logger.warn(f"Addon {addon.id} request failed: {error}")
                self._show_error(str(error))
        else:
            if sequence == self._sequence and self._addon is not None and self._addon.id == addon.id:
                self._states[addon.id] = response.state
                await self._show_response(response)
        finally:
            if sequence == self._sequence:
                self._request_running = False
                if method != "refresh":
                    self._set_actions_disabled(False)

    async def _show_response(self, response: AddonViewState) -> None:
        self.query_one("#addon-view-title", Label).update(Text(response.title))
        self.query_one("#addon-view-status", Static).update("")
        self.query_one("#addon-view-body", Static).update(response.body)
        actions_bar = self.query_one("#addon-view-actions", Horizontal)
        updated_actions = list(response.actions)
        if updated_actions != self._actions:
            await actions_bar.remove_children()
            self._actions = updated_actions
            if self._actions:
                await actions_bar.mount(
                    *(
                        Button(Text(action.label), variant="primary", id=f"addon-action-{index}")
                        for index, action in enumerate(self._actions)
                    )
                )

    def _show_error(self, message: str) -> None:
        self._stop_refresh_timer()
        self.query_one("#addon-view-status", Static).update(message)
        self.query_one("#addon-view-body", Static).update("")
        self._actions = []
        self.run_worker(
            self.query_one("#addon-view-actions", Horizontal).remove_children(),
            group="addon-view-actions",
            exclusive=True,
        )

    def _set_actions_disabled(self, disabled: bool) -> None:
        for button in self.query("#addon-view-actions Button"):
            button.disabled = disabled
