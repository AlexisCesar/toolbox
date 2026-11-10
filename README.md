# Toolbox TUI 🧰

![Toolbox TUI screenshot](https://github.com/user-attachments/assets/cb793e85-24b2-4d93-83d3-0b86fc051b0e)

**Toolbox TUI** is a terminal user interface for everyday software development
tasks. It brings together the scripts, logs, project folders, notes, and health
checks we use throughout the workday, so they are easy to find in one place.

## ❓ What you can do

- 🐚 Run commands in an interactive, persistent Bash session.
- 📜 Browse and run scripts from a configurable folder, with descriptions and
  saved parameters. Run `.sql` files on SQL Server or copy their contents.
- 📝 Create, browse, edit, and save text files and preview Markdown notes.
- 📂 Find project folders and open a solution or folder with an installed IDE or
  editor. Choose from detected tools such as Visual Studio, VS Code, Rider,
  Devin Desktop, IntelliJ IDEA, PyCharm, WebStorm, GoLand, CLion, PhpStorm,
  RubyMine, RustRover, Cursor, Sublime Text, Zed, and Notepad++.
- 📋 Browse local or network log folders and inspect recent log output.
- 🏥 Monitor HTTP endpoints and TCP connections on a configurable interval.
- ✅ Create and organize TODOs, sub-items, descriptions, and priorities.
- 🧰 Search offline utilities for formatting, validation, text comparison, encoding,
  conversion, and sample data generation.
- 🧩 Install third-party Addons from Git repositories, with separate sidebar views.
- 🔧 Configure folders, theme, log sources, health checks, and other settings.
- 🎃🎄 Enjoy seasonal themes!

## 🧰 Get started

### Prerequisites

- Install [Git](https://git-scm.com/downloads) (to clone this repository)
- Install [Python 3.12 or newer](https://www.python.org/downloads/)
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (for installing
  project dependencies and running the app)
- Install the [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/)
  (version 17 or 18) to run `.sql` scripts.
- Install Bash, if you want to use the embedded Bash view. Linux and macOS use Bash on
  `PATH`; on Windows, install [Git for Windows](https://gitforwindows.org/).

### Clone and run

```bash
git clone https://github.com/AlexisCesar/toolbox.git
cd toolbox
uv run python main.py
```

On first launch, Toolbox creates `config.override.toml` in the project folder
from the checked-in `config.toml` defaults. The override is ignored by Git and
stores your local settings, so pulling project changes does not overwrite them.


## 🔧 Configure your Toolbox

The included `config.toml` contains example settings and paths for scripts,
notes, projects, logs, and health checks. Open **Settings** in the app to change
the configured directories, theme, log folders, and health checks. 

The Scripts settings also let you set how many subfolder levels are scanned and
generate a `scripts_configuration.toml` file for script descriptions and saved
parameters.

Log folders may be local or network locations; the viewer opens at the latest 
part of a log file. 

Seasonal themes appear in Settings during their calendar periods. To make all
seasonal themes available year-round for development, set
`ui.enable_all_seasonal_themes = true` manually in `config.toml`.

TODO items are stored separately from `config.toml` in the current user's
application data directory: `%APPDATA%\\toolbox` on Windows,
`~/Library/Application Support/toolbox` on macOS, and
`$XDG_DATA_HOME/toolbox` or `~/.local/share/toolbox` on Linux. Set
`TOOLBOX_DATA_DIR` to use a different location. Startup notifications for
pending TODOs can be changed in Settings.

Use **Settings → Configuration → Export** to save selected settings groups to a
JSON file, or **Import** to choose which groups from an export to apply. Imports
replace only the selected groups in `config.override.toml`. The Calendar group
contains its subscription URL, so include it only when you intend to transfer
that private link.

## 🧩 Addons

Open **Addons** from the sidebar (shortcut **G**) to install or remove Addons.
Paste an HTTPS or SSH Git repository URL to install it. Toolbox clones the
repository, validates its `toolbox-addon.json` manifest, and adds one sidebar
item for the Addon. Addons are stored in the current user's application data
directory under `addons`; `TOOLBOX_DATA_DIR` can change that location.

### Addon contract (API version 1)

An Addon repository must contain `toolbox-addon.json` at its root:

```json
{
  "api_version": 1,
  "id": "pomodoro",
  "name": "Pomodoro",
  "version": "1.0.0",
  "icon": "⏱️",
  "refresh_interval_seconds": 1,
  "command": ["python", "addon.py"]
}
```

The `id` uses lowercase letters, digits, and hyphens, starts with a letter, and
is limited to 64 characters. `name` and `version` are short display strings;
`icon` is optional and defaults to a puzzle piece. `command` is a non-empty
array of command arguments. `refresh_interval_seconds` is optional; set it to a
number from 1 to 3600 to refresh the view at that interval while its sidebar tab
is open. Toolbox stops polling when another view is selected. Choose a runtime
command that is available on the user's `PATH` and document any runtime or
package requirements. Toolbox starts it with the repository as the working
directory and does not pass it through a shell.

Toolbox starts the Addon process for each request, writes one UTF-8 JSON object
and a newline to stdin, reads one UTF-8 JSON object from stdout, and then expects
the process to exit with status 0. The request shape is:

```json
{
  "protocol": 1,
  "id": "request-id",
  "method": "view",
  "state": null
}
```

For an action, `method` is `"action"` and the request also contains the action
id in `"action"`. A periodic update uses `method: "refresh"`. For both, `state`
contains the previous response's state. Every response has the same protocol
and request id and a `view` object:

```json
{
  "protocol": 1,
  "id": "request-id",
  "view": {
    "title": "Pomodoro",
    "body": "Ready for a 25 minute focus session.",
    "state": {"remaining_seconds": 1500},
    "actions": [{"id": "start", "label": "Start"}]
  }
}
```

`title` and `body` are text. The body is displayed as plain text. `state` must be
a JSON object or `null`; Toolbox keeps it in memory for the current app session
and returns it to the Addon on its next action or refresh. `actions` is optional and may
contain up to 20 buttons, each with a unique id (letters, digits, `_`, and `-`)
and a short label. Responses are limited to 512 KB, the body to 100 KB, the state
to 100 KB, and each process request to 15 seconds. Write only the response JSON
to stdout; send diagnostics to stderr.

A minimal Python Addon can use this request/response loop:

```python
import json
import sys

request = json.loads(sys.stdin.readline())
state = request.get("state") or {"started": False}
if request["method"] == "action" and request.get("action") == "start":
    state["started"] = True

view = {
    "title": "Pomodoro",
    "body": "Focus session started." if state["started"] else "Ready to focus.",
    "state": state,
    "actions": [] if state["started"] else [{"id": "start", "label": "Start"}],
}
print(json.dumps({"protocol": 1, "id": request["id"], "view": view}))
```

The process boundary keeps Addon imports and failures out of Toolbox's Python
process, but it is not a security sandbox. An installed Addon runs with the
current user's permissions, can read accessible files and environment variables,
and can use the network. Review the repository before installing it. Toolbox
does not expose a host API or send configuration through this protocol.

## 💻 Bash view

The Bash tab starts a persistent interactive session in the directory
where Toolbox was launched. Commands, variables, aliases, history, and tab
completion stay in the same session while you move between tabs. Use `Ctrl+C`
to interrupt a command, `Ctrl+D` or `exit` to end the session, and `Ctrl+G` to
return focus to the sidebar. Scroll through output with the mouse wheel or
`Shift+PageUp` / `Shift+PageDown`.

On Windows, Toolbox detects common Git for Windows Bash locations. For a custom
installation, set `TOOLBOX_BASH` to the full path of the Bash executable before
launching. Terminal emulation supports common ANSI output and keyboard input;
advanced terminal protocols and mouse interaction inside terminal programs are
not supported.

## 🧪 Development

Run the test suite with:

```bash
uv run pytest
```

During development, keep `APP_VERSION` at the latest official release and group
all unreleased notes in one pending version entry in `src/version.py`. When
preparing a pull request, assign that entry its release date and next version,
then synchronize `APP_VERSION` with `pyproject.toml` and `uv.lock`. The Home
Update Log defaults to the official version and lets you select other recorded
entries.

## Calendar

Open **Calendar** in the sidebar (shortcut **A**) to view today's appointments.
In your calendar provider's settings, find the option to copy or export a private
iCal subscription link. Paste it into Toolbox and select **Subscribe**. The
available steps and link access depend on your provider and account.

The agenda is read-only and uses your computer's timezone. It includes recurring,
all-day and overnight events; select a row to see the location and meeting URL.
It reloads when opened, on **Refresh**, and when the local date changes while
visible. Updates depend on the provider's iCal feed; they may not be immediate.
**Unsubscribe** removes the stored link and clears the agenda.

The subscription URL grants access to your private calendar. It is masked on
screen and saved in plain text in the Git-ignored `config.override.toml`
under `[calendar]` as `url`. Keep that file private. Toolbox does not log the
link or save event data to disk. It reads the iCal feed directly without asking
you to sign in.
