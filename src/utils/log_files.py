from pathlib import Path


LOG_FILE_EXTENSIONS = {".log", ".txt", ".out", ".err", ".trace", ".jsonl", ".ndjson"}


def iter_log_files(directory: Path) -> list[Path]:
    """Return supported log files directly inside a configured directory."""
    return sorted(
        (
            path
            for path in Path(directory).iterdir()
            if path.is_file() and path.suffix.lower() in LOG_FILE_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def read_log_text(path: Path) -> str:
    """Read a text log, supporting common UTF encodings and Windows text."""
    data = Path(path).read_bytes()

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        content = data.decode("utf-16")
    elif b"\x00" in data[:8192]:
        raise ValueError("The file appears to be binary.")
    else:
        content = None
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                content = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            content = data.decode("utf-8", errors="replace")

    return content.replace("\r\n", "\n").replace("\r", "\n")
