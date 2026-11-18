import json
from unittest.mock import MagicMock
from urllib.error import URLError

import pytest

from src.utils.recommended_addons import (
    CACHE_TTL_SECONDS,
    CATALOG_URLS,
    RecommendedAddon,
    RecommendedAddonsCatalog,
    RecommendedAddonsError,
    parse_recommendations,
)


RECOMMENDATIONS = [
    {
        "name": "Environment Report",
        "repository": "https://github.com/AlexisCesar/toolbox-environment-report",
        "description": "General information about the system.",
        "category": "Development",
    },
]


def mock_response(payload: object) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    return response


def write_cache(path, *, fetched_at: float, recommendations=RECOMMENDATIONS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "fetched_at": fetched_at,
                "recommendations": recommendations,
            }
        ),
        encoding="utf-8",
    )


def test_parse_recommendations_returns_typed_entries() -> None:
    result = parse_recommendations(RECOMMENDATIONS)

    assert result == (
        RecommendedAddon(
            name="Environment Report",
            repository="https://github.com/AlexisCesar/toolbox-environment-report",
            description="General information about the system.",
            category="Development",
        ),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Addon"},
        [{"name": "Addon"}],
        [{**RECOMMENDATIONS[0], "repository": "https://example.com/addon"}],
        [{**RECOMMENDATIONS[0], "repository": "http://github.com/owner/repo"}],
        [{**RECOMMENDATIONS[0], "repository": "https://github.com:444/owner/repo"}],
        [{**RECOMMENDATIONS[0], "repository": "https://[invalid"}],
    ],
)
def test_parse_recommendations_rejects_invalid_entries(payload: object) -> None:
    with pytest.raises(RecommendedAddonsError):
        parse_recommendations(payload)


def test_load_uses_fresh_cache_without_network(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "cache.json"
    write_cache(cache_path, fetched_at=1_000)
    monkeypatch.setattr("src.utils.recommended_addons.time.time", lambda: 1_000 + 10)
    monkeypatch.setattr(
        "src.utils.recommended_addons.urlopen",
        lambda *_args, **_kwargs: pytest.fail("Fresh cache should avoid the network."),
    )

    result = RecommendedAddonsCatalog(cache_path).load()

    assert result.from_cache
    assert not result.stale
    assert result.addons[0].name == "Environment Report"


def test_load_fetches_and_persists_catalog(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "nested" / "cache.json"
    response = mock_response(RECOMMENDATIONS)
    monkeypatch.setattr("src.utils.recommended_addons.time.time", lambda: 1_000)
    monkeypatch.setattr(
        "src.utils.recommended_addons.urlopen",
        lambda request, timeout: response,
    )

    result = RecommendedAddonsCatalog(cache_path).load()

    assert not result.from_cache
    assert result.addons[0].name == "Environment Report"
    assert cache_path.exists()
    assert json.loads(cache_path.read_text(encoding="utf-8"))["fetched_at"] == 1_000


def test_load_tries_develop_until_master_catalog_is_available(tmp_path, monkeypatch) -> None:
    requested_urls: list[str] = []

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        if request.full_url == CATALOG_URLS[0]:
            raise URLError("not published yet")
        return mock_response(RECOMMENDATIONS)

    monkeypatch.setattr("src.utils.recommended_addons.urlopen", fake_urlopen)
    monkeypatch.setattr("src.utils.recommended_addons.time.time", lambda: 1_000)

    result = RecommendedAddonsCatalog(tmp_path / "cache.json").load()

    assert requested_urls == list(CATALOG_URLS)
    assert not result.from_cache
    assert result.addons[0].name == "Environment Report"


def test_load_refreshes_expired_cache(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "cache.json"
    write_cache(cache_path, fetched_at=1_000)
    response = mock_response(
        [{**RECOMMENDATIONS[0], "name": "Updated Environment Report"}]
    )
    monkeypatch.setattr(
        "src.utils.recommended_addons.time.time",
        lambda: 1_000 + CACHE_TTL_SECONDS + 1,
    )
    monkeypatch.setattr("src.utils.recommended_addons.urlopen", lambda *_args, **_kwargs: response)

    result = RecommendedAddonsCatalog(cache_path).load()

    assert not result.from_cache
    assert result.addons[0].name == "Updated Environment Report"


def test_load_returns_stale_cache_when_catalog_sources_are_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    cache_path = tmp_path / "cache.json"
    write_cache(cache_path, fetched_at=1_000)
    monkeypatch.setattr(
        "src.utils.recommended_addons.time.time",
        lambda: 1_000 + CACHE_TTL_SECONDS + 1,
    )
    monkeypatch.setattr(
        "src.utils.recommended_addons.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )

    result = RecommendedAddonsCatalog(cache_path).load()

    assert result.from_cache
    assert result.stale
    assert "offline" in (result.warning or "")


def test_load_raises_when_network_and_cache_are_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.utils.recommended_addons.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )

    with pytest.raises(RecommendedAddonsError, match="offline"):
        RecommendedAddonsCatalog(tmp_path / "missing.json").load()
