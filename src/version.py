"""Application release version and user-facing release notes."""

from typing import TypedDict


class VersionChanges(TypedDict, total=False):
    """Release notes for one application version."""

    date: str
    added: list[str]
    changed: list[str]
    fixed: list[str]


APP_VERSION = "0.3.0"

CHANGELOG: dict[str, VersionChanges] = {
    "0.3.0": {
        "date": "2026-11-07",
        "added": [
            "Change log.",
            "Netrunner theme.",
            "Level and title system.",
            "Ability to create files from the Notes view.",
            "Ability to update script description directly from the Scripts view.",
            "Resource usage and clock.",
        ],
        "changed": [
            "Improved scripts view layout.",
            "Consolidated opening and editing scripts into a single button.",
        ],
    },
}
