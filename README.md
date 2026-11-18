# Toolbox TUI 🧰

<img width="1607" height="920" alt="image" src="https://github.com/user-attachments/assets/91e36ab8-5adb-4c9d-8542-a8bca8336cf2" />

**Toolbox TUI** brings common software development tasks into one terminal
application: scripts, projects, notes, logs, health checks, TODOs, and more.

## Features

- Run commands in a persistent Bash session.
- Browse scripts, descriptions, and saved parameters; run SQL Server scripts.
- Find projects and open them with detected IDEs and editors.
- Create and edit text files, and preview Markdown notes.
- Browse logs by last-modified time and monitor HTTP endpoints or TCP connections.
- Organize TODOs, hide completed items without deleting them, and use offline
  tools for common text and data tasks.
- View calendar events and customize folders, themes, and health checks.

## Quick start

### Requirements

- [Git](https://git-scm.com/downloads) to clone the repository.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) to run the app and
  manage its dependencies.
- A separate Python installation is optional. By default, uv uses a compatible
  Python already on the computer or downloads Python 3.12 or newer when needed.
  If automatic downloads are disabled or unavailable, install
  [Python 3.12 or newer](https://www.python.org/downloads/) yourself. See the
  [uv Python documentation](https://docs.astral.sh/uv/guides/install-python/).

Optional tools:

- Install the [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/)
  (version 17 or 18) to run SQL Server scripts.
- Install Bash to use the embedded Bash view. On Windows, install
  [Git for Windows](https://gitforwindows.org/); on Linux and macOS, use Bash
  available on `PATH`.

### Clone and launch

```bash
git clone https://github.com/AlexisCesar/toolbox.git
cd toolbox
uv run python main.py
```

On first launch, Toolbox creates `config.override.toml` from the checked-in
`config.toml`. The override contains local settings and is ignored by Git.

When a newer release is available, the Home screen offers an update button.
Updates require a clean working tree and a branch tracking `origin/<branch>`;
Toolbox fetches, fast-forwards that branch, and runs `uv sync`. Afterward, close
and relaunch Toolbox to use the updated version.

## Configuration

Open **Settings** to configure folders, themes, log sources, and health checks.
The checked-in `config.toml` provides the initial defaults.

- **Scripts:** choose the folder to scan, set the scan depth, and create
  `scripts_configuration.toml` for descriptions and saved parameters.
- **TODOs:** stored in the user's application data directory. Set
  `TOOLBOX_DATA_DIR` to use a different data location.
- **Configuration transfer:** use **Settings → Configuration → Export** or
  **Import** to transfer selected settings groups. Imports replace only the
  selected groups in `config.override.toml`.
- **Seasonal themes:** themes are available in Settings during their calendar
  periods. For development, set `ui.enable_all_seasonal_themes = true` in
  `config.toml` to show them year-round.

## Calendar

Open **Calendar** (shortcut **A**) to view today's appointments. Copy a private
iCal subscription link from your calendar provider, paste it into Toolbox, and
select **Subscribe**. The agenda is read-only and uses your computer's timezone.
It includes recurring, all-day, and overnight events.

The agenda reloads when opened, on **Refresh**, and when the local date changes
while it is visible. Updates depend on the provider's iCal feed and may not be
immediate. **Unsubscribe** removes the saved link and clears the agenda.

The subscription URL grants access to your private calendar. Toolbox masks it
on screen and stores it in plain text in the Git-ignored `config.override.toml`
under `[calendar].url`. Keep that file private. Toolbox does not log the URL
or save event data to disk.

## Addons

[About Addons](https://github.com/AlexisCesar/toolbox/wiki/About-Addons)

## Bash view

The Bash tab starts a persistent session in the directory where Toolbox was
launched. Commands, variables, aliases, history, and tab completion remain
available as you move between views. Use `Ctrl+C` to interrupt a command,
`Ctrl+D` or `exit` to end the session, and `Ctrl+G` to return focus to the
sidebar.

On Windows, Toolbox detects common Git for Windows Bash locations. Set
`TOOLBOX_BASH` to the full executable path to use a custom installation.
Terminal emulation supports common ANSI output and keyboard input; advanced
terminal protocols and mouse interaction inside terminal programs are not
supported.

## Development

Run the test suite with:

```bash
uv run pytest
```

The application version and release notes are maintained in `src/version.py`.
