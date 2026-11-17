import importlib.util
from pathlib import Path


ADDON_PATH = Path(__file__).parents[2] / "addons" / "environment-report" / "addon.py"
SPEC = importlib.util.spec_from_file_location("environment_report_addon", ADDON_PATH)
assert SPEC is not None and SPEC.loader is not None
addon = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(addon)


def test_environment_report_returns_structured_dashboard(monkeypatch) -> None:
    layout = [
        {
            "type": "panel",
            "title": "System",
            "children": [
                {
                    "type": "table",
                    "columns": ["Property", "Value"],
                    "rows": [["Operating system", "Example OS"]],
                }
            ],
        }
    ]
    monkeypatch.setattr(addon, "build_layout", lambda: layout)

    response = addon.create_response(
        {"id": "view-1", "method": "view", "action": None}
    )

    assert response["protocol"] == 1
    assert response["id"] == "view-1"
    assert response["view"]["layout"] == layout
    assert "body" not in response["view"]
    assert response["view"]["actions"] == [
        {"id": "refresh", "label": "Refresh report"}
    ]
    assert "notifications" not in response


def test_environment_report_notifies_after_refresh_action(monkeypatch) -> None:
    monkeypatch.setattr(addon, "build_layout", lambda: [{"type": "text", "content": "Ready"}])

    response = addon.create_response(
        {"id": "action-1", "method": "action", "action": "refresh"}
    )

    assert response["notifications"] == [
        {
            "title": "Environment Report",
            "message": "The environment report has been refreshed.",
            "severity": "information",
            "timeout": 3,
        }
    ]


def test_environment_dashboard_composes_panels_tables_and_buttons(monkeypatch) -> None:
    monkeypatch.setattr(addon, "_system_rows", lambda: [["OS", "Example"]])
    monkeypatch.setattr(addon, "_tool_rows", lambda: [["Python", "3.12"]])
    monkeypatch.setattr(addon, "_environment_rows", lambda: [["PATH", "4 entries"]])
    monkeypatch.setattr(addon, "_network_rows", lambda: [["Host", "localhost"]])

    layout = addon.build_layout()

    assert layout[0]["type"] == "panel"
    assert layout[0]["children"][0]["type"] == "table"
    assert layout[2]["type"] == "row"
    assert layout[-1]["type"] == "button"
    assert layout[-1]["action"] == "refresh"
