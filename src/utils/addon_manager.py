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
ADDON_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ACTION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SSH_URL_PATTERN = re.compile(r"^[\w.-]+@[\w.-]+:[\w./-]+(?:\.git)?$")


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
class AddonViewState:
    """Content returned by an Addon process."""

    title: str
    body: str
    state: dict[str, Any] | None
    actions: tuple[AddonAction, ...]


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
    state = view.get("state")
    actions = view.get("actions", [])
    if not _valid_text(title, maximum=120):
        raise AddonError("The Addon view title must be non-empty text of at most 120 characters.")
    if (
        not isinstance(body, str)
        or len(body) > ADDON_BODY_LIMIT
        or any(ord(character) < 32 and character not in "\t\n\r" for character in body)
    ):
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

    return AddonViewState(title.strip(), body, state, tuple(parsed_actions))


def _no_console_window() -> int:
    """Keep Addon subprocesses from opening a console on Windows."""
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0
