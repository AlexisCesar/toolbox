from pathlib import Path

import pytest

from src.utils.log_files import iter_log_files, read_log_text


def test_iter_log_files_includes_supported_types_and_skips_other_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.LOG").write_text("latest", encoding="utf-8")
    (tmp_path / "details.txt").write_text("details", encoding="utf-8")
    (tmp_path / "events.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / "2001-01-02.log").write_text("newer", encoding="utf-8")
    (tmp_path / "2001-01-01.log").write_text("older", encoding="utf-8")
    (tmp_path / "screenshot.png").write_bytes(b"image")
    (tmp_path / "subfolder").mkdir()

    assert [path.name for path in iter_log_files(tmp_path)] == [
        "events.jsonl",
        "details.txt",
        "app.LOG",
        "2001-01-02.log",
        "2001-01-01.log",
    ]


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


def test_iter_log_files_reports_unavailable_folder(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing"

    with pytest.raises(OSError):
        iter_log_files(missing_path)
