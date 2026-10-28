Running the toolbox:

With UV installed, run:
```uv sync```

Then:
```uv run python main.py```

Run the test suite with:
```uv run pytest```

The Bash tab (sidebar shortcut `b`) opens a persistent interactive Bash session
inside Toolbox, starting in the directory where Toolbox was launched. Commands,
`cd`, variables, aliases, history, Tab completion, and interactive input use the
same shell until it exits or you select **Stop session**. Switching tabs keeps
the session running; closing Toolbox stops it. Select **New session** after a
session ends to start again.

Use `Ctrl+C` to interrupt a command, `Ctrl+D` or `exit` to end Bash, and `Ctrl+G`
to return keyboard focus to the sidebar. While the terminal has focus, letters
and Tab go to Bash instead of Toolbox navigation. Scroll with the mouse wheel
or `Shift+PageUp` / `Shift+PageDown` (up to 2,000 lines of output history).

Bash must be installed: on Linux/macOS it is found on `PATH`; on Windows,
install Git for Windows (its usual installation paths are detected). For a
custom installation, set `TOOLBOX_BASH` to the full executable path before
launching Toolbox. Windows uses ConPTY via pywinpty; Linux/macOS use a native
PTY. Dependencies are installed by `uv sync`. Terminal emulation supports common
ANSI output and keyboard interaction; advanced terminal protocols and mouse
interaction inside terminal programs are not supported.

The Scripts view scans the configured scripts directory. Set `scripts.depth` in
`config.toml` to include subfolders (from `0` for the root directory only to
`5`); this value can also be changed in the Settings tab.

Configure log folders in Settings. Each entry uses a name and a folder path,
which may be a local directory or a network share accessible to this computer:

```toml
[[logs]]
name = "Application X v2"
location = 'C:\dev\my_projects\application_x_v2\logs\'
```

The Logs tab lists the configured folders and shows their entries in descending
name order. It accepts logs with any filename, including rotated or extensionless
logs, and checks a small content sample when you open an entry to reject common
binary formats such as images and videos. Folder scans and file reads run in the
background, and the viewer starts with up to the last 256 KiB of the file so
large remote logs do not need to be read in full.

Configure HTTP endpoint and TCP connection health checks in Settings. HTTP checks
use a URL; TCP checks use `host:port`. Checks run immediately when the Health
Checks tab opens, then repeat at the selected 5, 10, 15, 30, or 60 second
interval while that tab remains open. HTTP responses with status codes from 200
through 399 are considered healthy; TCP checks report whether a connection can
be established.
