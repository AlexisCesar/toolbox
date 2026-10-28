import os
from pathlib import Path


LOG_FILE_EXTENSIONS = {".log", ".txt", ".out", ".err", ".trace", ".jsonl", ".ndjson"}
DEFAULT_TAIL_BYTES = 256 * 1024


def iter_log_entries(directory: Path) -> list[Path]:
    """List directory entry names without querying metadata for each network item."""
    directory = Path(directory)
    with os.scandir(directory) as entries:
        paths = [directory / entry.name for entry in entries]
    return sorted(paths, key=lambda path: path.name.casefold(), reverse=True)


def is_supported_log_file(path: Path) -> bool:
    """Check whether a path is a regular file with a supported log extension."""
    path = Path(path)
    return path.suffix.lower() in LOG_FILE_EXTENSIONS and path.is_file()


def read_log_text(path: Path) -> str:
    """Read and decode an entire text log file."""
    return _decode_log_text(Path(path).read_bytes())


def read_log_tail(path: Path, max_bytes: int = DEFAULT_TAIL_BYTES) -> str:
    """Read a bounded tail of a text log, starting at a complete line when possible."""
    if max_bytes <= 0:
        raise ValueError("The tail size must be greater than zero.")

    path = Path(path)
    with path.open("rb") as log_file:
        log_file.seek(0, os.SEEK_END)
        file_size = log_file.tell()
        if file_size <= max_bytes:
            log_file.seek(0)
            data = log_file.read()
            return _decode_log_text(data)

        log_file.seek(0)
        prefix = log_file.read(2)
        utf16_encoding = {
            b"\xff\xfe": "utf-16-le",
            b"\xfe\xff": "utf-16-be",
        }.get(prefix)

        start = max(2 if utf16_encoding else 0, file_size - max_bytes)
        if utf16_encoding and (start - 2) % 2:
            start += 1
        log_file.seek(start)
        data = log_file.read()

    if utf16_encoding:
        if len(data) % 2:
            data = data[:-1]
        content = data.decode(utf16_encoding, errors="replace")
        newline = "\n".encode(utf16_encoding)
        if start > 2:
            first_line_end = data.find(newline)
            data = data[first_line_end + len(newline):] if first_line_end >= 0 else b""
            content = data.decode(utf16_encoding, errors="replace")
    else:
        if start > 0:
            first_line_end = data.find(b"\n")
            if first_line_end < 0:
                first_line_end = data.find(b"\r")
            data = data[first_line_end + 1:] if first_line_end >= 0 else b""
        content = _decode_log_text(data)

    return content.replace("\r\n", "\n").replace("\r", "\n")


def _decode_log_text(data: bytes) -> str:
    """Decode common log encodings and reject data that looks binary."""
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
