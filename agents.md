# Project Guidelines

## Code quality and organization

- Keep the code clean, readable, and organized around the existing project structure.
- Prefer small, focused functions and classes with clear responsibilities.
- Avoid duplicated code. Reuse existing utilities and UI components, or introduce a shared utility or base component when that is the appropriate way to keep common behavior in one place.
- Remove obsolete code and imports when changing a feature.
- Follow the conventions already used by the project and its Python tooling.

## Python and Textual

- Write Python that follows the project's configured version and tooling in `pyproject.toml`, with type hints and small, focused functions where they clarify behavior.
- Prefer standard-library facilities such as `pathlib` for filesystem paths and handle expected I/O errors explicitly.
- Build terminal interfaces with Textual's native widgets, containers, events, screens, and modal screens. Follow existing Textual interaction patterns instead of manually drawing or handling terminal input.
- Keep UI updates on the Textual event loop; use Textual workers for I/O that would otherwise block user interaction.
- Check the installed Textual API and nearby project examples before introducing a new widget or interaction pattern.

## Tests

- Add unit tests for every new feature, covering its expected behavior and relevant edge cases.
- Run the test suite after adding or changing functionality to confirm the new behavior works and existing features continue to pass.
- When a test cannot be run, document the reason and the remaining verification needed.
- On Windows in the restricted Codex environment, pass `--basetemp` with a fresh directory under `.pytest_tmp`; the default `%TEMP%` may not be writable. Confirm the chosen directory does not already exist because pytest clears its `--basetemp` directory before use.
- Bash session tests use `socket.socketpair()`. Python's Windows fallback opens a loopback connection, which the restricted environment may block and leave tests hanging. When this happens, rerun pytest in an environment that permits localhost loopback; do not change application code to work around the sandbox restriction. If that run is unavailable, report the limitation and the verification still needed.
- Organize tests under `tests/unit` and `tests/integration`.
- Keep `.gitkeep` files only in otherwise empty folders, and remove them as soon as a folder contains another file.

## Language

- Write all code, identifiers, comments, docstrings, and developer-facing messages in English.
- Keep user-facing text in the language already used by the relevant screen unless the task requests a language change.

## Documentation

- Keep `README.md` current whenever a change adds or alters relevant project information, such as setup, execution, configuration, features, or usage.
- Prefer concise, actionable documentation that matches the behavior of the application.
- Keep `src/version.py` as the application source for `APP_VERSION` and the release `CHANGELOG`; keep the package version in `pyproject.toml` and `uv.lock` synchronized with `APP_VERSION`.
- For every change prepared for merge, increment `APP_VERSION` and add a dated changelog entry under the same version. Use MAJOR for breaking changes, MINOR for backward-compatible features, and PATCH for fixes or other backward-compatible changes. Include only non-empty `added`, `changed`, and `fixed` sections in the Home screen output.
- Keep the version label in the UI derived from `APP_VERSION`; do not add a separate hard-coded version.

## Toolbox TUI home screen

- Keep the Home screen's introductory information and usage tips current as features, navigation, shortcuts, setup, or workflows change.
- Make first-run guidance clear and actionable so users know how to get started.
- When adding or changing a feature that affects how users get started, review the Home screen instructions in `src/views/home.py`.

## Screen layout and interaction

- Follow the established layout and interaction patterns across all Toolbox TUI screens.
- Keep shared elements, spacing, alignment, headings, navigation, and control behavior consistent with neighboring views.
- Before introducing a new screen pattern, check existing views and shared styles and reuse their approach where it fits.
- Ensure each screen works within the application's existing main panel and remains usable at typical terminal sizes.
- Update the relevant UI styles when needed so new or changed screens preserve the shared visual language.

## Operating system compatibility

- Account for the application running on Windows, Linux, or macOS when implementing features.
- Support all three operating systems where practical, including platform-specific paths, commands, and behavior.
- If a feature is unavailable on a particular operating system, clearly indicate that limitation to the user or write an application log entry identifying the unsupported platform and feature.

## Application logging

- Log application operations, errors, warnings, and relevant informational events through the application's `Logger` class.
- Choose the log level that matches the event's severity and purpose.
- Avoid silently swallowing errors or hiding meaningful application state changes from the log.
