import os
import unicodedata
from pathlib import Path


DEFAULT_TAIL_BYTES = 256 * 1024
TEXT_PROBE_BYTES = 8 * 1024
_BINARY_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",
    b"GIF89a",
    b"II*\x00",  # TIFF little-endian
    b"MM\x00*",  # TIFF big-endian
    b"\x00\x00\x01\x00",  # ICO
    b"\x1aE\xdf\xa3",  # Matroska / WebM
    b"FLV",  # Flash video
    b"OggS",  # Ogg media
    b"ID3",  # MP3 with an ID3 tag
    b"PK\x03\x04",  # ZIP and Office documents
    b"\x1f\x8b",  # Gzip
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!\x1a\x07",
    b"%PDF-",
)


def iter_log_entries(directory: Path) -> list[Path]:
    """List directory entry names without querying metadata for each network item."""
    directory = Path(directory)
    with os.scandir(directory) as entries:
        paths = [directory / entry.name for entry in entries]
    return sorted(paths, key=lambda path: path.name.casefold(), reverse=True)


def is_text_log_file(path: Path) -> bool:
    """Check a small file sample to distinguish text logs from binary files."""
    path = Path(path)
    if not path.is_file():
        return False

    with path.open("rb") as log_file:
        sample = log_file.read(TEXT_PROBE_BYTES)
    return _looks_like_text(sample)


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
        log_file.seek(0)
        sample = log_file.read(TEXT_PROBE_BYTES)
        if not _looks_like_text(sample):
            raise ValueError("The file appears to be binary, not a text log.")

        if file_size <= max_bytes:
            log_file.seek(0)
            data = log_file.read()
            return _decode_log_text(data)

        prefix = sample[:2]
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
    if not _looks_like_text(data):
        raise ValueError("The file appears to be binary, not a text log.")

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        content = data.decode("utf-16")
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


def _looks_like_text(data: bytes) -> bool:
    """Use a bounded byte sample to reject common binary formats and controls."""
    if not data:
        return True

    if any(data.startswith(signature) for signature in _BINARY_SIGNATURES):
        return False
    if (
        len(data) >= 18
        and data.startswith(b"BM")
        and data[6:10] == b"\x00" * 4
        and int.from_bytes(data[14:18], "little") >= 12
    ):
        return False
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] in {b"AVI ", b"WEBP"}:
        return False
    if len(data) >= 8 and data[4:8] == b"ftyp":  # MP4, MOV, and related containers
        return False
    if data.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3")):  # MPEG
        return False
    if data.startswith(b"\x30\x26\xb2\x75\x8e\x66\xcf\x11"):  # ASF
        return False

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16-le" if data.startswith(b"\xff\xfe") else "utf-16-be"
        text = data[2:].decode(encoding, errors="replace")
        return _has_few_control_characters(text)
    if b"\x00" in data:
        return False

    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        return _has_few_control_characters(text)

    return False


def _has_few_control_characters(text: str) -> bool:
    if not text:
        return True
    non_text_characters = sum(
        unicodedata.category(character) == "Cc"
        and character not in "\t\n\f\r\x1b"
        for character in text
    )
    return non_text_characters / len(text) <= 0.01
