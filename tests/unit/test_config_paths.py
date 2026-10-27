from src.utils.config import normalize_directory_path


def test_normalize_directory_path_replaces_backslashes() -> None:
    assert normalize_directory_path(r"C:\Users\Jane\toolbox\notes") == "C:/Users/Jane/toolbox/notes"


def test_normalize_directory_path_preserves_forward_slashes() -> None:
    assert normalize_directory_path("/home/jane/toolbox/notes") == "/home/jane/toolbox/notes"
