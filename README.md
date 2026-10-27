Running the toolbox:

With UV installed, run:
```uv sync```

Then:
```uv run python main.py```

Run the test suite with:
```uv run pytest```

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

The Logs tab lists the configured folders, filters to supported text log types
(`.log`, `.txt`, `.out`, `.err`, `.trace`, `.jsonl`, and `.ndjson`), and opens a
selected file at its latest entries.
