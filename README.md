Running the toolbox:

With UV installed, run:
```uv sync```

Then:
```uv run python main.py```

Run the unit tests with:
```uv run pytest```

The Scripts view scans the configured scripts directory. Set `scripts.depth` in
`config.toml` to include subfolders (from `0` for the root directory only to
`5`); this value can also be changed in the Settings tab.
