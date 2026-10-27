# Project Guidelines

## Code quality and organization

- Keep the code clean, readable, and organized around the existing project structure.
- Prefer small, focused functions and classes with clear responsibilities.
- Avoid duplicated code. Reuse existing utilities and UI components, or introduce a shared utility or base component when that is the appropriate way to keep common behavior in one place.
- Remove obsolete code and imports when changing a feature.
- Follow the conventions already used by the project and its Python tooling.

## Tests

- Add unit tests for every new feature, covering its expected behavior and relevant edge cases.
- Run the test suite after adding or changing functionality to confirm the new behavior works and existing features continue to pass.
- When a test cannot be run, document the reason and the remaining verification needed.

## Language

- Write all code, identifiers, comments, docstrings, and developer-facing messages in English.
- Keep user-facing text in the language already used by the relevant screen unless the task requests a language change.

## Documentation

- Keep `README.md` current whenever a change adds or alters relevant project information, such as setup, execution, configuration, features, or usage.
- Prefer concise, actionable documentation that matches the behavior of the application.

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
