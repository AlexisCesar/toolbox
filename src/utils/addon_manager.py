"""Install, validate, and communicate with external Toolbox Addons."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from src.utils.todo_store import default_todo_path


ADDON_MANIFEST = "toolbox-addon.json"
ADDON_API_VERSION = 1
ADDON_RESPONSE_LIMIT = 512_000
ADDON_BODY_LIMIT = 100_000
ADDON_STATE_LIMIT = 100_000
ADDON_REQUEST_TIMEOUT = 15
ADDON_INSTALL_TIMEOUT = 120
ADDON_LAYOUT_BLOCK_LIMIT = 100
ADDON_LAYOUT_DEPTH_LIMIT = 5
ADDON_NOTIFICATION_LIMIT = 5
ADDON_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ACTION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
LAYOUT_COLOR_PATTERN = re.compile(r"^(#[0-9a-fA-F]{6}|[a-zA-Z][a-zA-Z0-9_]*)$")
SSH_URL_PATTERN = re.compile(r"^[\w.-]+@[\w.-]+:[\w./-]+(?:\.git)?$")
LAYOUT_COLORS = {
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright_black", "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_magenta", "bright_cyan", "bright_white", "gray", "grey",
}
BUTTON_VARIANTS = {"default", "primary", "success", "warning", "error"}
NOTIFICATION_SEVERITIES = {"information", "warning", "error"}


class AddonError(ValueError):
    """Raised when an Addon cannot be installed or used safely."""


@dataclass(frozen=True, slots=True)
class AddonManifestData:
    """Validated metadata declared by one Addon repository."""

    id: str
    name: str
    version: str
    icon: str
    command: tuple[str, ...]
    refresh_interval_seconds: float | None


@dataclass(frozen=True, slots=True)
class InstalledAddon:
    """One installed Addon, including metadata errors for repair and removal."""

    id: str
    name: str
    version: str
    icon: str
    path: Path
    command: tuple[str, ...] = ()
    error: str | None = None
    refresh_interval_seconds: float | None = None

    @property
    def available(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class AddonAction:
    """A validated button declared by an Addon's current view."""

    id: str
    label: str


@dataclass(frozen=True, slots=True)
class AddonNotification:
    """A toast requested by an Addon in its latest response."""

    title: str
    message: str
    severity: str
    timeout: float | None


@dataclass(frozen=True, slots=True)
class AddonViewState:
    """Content returned by an Addon process."""

    title: str
    body: str
    state: dict[str, Any] | None
    actions: tuple[AddonAction, ...]
    layout: tuple[dict[str, Any], ...] | None = None
    notifications: tuple[AddonNotification, ...] = ()


def default_addons_dir() -> Path:
    """Return the per-user directory where Addon repositories are installed."""
    return default_todo_path().parent / "addons"


def validate_repository_url(value: str) -> str:
    """Allow HTTPS and SSH Git URLs without embedded passwords."""
    url = value.strip()
    if not url:
        raise AddonError("Enter a Git repository URL.")
    if SSH_URL_PATTERN.fullmatch(url):
        return url

    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "ssh"} or not parsed.hostname:
        raise AddonError("Use an HTTPS or SSH Git repository URL.")
    if parsed.password is not None:
        raise AddonError("Do not put passwords or access tokens in the URL. Use Git's credential manager.")
    if parsed.query or parsed.fragment:
        raise AddonError("The repository URL cannot contain a query or fragment.")
    return url


def parse_addon_manifest(value: object) -> AddonManifestData:
    """Validate the public manifest contract without importing Addon code."""
    if not isinstance(value, dict):
        raise AddonError("The Addon manifest must contain a JSON object.")
    api_version = value.get("api_version")
    if (
        not isinstance(api_version, int)
        or isinstance(api_version, bool)
        or api_version != ADDON_API_VERSION
    ):
        raise AddonError(f"Unsupported Addon API version; expected {ADDON_API_VERSION}.")

    addon_id = value.get("id")
    name = value.get("name")
    version = value.get("version")
    icon = value.get("icon", "🧩")
    command = value.get("command")
    refresh_interval = value.get("refresh_interval_seconds")
    if not isinstance(addon_id, str) or not ADDON_ID_PATTERN.fullmatch(addon_id):
        raise AddonError("The Addon id must use lowercase letters, digits, and hyphens, and start with a letter.")
    if not _valid_text(name, maximum=80):
        raise AddonError("The Addon name must be non-empty text of at most 80 characters.")
    if not _valid_text(version, maximum=40):
        raise AddonError("The Addon version must be non-empty text of at most 40 characters.")
    if not _valid_text(icon, maximum=8):
        raise AddonError("The Addon icon must be text of at most 8 characters.")
    if (
        not isinstance(command, list)
        or not command
        or len(command) > 32
        or any(not _valid_text(part, maximum=500) for part in command)
    ):
        raise AddonError("The Addon command must be a non-empty array of text arguments.")
    if refresh_interval is not None and (
        not isinstance(refresh_interval, (int, float))
        or isinstance(refresh_interval, bool)
        or not 1 <= refresh_interval <= 3_600
    ):
        raise AddonError(
            "The Addon refresh interval must be between 1 and 3600 seconds, or omitted."
        )

    return AddonManifestData(
        addon_id,
        name.strip(),
        version.strip(),
        icon,
        tuple(part.strip() for part in command),
        float(refresh_interval) if refresh_interval is not None else None,
    )


class AddonManager:
    """Manage installed repositories and one-shot JSON Lines requests."""

    def __init__(self, addons_dir: Path | None = None) -> None:
        self.addons_dir = Path(addons_dir) if addons_dir is not None else default_addons_dir()

    def list_installed(self) -> list[InstalledAddon]:
        """Return installed Addons, retaining invalid folders so they can be removed."""
        if not self.addons_dir.is_dir():
            return []
        installed: list[InstalledAddon] = []
        try:
            entries = sorted(self.addons_dir.iterdir(), key=lambda path: path.name.casefold())
        except OSError as error:
            raise AddonError(f"Could not read the Addons directory: {error}") from error

        for entry in entries:
            if entry.name.startswith(".install-") or entry.is_symlink() or not entry.is_dir():
                continue
            try:
                manifest = self._read_manifest(entry)
                if manifest.id != entry.name:
                    raise AddonError("The manifest id does not match its installed directory.")
            except AddonError as error:
                installed.append(
                    InstalledAddon(
                        id=entry.name,
                        name=f"Unavailable Addon ({entry.name})",
                        version="—",
                        icon="⚠️",
                        path=entry,
                        error=str(error),
                    )
                )
                continue
            installed.append(
                InstalledAddon(
                    id=manifest.id,
                    name=manifest.name,
                    version=manifest.version,
                    icon=manifest.icon,
                    path=entry,
                    command=manifest.command,
                    refresh_interval_seconds=manifest.refresh_interval_seconds,
                )
            )
        return installed

    def install(self, repository_url: str) -> InstalledAddon:
        """Clone, validate, and atomically install an Addon repository."""
        url = validate_repository_url(repository_url)
        try:
            self.addons_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise AddonError(f"Could not create the Addons directory: {error}") from error

        try:
            with tempfile.TemporaryDirectory(prefix=".install-", dir=self.addons_dir) as temporary:
                checkout = Path(temporary) / "checkout"
                try:
                    result = subprocess.run(
                        ["git", "clone", "--depth", "1", "--", url, str(checkout)],
                        capture_output=True,
                        text=True,
                        timeout=ADDON_INSTALL_TIMEOUT,
                        check=False,
                        creationflags=_no_console_window(),
                    )
                except FileNotFoundError as error:
                    raise AddonError("Git was not found. Install Git and try again.") from error
                except subprocess.TimeoutExpired as error:
                    raise AddonError("Git clone timed out. Check the repository and network connection.") from error
                except OSError as error:
                    raise AddonError(f"Could not start Git: {error}") from error
                if result.returncode != 0:
                    raise AddonError("Git could not clone the repository. Check its URL and access permissions.")

                manifest = self._read_manifest(checkout)
                destination = self.addons_dir / manifest.id
                if destination.exists() or destination.is_symlink():
                    raise AddonError(f"Addon '{manifest.id}' is already installed.")
                checkout.rename(destination)
        except OSError as error:
            raise AddonError(f"Could not install the Addon: {error}") from error

        return InstalledAddon(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            icon=manifest.icon,
            path=destination,
            command=manifest.command,
            refresh_interval_seconds=manifest.refresh_interval_seconds,
        )

    def remove(self, addon_id: str) -> None:
        """Remove an installed Addon directory after checking its boundary."""
        if not isinstance(addon_id, str) or not ADDON_ID_PATTERN.fullmatch(addon_id):
            raise AddonError("The installed Addon id is invalid.")
        root = self.addons_dir.resolve()
        target = self.addons_dir / addon_id
        try:
            if target.is_symlink() or not target.is_dir():
                raise AddonError(f"Addon '{addon_id}' is not installed.")
            if target.resolve().parent != root:
                raise AddonError("The Addon directory is outside the configured Addons folder.")
            shutil.rmtree(target)
        except OSError as error:
            raise AddonError(f"Could not remove Addon '{addon_id}': {error}") from error

    def request(
        self,
        addon_id: str,
        method: str,
        *,
        state: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> AddonViewState:
        """Run one Addon request and validate its single JSON Lines response."""
        if method not in {"view", "action", "refresh"}:
            raise AddonError("Unsupported Addon request method.")
        if method == "action" and (not isinstance(action, str) or not ACTION_ID_PATTERN.fullmatch(action)):
            raise AddonError("The requested Addon action is invalid.")
        if state is not None and not isinstance(state, dict):
            raise AddonError("Addon request state must be a JSON object or null.")
        addon = next((item for item in self.list_installed() if item.id == addon_id), None)
        if addon is None or not addon.available:
            raise AddonError(f"Addon '{addon_id}' is unavailable.")

        request_id = str(uuid4())
        request: dict[str, Any] = {
            "protocol": ADDON_API_VERSION,
            "id": request_id,
            "method": method,
            "state": state,
        }
        if action is not None:
            request["action"] = action
        try:
            request_text = json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n"
            if len(request_text.encode("utf-8")) > ADDON_STATE_LIMIT + 2_000:
                raise AddonError("The Addon state is too large to send.")
            result = subprocess.run(
                list(addon.command),
                cwd=addon.path,
                input=request_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=ADDON_REQUEST_TIMEOUT,
                check=False,
                creationflags=_no_console_window(),
            )
        except FileNotFoundError as error:
            raise AddonError("The Addon runtime was not found. Check its command and install the required runtime.") from error
        except subprocess.TimeoutExpired as error:
            raise AddonError("The Addon did not respond before the request timed out.") from error
        except OSError as error:
            raise AddonError(f"Could not start the Addon: {error}") from error

        if result.returncode != 0:
            raise AddonError("The Addon process exited with an error. Check its diagnostics in the Addon repository.")
        if len(result.stdout.encode("utf-8")) > ADDON_RESPONSE_LIMIT:
            raise AddonError("The Addon response is too large.")
        try:
            response = json.loads(result.stdout)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise AddonError("The Addon must write one JSON response line to stdout.") from error
        return _parse_response(response, request_id)

    def _read_manifest(self, directory: Path) -> AddonManifestData:
        manifest_path = directory / ADDON_MANIFEST
        try:
            if manifest_path.is_symlink():
                raise AddonError("The Addon manifest cannot be a symbolic link.")
            raw = manifest_path.read_bytes()
        except FileNotFoundError as error:
            raise AddonError(f"The repository is missing {ADDON_MANIFEST}.") from error
        except OSError as error:
            raise AddonError(f"Could not read {ADDON_MANIFEST}: {error}") from error
        if len(raw) > 64_000:
            raise AddonError("The Addon manifest is too large.")
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise AddonError(f"{ADDON_MANIFEST} must contain valid UTF-8 JSON.") from error
        return parse_addon_manifest(value)


def _valid_text(value: object, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= maximum
        and not any(ord(character) < 32 for character in value)
    )


def _parse_response(value: object, request_id: str) -> AddonViewState:
    if not isinstance(value, dict):
        raise AddonError("The Addon response must be a JSON object.")
    if value.get("protocol") != ADDON_API_VERSION or value.get("id") != request_id:
        raise AddonError("The Addon response has an invalid protocol version or request id.")
    view = value.get("view")
    if not isinstance(view, dict):
        raise AddonError("The Addon response must contain a view object.")

    title = view.get("title")
    body = view.get("body")
    has_layout = "layout" in view
    layout: tuple[dict[str, Any], ...] | None = None
    state = view.get("state")
    actions = view.get("actions", [])
    if not _valid_text(title, maximum=120):
        raise AddonError("The Addon view title must be non-empty text of at most 120 characters.")
    if has_layout:
        if "body" in view:
            raise AddonError("Use either the Addon view 'body' or 'layout', not both.")
    elif not _valid_body(body, maximum=ADDON_BODY_LIMIT):
        raise AddonError("The Addon view body must be text of at most 100,000 characters.")
    if state is not None:
        if not isinstance(state, dict):
            raise AddonError("Addon view state must be a JSON object or null.")
        try:
            state_size = len(json.dumps(state, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise AddonError("Addon view state must contain JSON-compatible values.") from error
        if state_size > ADDON_STATE_LIMIT:
            raise AddonError("Addon view state is too large.")
    if not isinstance(actions, list) or len(actions) > 20:
        raise AddonError("Addon actions must be an array containing at most 20 items.")

    parsed_actions: list[AddonAction] = []
    used_ids: set[str] = set()
    for item in actions:
        if not isinstance(item, dict):
            raise AddonError("Each Addon action must be a JSON object.")
        action_id = item.get("id")
        label = item.get("label")
        if not isinstance(action_id, str) or not ACTION_ID_PATTERN.fullmatch(action_id):
            raise AddonError("Addon action ids must contain letters, digits, underscores, or hyphens.")
        if action_id in used_ids:
            raise AddonError("Addon action ids must be unique within a view.")
        if not _valid_text(label, maximum=80):
            raise AddonError("Addon action labels must be non-empty text of at most 80 characters.")
        used_ids.add(action_id)
        parsed_actions.append(AddonAction(action_id, label.strip()))

    if has_layout:
        layout = _parse_layout(view.get("layout"), used_ids)

    notifications = _parse_notifications(value.get("notifications", []), title.strip())
    return AddonViewState(
        title.strip(),
        body if isinstance(body, str) else "",
        state,
        tuple(parsed_actions),
        layout,
        notifications,
    )


def _valid_body(value: object, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= maximum
        and not any(ord(character) < 32 and character not in "\t\n\r" for character in value)
    )


def _layout_text(value: object, *, field: str, maximum: int, allow_empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (not allow_empty and not value.strip())
        or any(ord(character) < 32 and character not in "\t\n\r" for character in value)
    ):
        raise AddonError(
            f"Addon layout '{field}' must be plain text of at most {maximum} characters."
        )
    return value


def _reject_unknown_layout_fields(block: dict[str, Any], allowed: set[str]) -> None:
    unknown = set(block) - allowed
    if unknown:
        field = sorted(unknown)[0]
        raise AddonError(f"Unknown field '{field}' in Addon layout block '{block.get('type')}'.")


def _parse_layout(
    value: object,
    action_ids: set[str],
) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or not value or len(value) > 40:
        raise AddonError("Addon view 'layout' must be a non-empty array of at most 40 blocks.")
    block_count = [0]
    return tuple(
        _parse_layout_block(block, action_ids, block_count, depth=1)
        for block in value
    )


def _parse_layout_block(
    value: object,
    action_ids: set[str],
    block_count: list[int],
    *,
    depth: int,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AddonError("Each Addon layout block must be a JSON object.")
    block_count[0] += 1
    if block_count[0] > ADDON_LAYOUT_BLOCK_LIMIT:
        raise AddonError(
            f"Addon layout cannot contain more than {ADDON_LAYOUT_BLOCK_LIMIT} blocks."
        )
    if depth > ADDON_LAYOUT_DEPTH_LIMIT:
        raise AddonError(f"Addon layout nesting cannot exceed {ADDON_LAYOUT_DEPTH_LIMIT} levels.")

    block_type = value.get("type")
    if block_type == "text":
        _reject_unknown_layout_fields(
            value,
            {"type", "content", "color", "background", "bold", "italic", "underline"},
        )
        content = _layout_text(value.get("content"), field="content", maximum=10_000)
        parsed: dict[str, Any] = {"type": "text", "content": content}
        for field in ("color", "background"):
            if field in value:
                color = value[field]
                if (
                    not isinstance(color, str)
                    or not LAYOUT_COLOR_PATTERN.fullmatch(color)
                    or (not color.startswith("#") and color.lower() not in LAYOUT_COLORS)
                ):
                    raise AddonError(
                        f"Addon layout '{field}' must be a supported color name or #RRGGBB value."
                    )
                parsed[field] = color if color.startswith("#") else color.lower()
        for field in ("bold", "italic", "underline"):
            if field in value:
                if not isinstance(value[field], bool):
                    raise AddonError(f"Addon layout '{field}' must be true or false.")
                parsed[field] = value[field]
        return parsed

    if block_type in {"panel", "row"}:
        allowed = {"type", "children"} | ({"title"} if block_type == "panel" else set())
        _reject_unknown_layout_fields(value, allowed)
        title = None
        if block_type == "panel":
            title = _layout_text(value.get("title"), field="title", maximum=80)
        children_value = value.get("children")
        if not isinstance(children_value, list) or not children_value or len(children_value) > 20:
            raise AddonError("Addon panel and row blocks need 1 to 20 child blocks.")
        if block_type == "row" and len(children_value) < 2:
            raise AddonError("Addon row blocks need at least 2 child blocks.")
        children = tuple(
            _parse_layout_block(child, action_ids, block_count, depth=depth + 1)
            for child in children_value
        )
        parsed = {"type": block_type, "children": children}
        if title is not None:
            parsed["title"] = title
        return parsed

    if block_type == "table":
        _reject_unknown_layout_fields(value, {"type", "title", "columns", "rows"})
        title = None
        if "title" in value:
            title = _layout_text(value["title"], field="title", maximum=80)
        columns = value.get("columns")
        rows = value.get("rows")
        if not isinstance(columns, list) or not 1 <= len(columns) <= 12:
            raise AddonError("Addon table 'columns' must contain 1 to 12 column names.")
        parsed_columns = tuple(
            _layout_text(column, field="column name", maximum=80)
            for column in columns
        )
        if not isinstance(rows, list) or len(rows) > 100:
            raise AddonError("Addon table 'rows' must contain at most 100 rows.")
        parsed_rows: list[tuple[str, ...]] = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(parsed_columns):
                raise AddonError("Every Addon table row must match the number of columns.")
            parsed_rows.append(
                tuple(
                    _layout_text(cell, field="table cell", maximum=1_000, allow_empty=True)
                    for cell in row
                )
            )
        parsed = {
            "type": "table",
            "columns": parsed_columns,
            "rows": tuple(parsed_rows),
        }
        if title is not None:
            parsed["title"] = title
        return parsed

    if block_type == "button":
        _reject_unknown_layout_fields(value, {"type", "action", "label", "variant"})
        action_id = value.get("action")
        if not isinstance(action_id, str) or action_id not in action_ids:
            raise AddonError("Addon layout buttons must reference an id declared in 'actions'.")
        parsed = {"type": "button", "action": action_id}
        if "label" in value:
            parsed["label"] = _layout_text(value["label"], field="label", maximum=80)
        if "variant" in value:
            variant = value["variant"]
            if not isinstance(variant, str) or variant not in BUTTON_VARIANTS:
                raise AddonError(
                    "Addon layout button 'variant' must be default, primary, success, "
                    "warning, or error."
                )
            parsed["variant"] = variant
        return parsed

    raise AddonError("Addon layout block 'type' must be text, panel, row, table, or button.")


def _parse_notifications(value: object, default_title: str) -> tuple[AddonNotification, ...]:
    if not isinstance(value, list) or len(value) > ADDON_NOTIFICATION_LIMIT:
        raise AddonError(
            f"Addon 'notifications' must be an array of at most {ADDON_NOTIFICATION_LIMIT} items."
        )
    notifications: list[AddonNotification] = []
    for item in value:
        if not isinstance(item, dict):
            raise AddonError("Each Addon notification must be a JSON object.")
        unknown = set(item) - {"title", "message", "severity", "timeout"}
        if unknown:
            raise AddonError(f"Unknown Addon notification field '{sorted(unknown)[0]}'.")
        title = item.get("title", default_title)
        message = item.get("message")
        severity = item.get("severity", "information")
        timeout = item.get("timeout")
        if not _valid_text(title, maximum=80):
            raise AddonError(
                "Addon notification 'title' must be non-empty text of at most 80 characters."
            )
        if not _valid_text(message, maximum=500):
            raise AddonError(
                "Addon notification 'message' must be non-empty text of at most 500 characters."
            )
        if not isinstance(severity, str) or severity not in NOTIFICATION_SEVERITIES:
            raise AddonError(
                "Addon notification 'severity' must be information, warning, or error."
            )
        if timeout is not None and (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not 1 <= timeout <= 30
        ):
            raise AddonError("Addon notification 'timeout' must be between 1 and 30 seconds.")
        notifications.append(
            AddonNotification(
                title.strip(),
                message.strip(),
                severity,
                float(timeout) if timeout is not None else None,
            )
        )
    return tuple(notifications)


def _no_console_window() -> int:
    """Keep Addon subprocesses from opening a console on Windows."""
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0
