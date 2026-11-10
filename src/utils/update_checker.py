"""Check the project's GitHub releases without blocking the UI."""

import json
import re
from urllib.request import Request, urlopen


LATEST_RELEASE_URL = "https://api.github.com/repos/AlexisCesar/toolbox/releases/latest"
REQUEST_TIMEOUT = 3
MAX_RESPONSE_BYTES = 1024 * 1024
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$", re.IGNORECASE)


class UpdateCheckError(Exception):
    """Raised when GitHub does not return a usable release response."""


def _parse_version(version: str) -> tuple[int, int, int]:
    """Parse a stable three-part release version, allowing a leading v."""
    match = VERSION_PATTERN.fullmatch(version.strip())
    if match is None:
        raise ValueError(f"Unsupported release version: {version!r}")
    return tuple(int(part) for part in match.groups())


def check_for_update(current_version: str) -> str | None:
    """Return the latest stable release version when it is newer than current."""
    try:
        current = _parse_version(current_version)
    except (AttributeError, ValueError) as error:
        raise UpdateCheckError(f"Invalid installed version: {error}") from error

    request = Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ToolboxTUI",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except OSError as error:
        raise UpdateCheckError(str(error) or error.__class__.__name__) from error

    if len(body) > MAX_RESPONSE_BYTES:
        raise UpdateCheckError("GitHub release response exceeded the size limit.")

    try:
        release = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateCheckError("GitHub returned an invalid release response.") from error

    tag_name = release.get("tag_name") if isinstance(release, dict) else None
    if not isinstance(tag_name, str):
        raise UpdateCheckError("GitHub release response did not include a version tag.")

    version = tag_name.removeprefix("v").removeprefix("V")
    try:
        latest = _parse_version(version)
    except ValueError as error:
        raise UpdateCheckError(f"Unsupported GitHub release tag: {tag_name!r}") from error

    return version if latest > current else None
