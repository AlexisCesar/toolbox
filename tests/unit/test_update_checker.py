import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from src.utils.update_checker import (
    LATEST_RELEASE_URL,
    REQUEST_TIMEOUT,
    UpdateCheckError,
    check_for_update,
)


def mock_response(payload: object) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    return response


def test_check_for_update_returns_newer_stable_release() -> None:
    response = mock_response({"tag_name": "v0.4.0"})

    with patch("src.utils.update_checker.urlopen", return_value=response) as urlopen:
        result = check_for_update("0.3.0")

    assert result == "0.4.0"
    request = urlopen.call_args.args[0]
    assert request.full_url == LATEST_RELEASE_URL
    assert request.get_header("User-agent") == "ToolboxTUI"
    assert urlopen.call_args.kwargs["timeout"] == REQUEST_TIMEOUT


@pytest.mark.parametrize("tag", ["0.3.0", "v0.2.9"])
def test_check_for_update_ignores_current_or_older_release(tag: str) -> None:
    with patch(
        "src.utils.update_checker.urlopen",
        return_value=mock_response({"tag_name": tag}),
    ):
        assert check_for_update("0.3.0") is None


def test_check_for_update_wraps_network_errors() -> None:
    with patch(
        "src.utils.update_checker.urlopen",
        side_effect=URLError("offline"),
    ):
        with pytest.raises(UpdateCheckError, match="offline"):
            check_for_update("0.3.0")


def test_check_for_update_rejects_unusable_release_payload() -> None:
    with patch(
        "src.utils.update_checker.urlopen",
        return_value=mock_response({"tag_name": "next"}),
    ):
        with pytest.raises(UpdateCheckError, match="Unsupported GitHub release tag"):
            check_for_update("0.3.0")
