---
name: prepare-merge-request
description: Prepare the develop branch for a pull or merge request to master by syncing it, consolidating related changes into descriptive commits, running project tests, pushing the branch, and opening a request with the repository owner as reviewer.
---

# Prepare Merge Request

Use this skill when the user asks to prepare the repository's `develop` branch for a merge request into `master`. Follow the repository's own instructions and tooling for code changes, tests, commits, remotes, and review requests.

## 1. Confirm repository and branch

- Confirm the repository root, current branch, and the local `master` and `develop` branches. Require both branches to exist; do not create or guess them.
- This workflow targets `develop`. If the current branch is `master`, save any working-tree changes (including untracked files) with `git stash push --include-untracked`, switch to `develop`, and reapply the saved stash. Keep the stash entry until the changes are restored cleanly. If applying it conflicts, stop, report the conflicted paths, and leave the stash available for recovery.
- If the current branch is neither `master` nor `develop`, stop before changing branches or history and ask the user to switch to the intended branch. Do not silently prepare a different branch.
- Record the current `develop` commit before any history rewrite. If it has commits or changes that a reset would replace, keep a recoverable local backup ref before proceeding.

## 2. Sync `develop` with `master`

- Run `git fetch --all` before comparing branches. If fetching fails, stop without resetting anything.
- Resolve the fetched `master` for the repository's intended remote (normally `origin/master`); do not compare against a stale tracking ref. If the remote or branch cannot be identified unambiguously, stop and report what is missing.
- Compare the commit trees of `develop` and fetched `master`, not just their ancestry. If they differ, stash working-tree changes, reset `develop` to the fetched `master` commit, and reapply the saved changes. Retain the stash until reapplication succeeds. On any conflict, stop and report it; do not continue to commit, push, or open a request.
- Before a reset, protect any `develop` commits that would be displaced with a named backup ref. The requested reset is intentional, but the backup makes recovery possible. Never reset a different branch.

## 3. Consolidate changes into descriptive commits

- Inspect the full diff from `master` to the prepared `develop` work, including staged, unstaged, and untracked files. Identify distinct implementation types from the actual code changes.
- Check how many commits `develop` is ahead of `master`. Rewrite the branch history so it contains one commit for each distinct implementation type, with no more than one commit per type. If the changes form one implementation, create one commit. If they contain several independent implementations, split them into separate commits only where the file changes can be cleanly separated; otherwise use one coherent commit.
- Give every commit a concise, descriptive subject and a body that records the relevant code areas and behavior changed. Do not use vague subjects such as `updates` or `fixes`.
- Preserve all intended changes while rewriting history. Review the resulting commit list and diff against `master` before moving on. If the change set cannot be safely regrouped or a conflict occurs during history editing, stop and report the state rather than discarding work.

## 4. Run project tests

- Determine the relevant test commands from repository documentation and configuration (for example `README.md`, `pyproject.toml`, or package scripts). Run the project's test suite required for this change.
- If tests fail, report the failing command and results, and do not push or create a request. If no test suite or runnable command exists, report that validation could not be completed and stop before pushing or opening a request.
- Review `git status`, the final diff, and commit list after testing. Do not include generated files or unrelated local changes accidentally.

## 5. Push and open the request

- Identify the configured push remote and repository hosting service. Push `develop` to that remote. Since consolidating commits rewrites history, use a lease-protected force push only when the remote branch is the previous version of this same branch and the lease can be verified. If the remote has unrelated or newer commits, stop and report the divergence; never overwrite it blindly.
- When repository access and an authenticated host tool are available, open a pull/merge request from `develop` to `master`. Use the repository owner as reviewer, resolving the owner from repository metadata rather than guessing. Include a concise summary of the implementation and the tests run. If a request already exists for this branch, update or reuse it and ensure its base and reviewer are correct rather than creating a duplicate.
- If push or request creation is unavailable, report the precise completed state and the missing access or tool. Do not claim an operation succeeded unless the host confirms it.

## Completion report

Report the branch and base, commits created, tests and results, push status, and request link. If the workflow stopped, identify the stop condition and any retained stash or backup ref needed for recovery.
