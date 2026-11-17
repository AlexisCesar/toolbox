"""Load and cache the Toolbox recommended Addons catalog."""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from src.utils.todo_store import default_todo_path


CATALOG_URLS = (
    "https://raw.githubusercontent.com/AlexisCesar/toolbox/master/addons-catalog/recommended.json",
    "https://raw.githubusercontent.com/AlexisCesar/toolbox/develop/addons-catalog/recommended.json",
)
CACHE_TTL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT = 5
MAX_RESPONSE_BYTES = 256 * 1024
MAX_RECOMMENDATIONS = 100
CACHE_VERSION = 1


class RecommendedAddonsError(Exception):
    """Raised when no usable recommended Addons catalog is available."""


@dataclass(frozen=True)
class RecommendedAddon:
    """One Addon listed in the remote recommendations catalog."""

    name: str
    repository: str
    description: str
    category: str


@dataclass(frozen=True)
class RecommendedAddonsResult:
    """Catalog data and information about whether it came from the cache."""

    addons: tuple[RecommendedAddon, ...]
    from_cache: bool
    stale: bool = False
    warning: str | None = None


def default_recommended_addons_cache_path() -> Path:
    """Return the per-user cache path alongside Toolbox's other data."""
    return default_todo_path().parent / "cache" / "recommended-addons.json"


def parse_recommendations(payload: object) -> tuple[RecommendedAddon, ...]:
    """Validate and parse the public catalog JSON structure."""
    if not isinstance(payload, list):
        raise RecommendedAddonsError("The recommendations catalog must be a JSON list.")
    if len(payload) > MAX_RECOMMENDATIONS:
        raise RecommendedAddonsError("The recommendations catalog contains too many entries.")

    recommendations: list[RecommendedAddon] = []
    limits = {"name": 100, "repository": 500, "description": 1000, "category": 80}
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise RecommendedAddonsError(f"Recommendation {index + 1} must be an object.")
        values: dict[str, str] = {}
        for field, limit in limits.items():
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RecommendedAddonsError(
                    f"Recommendation {index + 1} must include a non-empty {field}."
                )
            value = value.strip()
            if len(value) > limit:
                raise RecommendedAddonsError(
                    f"Recommendation {index + 1} has a {field} that is too long."
                )
            values[field] = value

        _validate_repository_url(values["repository"], index + 1)
        recommendations.append(RecommendedAddon(**values))
    return tuple(recommendations)


def _validate_repository_url(repository: str, index: int) -> None:
    try:
        parsed = urlsplit(repository)
    except ValueError as error:
        raise RecommendedAddonsError(
            f"Recommendation {index} must use an HTTPS GitHub repository URL."
        ) from error
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != "github.com"
        or parsed.query
        or parsed.fragment
        or len([part for part in parsed.path.split("/") if part]) < 2
    ):
        raise RecommendedAddonsError(
            f"Recommendation {index} must use an HTTPS GitHub repository URL."
        )


class RecommendedAddonsCatalog:
    """Fetch the catalog occasionally and use a local copy between requests."""

    def __init__(
        self,
        cache_path: Path | None = None,
        *,
        catalog_urls: tuple[str, ...] = CATALOG_URLS,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ) -> None:
        self.cache_path = cache_path or default_recommended_addons_cache_path()
        self.catalog_urls = catalog_urls
        self.cache_ttl_seconds = cache_ttl_seconds

    def load(self) -> RecommendedAddonsResult:
        """Return a fresh catalog, falling back to cached data when offline."""
        now = time.time()
        cached, cache_timestamp, cache_warning = self._read_cache()
        if cached is not None and cache_timestamp is not None:
            age = now - cache_timestamp
            if 0 <= age <= self.cache_ttl_seconds:
                return RecommendedAddonsResult(cached, from_cache=True, warning=cache_warning)

        errors: list[str] = []
        for url in self.catalog_urls:
            try:
                recommendations = self._fetch(url)
            except RecommendedAddonsError as error:
                errors.append(f"{url}: {error}")
                continue

            warning = cache_warning
            try:
                self._write_cache(recommendations, now)
            except OSError as error:
                warning = _join_warnings(warning, f"Could not save the recommendations cache: {error}")
            return RecommendedAddonsResult(
                recommendations,
                from_cache=False,
                warning=warning,
            )

        detail = "; ".join(errors) or "No catalog source is configured."
        if cached is not None:
            return RecommendedAddonsResult(
                cached,
                from_cache=True,
                stale=True,
                warning=_join_warnings(cache_warning, f"GitHub could not be reached: {detail}"),
            )
        raise RecommendedAddonsError(f"Could not load recommended Addons: {detail}")

    def _fetch(self, url: str) -> tuple[RecommendedAddon, ...]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ToolboxTUI",
            },
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except OSError as error:
            raise RecommendedAddonsError(str(error) or error.__class__.__name__) from error

        if len(body) > MAX_RESPONSE_BYTES:
            raise RecommendedAddonsError("The recommendations catalog exceeded the size limit.")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RecommendedAddonsError("GitHub returned an invalid recommendations catalog.") from error
        return parse_recommendations(payload)

    def _read_cache(
        self,
    ) -> tuple[tuple[RecommendedAddon, ...] | None, float | None, str | None]:
        try:
            raw_cache = self.cache_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None, None, None
        except (OSError, UnicodeError) as error:
            return None, None, f"Could not read the recommendations cache: {error}"

        try:
            payload = json.loads(raw_cache)
            if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION:
                raise ValueError("unsupported cache format")
            fetched_at = payload.get("fetched_at")
            if (
                not isinstance(fetched_at, (int, float))
                or isinstance(fetched_at, bool)
                or not math.isfinite(fetched_at)
            ):
                raise ValueError("invalid cache timestamp")
            recommendations = parse_recommendations(payload.get("recommendations"))
        except (ValueError, OverflowError, RecommendedAddonsError) as error:
            return None, None, f"Ignored an invalid recommendations cache: {error}"
        return recommendations, float(fetched_at), None

    def _write_cache(
        self,
        recommendations: tuple[RecommendedAddon, ...],
        fetched_at: float,
    ) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "fetched_at": fetched_at,
            "recommendations": [asdict(addon) for addon in recommendations],
        }
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.cache_path.parent,
                prefix=f".{self.cache_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(self.cache_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def _join_warnings(first: str | None, second: str) -> str:
    return f"{first}; {second}" if first else second
