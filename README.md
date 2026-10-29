# Toolbox TUI 🧰

![Toolbox TUI screenshot](https://github.com/user-attachments/assets/cb793e85-24b2-4d93-83d3-0b86fc051b0e)

**Toolbox TUI** is a terminal user interface for everyday software development
tasks. It brings together the scripts, logs, project folders, notes, and health
checks we use throughout the workday, so they are easy to find in one place.

## ❓ What you can do

- 🐚 Run commands in an interactive, persistent Bash session.
- 📜 Browse and run scripts from a configurable folder, with descriptions and
  saved parameters.
- 📝 Browse, edit, and save text files and preview Markdown notes.
- 📂 Find project folders and open solutions in Visual Studio or VS Code. Open
  folders without a solution in VS Code when it is installed.
- 📋 Browse local or network log folders and inspect recent log output.
- 🏥 Monitor HTTP endpoints and TCP connections on a configurable interval.
- ✅ Create and organize TODOs, sub-items, descriptions, and priorities.
- 🧰 Search offline utilities for formatting, validation, text comparison, encoding,
  conversion, and sample data generation.
- 🔧 Configure folders, theme, log sources, health checks, and other settings.
- 🎃🎄 Enjoy seasonal themes!

## 🧰 Get started

### Prerequisites

- Install [Git](https://git-scm.com/downloads) (to clone this repository)
- Install [Python 3.12 or newer](https://www.python.org/downloads/)
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) (for installing
  project dependencies and running the app)
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
