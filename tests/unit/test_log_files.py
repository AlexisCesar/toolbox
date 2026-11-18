import os
from datetime import datetime
from pathlib import Path

import pytest

from src.utils.log_files import (
    is_text_log_file,
    iter_log_entries,
    read_log_tail,
    read_log_text,
)


def test_iter_log_entries_lists_all_items_without_filtering_extensions(
    tmp_path: Path,
) -> None:
    paths = [
        tmp_path / "app.LOG",
        tmp_path / "details.txt",
        tmp_path / "events.jsonl",
        tmp_path / "2001-01-02.log",
        tmp_path / "2001-01-01.log",
        tmp_path / "screenshot.png",
        tmp_path / "subfolder",
    ]
    contents = [
        b"latest",
        b"details",
        b"{}",
        b"newer",
        b"older",
        b"\x89PNG\r\n\x1a\nimage",
    ]
    for path, content in zip(paths[:6], contents, strict=True):
        path.write_bytes(content)
    paths[-1].mkdir()

    first_timestamp = 1_700_000_000
    for index, path in enumerate(paths[:6]):
        timestamp = first_timestamp + index
        os.utime(path, (timestamp, timestamp))

    entries = iter_log_entries(tmp_path)
    files = [entry for entry in entries if entry.path.is_file()]

    assert {entry.path.name for entry in entries} == {path.name for path in paths}
    assert [entry.path.name for entry in files] == [
        path.name for path in reversed(paths[:6])
    ]
    assert files[0].modified_at == datetime.fromtimestamp(
        first_timestamp + len(paths[:6]) - 1
    ).astimezone()


def test_is_text_log_file_accepts_rotated_and_extensionless_logs_and_rejects_binary(
    tmp_path: Path,
) -> None:
    regular_log = tmp_path / "application.LOG"
    regular_log.write_text("log", encoding="utf-8")
    rotated_log = tmp_path / "app01.log.20261027"
    rotated_log.write_text("yesterday's log", encoding="utf-8")
    extensionless_log = tmp_path / "app02-2026-10-27"
    extensionless_log.write_text("another log", encoding="utf-8")
    image_file = tmp_path / "image.png"
    image_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x01\x02" * 20)
    video_file = tmp_path / "clip"
    video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"video" * 20)
    directory = tmp_path / "directory"
    directory.mkdir()

    assert is_text_log_file(regular_log)
    assert is_text_log_file(rotated_log)
    assert is_text_log_file(extensionless_log)
    assert not is_text_log_file(image_file)
    assert not is_text_log_file(video_file)
    assert not is_text_log_file(directory)


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
