from pathlib import Path

import pytest

from src.utils.log_files import (
    is_supported_log_file,
    iter_log_entries,
    read_log_tail,
    read_log_text,
)


def test_iter_log_entries_lists_all_items_without_filtering_extensions(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.LOG").write_text("latest", encoding="utf-8")
    (tmp_path / "details.txt").write_text("details", encoding="utf-8")
    (tmp_path / "events.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / "2001-01-02.log").write_text("newer", encoding="utf-8")
    (tmp_path / "2001-01-01.log").write_text("older", encoding="utf-8")
    (tmp_path / "screenshot.png").write_bytes(b"image")
    (tmp_path / "subfolder").mkdir()

    assert [path.name for path in iter_log_entries(tmp_path)] == [
        "subfolder",
        "screenshot.png",
        "events.jsonl",
        "details.txt",
        "app.LOG",
        "2001-01-02.log",
        "2001-01-01.log",
    ]


def test_is_supported_log_file_requires_allowed_extension_and_regular_file(
    tmp_path: Path,
) -> None:
    valid_file = tmp_path / "application.LOG"
    valid_file.write_text("log", encoding="utf-8")
    unsupported_file = tmp_path / "image.png"
    unsupported_file.write_bytes(b"image")
    log_named_directory = tmp_path / "directory.log"
    log_named_directory.mkdir()

    assert is_supported_log_file(valid_file)
    assert not is_supported_log_file(unsupported_file)
    assert not is_supported_log_file(log_named_directory)


def test_read_log_text_supports_utf8_bom_and_legacy_windows_text(
    tmp_path: Path,
) -> None:
    utf8_path = tmp_path / "utf8.log"
    utf8_path.write_bytes("\ufefflatest: é".encode("utf-8"))
    windows_path = tmp_path / "windows.txt"
    windows_path.write_bytes("latest: café".encode("cp1252"))

    assert read_log_text(utf8_path) == "latest: é"
    assert read_log_text(windows_path) == "latest: café"


def test_read_log_text_rejects_binary_content(tmp_path: Path) -> None:
    path = tmp_path / "bad.log"
    path.write_bytes(b"\x00\x01\x02")

    with pytest.raises(ValueError, match="binary"):
        read_log_text(path)


def test_read_log_tail_returns_latest_complete_lines_with_bounded_read(
    tmp_path: Path,
) -> None:
    path = tmp_path / "large.log"
    path.write_text("discard this long line\nlatest one\nlatest two", encoding="utf-8")

    assert read_log_tail(path, max_bytes=24) == "latest one\nlatest two"


def test_read_log_tail_supports_utf16_logs(tmp_path: Path) -> None:
    path = tmp_path / "utf16.log"
    path.write_bytes(("discard this long line\nlatest entry\n" * 4).encode("utf-16"))

    assert read_log_tail(path, max_bytes=40).endswith("latest entry\n")


def test_iter_log_entries_reports_unavailable_folder(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing"

    with pytest.raises(OSError):
        iter_log_entries(missing_path)
