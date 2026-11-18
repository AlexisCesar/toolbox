"""Safely update a Toolbox checkout using its configured Git branch."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


COMMAND_TIMEOUT = 180
MAX_ERROR_OUTPUT = 4000
_CREDENTIALS_IN_URL = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)


@dataclass(frozen=True)
class UpdatePlan:
    """Validated checkout and remote branch to update."""

    repository_root: Path
    branch: str


class ToolboxUpdateError(RuntimeError):
    """An update step failed, with whether the checkout may have changed."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        checkout_may_have_changed: bool = False,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.checkout_may_have_changed = checkout_may_have_changed


class ToolboxUpdater:
    """Validate and update a Toolbox Git checkout without destructive commands."""

    def prepare(self) -> UpdatePlan:
        """Validate the running directory, its branch, origin and clean state."""
        cwd = Path.cwd().resolve()
        root_output = self._run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            stage="repository check",
        )
        repository_root = Path(root_output.strip()).resolve()
        if repository_root != cwd:
            raise ToolboxUpdateError(
                "Run Toolbox from the root of its Git repository before updating.",
                stage="repository check",
            )
        markers = ("main.py", "pyproject.toml", "uv.lock")
        if not all((repository_root / marker).is_file() for marker in markers):
            raise ToolboxUpdateError(
                "The current Git repository does not look like a Toolbox installation.",
                stage="repository check",
            )

        branch = self._run(
            ["git", "branch", "--show-current"],
            cwd=repository_root,
            stage="branch check",
        ).strip()
        if not branch:
            raise ToolboxUpdateError(
                "Toolbox is in a detached HEAD state and cannot be updated safely.",
                stage="branch check",
            )

        try:
            upstream = self._run(
                [
                    "git",
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{upstream}",
                ],
                cwd=repository_root,
                stage="branch check",
            ).strip()
        except ToolboxUpdateError as error:
            raise ToolboxUpdateError(
                f"Branch '{branch}' has no configured remote upstream. Configure it to "
                f"'origin/{branch}' before updating.",
                stage="branch check",
            ) from error
        expected_upstream = f"origin/{branch}"
        if upstream != expected_upstream:
            raise ToolboxUpdateError(
                f"Branch '{branch}' must track '{expected_upstream}' to update Toolbox safely. "
                f"Its configured upstream is '{upstream or 'none'}'.",
                stage="branch check",
            )

        self._run(
            ["git", "remote", "get-url", "origin"],
            cwd=repository_root,
            stage="remote check",
        )
        self._ensure_clean(repository_root)
        return UpdatePlan(repository_root=repository_root, branch=branch)

    def fetch(self, plan: UpdatePlan) -> None:
        """Fetch the configured remote without changing tracked files."""
        self._run(
            ["git", "fetch", "origin"],
            cwd=plan.repository_root,
            stage="fetch",
        )

    def pull(self, plan: UpdatePlan) -> None:
        """Fast-forward the current branch only when the working tree is clean."""
        self._ensure_clean(plan.repository_root)
        try:
            self._run(
                ["git", "pull", "--ff-only", "origin", plan.branch],
                cwd=plan.repository_root,
                stage="pull",
            )
        except ToolboxUpdateError as error:
            raise ToolboxUpdateError(
                str(error),
                stage="pull",
                checkout_may_have_changed=True,
            ) from error

    def sync(self, plan: UpdatePlan) -> None:
        """Synchronize the environment from the updated lock file."""
        try:
            self._run(
                ["uv", "sync"],
                cwd=plan.repository_root,
                stage="dependency sync",
            )
        except ToolboxUpdateError as error:
            raise ToolboxUpdateError(
                str(error),
                stage="dependency sync",
                checkout_may_have_changed=True,
            ) from error

    def _ensure_clean(self, repository_root: Path) -> None:
        status = self._run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repository_root,
            stage="working tree check",
        )
        if status.strip():
            raise ToolboxUpdateError(
                "The working tree has local changes. Commit or move them elsewhere, "
                "then try the update again.",
                stage="working tree check",
            )

    @staticmethod
    def _run(command: list[str], *, cwd: Path, stage: str) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=COMMAND_TIMEOUT,
                check=False,
            )
        except FileNotFoundError as error:
            executable = command[0]
            raise ToolboxUpdateError(
                f"Required command '{executable}' was not found on PATH.", stage=stage
            ) from error
        except subprocess.TimeoutExpired as error:
            raise ToolboxUpdateError(
                f"Command '{command[0]}' timed out during {stage}.", stage=stage
            ) from error
        except OSError as error:
            raise ToolboxUpdateError(
                f"Could not run '{command[0]}' during {stage}: {error}", stage=stage
            ) from error

        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            details = _CREDENTIALS_IN_URL.sub(r"\1[redacted]@", details)
            if len(details) > MAX_ERROR_OUTPUT:
                details = details[:MAX_ERROR_OUTPUT] + "…"
            message = f"Command '{command[0]}' failed during {stage}."
            if details:
                message = f"{message}\n{details}"
            raise ToolboxUpdateError(message, stage=stage)
        return result.stdout
