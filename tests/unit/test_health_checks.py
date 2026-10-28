from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

from src.views.health_checks import check_service
from src.utils.health_check_config_dialog import HealthCheckConfigDialog


def test_http_check_accepts_success_status() -> None:
    response = MagicMock()
    response.status = 204
    response.__enter__.return_value = response

    with patch("src.views.health_checks.urlopen", return_value=response):
        healthy, message, duration = check_service(
            {"type": "http", "target": "https://example.com/health"}
        )

    assert healthy is True
    assert message == "HTTP 204"
    assert duration >= 0


def test_http_check_rejects_error_status() -> None:
    response_error = HTTPError(
        "https://example.com/health", 503, "Unavailable", {}, None
    )

    with patch("src.views.health_checks.urlopen", side_effect=response_error):
        healthy, message, _ = check_service(
            {"type": "http", "target": "https://example.com/health"}
        )

    assert healthy is False
    assert message == "HTTP 503"


def test_tcp_check_reports_successful_connection() -> None:
    connection = MagicMock()
    connection.__enter__.return_value = connection

    with patch("src.views.health_checks.socket.create_connection", return_value=connection):
        healthy, message, _ = check_service({"type": "tcp", "target": "localhost:5432"})

    assert healthy is True
    assert message == "Connection accepted"


def test_tcp_check_reports_connection_error() -> None:
    with patch(
        "src.views.health_checks.socket.create_connection",
        side_effect=OSError("Connection refused"),
    ):
        healthy, message, _ = check_service({"type": "tcp", "target": "localhost:5432"})

    assert healthy is False
    assert message == "Connection refused"


def test_unknown_check_type_is_down() -> None:
    healthy, message, _ = check_service({"type": "process", "target": "service"})

    assert healthy is False
    assert message == "Unsupported health check type: process"


def test_http_target_validation_requires_http_scheme_and_host() -> None:
    assert HealthCheckConfigDialog._valid_target("http", "https://example.com/health")
    assert HealthCheckConfigDialog._valid_target("http", "http://localhost:8080/health")
    assert not HealthCheckConfigDialog._valid_target("http", "ftp://example.com/health")
    assert not HealthCheckConfigDialog._valid_target("http", "https:///health")
    assert not HealthCheckConfigDialog._valid_target("http", "http://example.com:bad/health")


def test_tcp_target_validation_requires_host_and_valid_port() -> None:
    assert HealthCheckConfigDialog._valid_target("tcp", "localhost:5432")
    assert HealthCheckConfigDialog._valid_target("tcp", "[::1]:5432")
    assert not HealthCheckConfigDialog._valid_target("tcp", "localhost")
    assert not HealthCheckConfigDialog._valid_target("tcp", "localhost:70000")
    assert not HealthCheckConfigDialog._valid_target("tcp", "localhost:5432/path")
