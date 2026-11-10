"""Application release version and user-facing release notes."""

from typing import TypedDict


class VersionChanges(TypedDict, total=False):
    """Release notes for one application version."""

    date: str
    added: list[str]
    changed: list[str]
    fixed: list[str]


APP_VERSION = "0.4.0"

CHANGELOG: dict[str, VersionChanges] = {
    "0.4.0": {
        "date": "2026-11-10",
        "added": [
            "Calendar view with iCal subscription.",
            "Version selector to browse release notes.",
            "Export and import configuration.",
            "Run SQL Server scripts directly from the Scripts view.",
            "Addons support.",
            "Check GitHub for newer releases.",
        ],
        "changed": [
            "Added the date and available battery status to the header.",
            "Improved the TODO progress bar by labeling and thickening it.",
            "Show an Admin marker in the header when Toolbox runs with administrator or root privileges.",
            "My Projects now shows one Open action per solution and lets you choose an installed IDE or editor (more editors identified now).",
        ],
        "fixed": [
            "Projects with solution files sometimes would not show the \"Open in Visual Studio\" option.",
        ],
    },
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
