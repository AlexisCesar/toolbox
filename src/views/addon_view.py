"""Render one Addon using the versioned JSON Lines host contract."""

from __future__ import annotations

import asyncio
from typing import Any

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label, Static

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
        self._action_indexes: dict[str, int] = {}
        self._button_actions: dict[str, int] = {}
        self._action_button_index = 0
        self._layout_widget_index = 0
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
            layout = Vertical(id="addon-view-layout")
            layout.display = False
            yield layout
            yield Horizontal(id="addon-view-actions")

    def load_addon(self, addon: InstalledAddon) -> None:
        """Request an Addon's first view when its sidebar item is selected."""
        self._stop_refresh_timer()
        self._request_running = False
        self._addon = addon
        self._sequence += 1
        self.query_one("#addon-view-title", Label).update(Text(addon.name))
        body = self.query_one("#addon-view-body", Static)
        body.update("")
        body.display = True
        self.query_one("#addon-view-layout", Vertical).display = False
        self._actions = []
        self._action_indexes: dict[str, int] = {}
        self._button_actions = {}
        self._action_button_index = 0
        self.run_worker(
            self.query_one("#addon-view-actions", Horizontal).remove_children(),
            group="addon-view-actions",
            exclusive=True,
        )
        self.run_worker(
            self.query_one("#addon-view-layout", Vertical).remove_children(),
            group="addon-view-layout",
            exclusive=True,
        )
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
        action_index = self._button_actions.get(event.button.id)
        if action_index is None or action_index >= len(self._actions):
            self.logger.warn("Ignored an Addon action that is no longer available.")
            return
        action = self._actions[action_index]
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
        body = self.query_one("#addon-view-body", Static)
        layout_container = self.query_one("#addon-view-layout", Vertical)
        actions_bar = self.query_one("#addon-view-actions", Horizontal)
        self._actions = list(response.actions)
        self._action_indexes = {
            action.id: index for index, action in enumerate(self._actions)
        }
        self._button_actions = {}
        self._action_button_index = 0
        await actions_bar.remove_children()
        await layout_container.remove_children()

        if response.layout is None:
            body.display = True
            layout_container.display = False
            body.update(response.body)
            used_actions: set[str] = set()
        else:
            body.display = False
            layout_container.display = True
            used_actions = _layout_action_ids(response.layout)
            self._layout_widget_index = 0
            await layout_container.mount(
                *(self._build_layout_widget(block) for block in response.layout)
            )

        footer_actions = [
            (index, action)
            for index, action in enumerate(self._actions)
            if action.id not in used_actions
        ]
        if footer_actions:
            await actions_bar.mount(
                *(
                    self._make_action_button(index, action.label, "primary")
                    for index, action in footer_actions
                )
            )

        if response.notifications and self._addon is not None:
            self.logger.info(
                f"Addon {self._addon.id} requested "
                f"{len(response.notifications)} toast notification(s)."
            )
        for notification in response.notifications:
            self.notify(
                notification.message,
                title=notification.title,
                severity=notification.severity,
                timeout=notification.timeout,
                markup=False,
            )

    def _build_layout_widget(self, block: dict[str, Any]) -> Widget:
        """Build a native Textual widget from a validated layout block."""
        block_type = block["type"]
        if block_type == "text":
            style = Style(
                color=block.get("color"),
                bgcolor=block.get("background"),
                bold=block.get("bold", False),
                italic=block.get("italic", False),
                underline=block.get("underline", False),
            )
            return Static(
                Text(block["content"], style=style),
                markup=False,
                classes="addon-layout-text",
            )

        if block_type == "row":
            return Horizontal(
                *(self._build_layout_widget(child) for child in block["children"]),
                classes="addon-layout-row",
            )

        if block_type == "panel":
            return Vertical(
                Label(Text(block["title"]), classes="addon-layout-panel-title"),
                *(self._build_layout_widget(child) for child in block["children"]),
                classes="addon-layout-panel",
            )

        if block_type == "table":
            self._layout_widget_index += 1
            table = DataTable(
                id=f"addon-layout-table-{self._layout_widget_index}",
                classes="addon-layout-table",
                zebra_stripes=True,
                show_cursor=False,
                show_row_labels=False,
                cursor_type="none",
            )
            table.add_columns(*(Text(column) for column in block["columns"]))
            for row in block["rows"]:
                table.add_row(*(Text(cell) for cell in row))
            if "title" in block:
                title = Label(Text(block["title"]), classes="addon-layout-table-title")
                return Vertical(title, table, classes="addon-layout-table-container")
            return table

        if block_type == "button":
            action_id = block["action"]
            index = self._action_indexes[action_id]
            action = self._actions[index]
            return self._make_action_button(
                index,
                block.get("label", action.label),
                block.get("variant", "primary"),
            )

        raise AssertionError(f"Unsupported validated Addon layout block: {block_type}")

    def _make_action_button(self, action_index: int, label: str, variant: str) -> Button:
        button_id = f"addon-action-{self._action_button_index}"
        self._action_button_index += 1
        self._button_actions[button_id] = action_index
        return Button(
            Text(label),
            variant=variant,
            id=button_id,
            classes="addon-layout-button",
        )

    def _show_error(self, message: str) -> None:
        self._stop_refresh_timer()
        self.query_one("#addon-view-status", Static).update(message)
        self.query_one("#addon-view-body", Static).update("")
        self.query_one("#addon-view-body", Static).display = False
        self.query_one("#addon-view-layout", Vertical).display = False
        self._actions = []
        self._action_indexes = {}
        self._button_actions = {}
        self.run_worker(
            self.query_one("#addon-view-actions", Horizontal).remove_children(),
            group="addon-view-actions",
            exclusive=True,
        )
        self.run_worker(
            self.query_one("#addon-view-layout", Vertical).remove_children(),
            group="addon-view-layout",
            exclusive=True,
        )

    def _set_actions_disabled(self, disabled: bool) -> None:
        for button in self.query("#addon-view-actions Button"):
            button.disabled = disabled
        for button in self.query("#addon-view-layout Button"):
            button.disabled = disabled


def _layout_action_ids(layout: tuple[dict[str, Any], ...]) -> set[str]:
    """Return action ids placed directly in the Addon's layout."""
    action_ids: set[str] = set()
    for block in layout:
        if block["type"] == "button":
            action_ids.add(block["action"])
        elif block["type"] in {"row", "panel"}:
            action_ids.update(_layout_action_ids(block["children"]))
    return action_ids
