from src.utils.config import Config, iter_script_files
from src.views.scripts import format_script_display_name, format_scripts_directory_label


def test_script_files_respect_configured_depth(tmp_path) -> None:
    root_script = tmp_path / "root.py"
    level_one_script = tmp_path / "one" / "nested.sh"
    level_two_script = tmp_path / "one" / "two" / "deep.sql"
    unsupported_file = tmp_path / "one" / "readme.txt"
    batch_script = tmp_path / "run.bat"
    for path in (root_script, level_one_script, level_two_script, unsupported_file, batch_script):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def relative_paths(depth: int) -> list[str]:
        return sorted(path.relative_to(tmp_path).as_posix() for path in iter_script_files(tmp_path, depth))

    assert relative_paths(0) == ["root.py", "run.bat"]
    assert relative_paths(1) == ["one/nested.sh", "root.py", "run.bat"]
    assert relative_paths(5) == ["one/nested.sh", "one/two/deep.sql", "root.py", "run.bat"]


def test_scripts_depth_defaults_and_clamps_to_supported_range() -> None:
    settings = Config.__new__(Config)
    settings._data = {"scripts": {"timeout": 3}}
    assert settings.scripts_depth == 0

    settings._data["scripts"]["depth"] = 9
    assert settings.scripts_depth == Config.MAX_SCRIPTS_DEPTH

    settings._data["scripts"]["depth"] = -2
    assert settings.scripts_depth == 0


def test_scripts_directory_label_mentions_depth_only_when_enabled(tmp_path) -> None:
    assert format_scripts_directory_label(tmp_path, 0) == f"Reading scripts from: 📂 {tmp_path.absolute()}"
    assert format_scripts_directory_label(tmp_path, 3).endswith("(with a depth of 3 subfolders)")


def test_script_display_name_shows_subfolder_depth(tmp_path) -> None:
    root_script = tmp_path / "hello.py"
    nested_script = tmp_path / "one" / "two" / "hello.py"

    assert format_script_display_name(root_script, tmp_path) == "hello.py"
    assert format_script_display_name(nested_script, tmp_path) == "📁 (2) hello.py"
