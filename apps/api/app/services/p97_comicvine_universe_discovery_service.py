"""P97-23A ComicVine volume universe discovery (metadata only, no issue import)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.services.comicvine_api_limits import (
    COMICVINE_MIN_SECONDS_BETWEEN_REQUESTS,
    comicvine_cache_key,
    read_comicvine_cache,
    write_comicvine_cache,
)
from app.services.comicvine_api_response import (
    ComicVineApiError,
    clamp_page_limit,
    parse_comicvine_payload,
    payload_results,
)
from app.services.comicvine_catalog_importer import COMICVINE_THROTTLE_STATUS, ComicVineThrottleError
from app.services.comicvine_importer_http import (
    DEFAULT_COMICVINE_BASE_URL,
    DEFAULT_DIAGNOSTIC_VOLUME_ID,
    comicvine_importer_base_url,
    comicvine_importer_request_headers,
)
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget

LOGGER = logging.getLogger(__name__)

VOLUME_FIELD_LIST = "id,name,start_year,publisher,count_of_issues,date_added,date_last_updated"
SEARCH_FIELD_LIST = (
    "id,name,start_year,publisher,count_of_issues,date_added,date_last_updated,resource_type"
)
MANUAL_VOLUME_SEARCH_FIELD_LIST = (
    "id,name,start_year,publisher,count_of_issues,site_detail_url,date_added,date_last_updated,resource_type"
)
REQUEST_TYPE = "universe_discovery"
VOLUMES_ENDPOINT = "volumes/"
SEARCH_ENDPOINT = "search/"
DISCOVERY_MODE_LIST = "list"
DISCOVERY_MODE_SEARCH = "search"
STATUS_ENDPOINT_FORBIDDEN = "endpoint_forbidden"


class ComicVineEndpointForbiddenError(RuntimeError):
    """ComicVine returned HTTP 403 — do not retry inline."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def search_discovery_buckets() -> tuple[str, ...]:
    """Alphanumeric search queries for volume discovery when ``/volumes/`` is forbidden."""
    singles = [str(digit) for digit in range(10)] + [chr(code) for code in range(ord("a"), ord("z") + 1)]
    double_digit = [f"{index:02d}" for index in range(100)]
    return tuple(singles + double_digit)


def parse_comicvine_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def publisher_name_from_row(row: dict[str, Any]) -> str | None:
    publisher = row.get("publisher")
    if isinstance(publisher, dict):
        name = publisher.get("name")
        return str(name).strip() if name else None
    if isinstance(publisher, str) and publisher.strip():
        return publisher.strip()
    return None


def volume_row_from_api(row: dict[str, Any]) -> dict[str, Any] | None:
    raw_id = row.get("id")
    if raw_id is None:
        return None
    try:
        volume_id = int(str(raw_id).split("-")[-1])
    except (TypeError, ValueError):
        return None
    name = str(row.get("name") or "").strip() or f"Volume {volume_id}"
    count_raw = row.get("count_of_issues")
    count_of_issues: int | None
    try:
        count_of_issues = int(count_raw) if count_raw is not None else None
    except (TypeError, ValueError):
        count_of_issues = None
    start_year_raw = row.get("start_year")
    start_year: int | None
    try:
        start_year = int(start_year_raw) if start_year_raw is not None else None
    except (TypeError, ValueError):
        start_year = None
    return {
        "volume_id": volume_id,
        "name": name,
        "publisher": publisher_name_from_row(row),
        "start_year": start_year,
        "count_of_issues": count_of_issues,
        "date_added": parse_comicvine_datetime(row.get("date_added")),
        "date_last_updated": parse_comicvine_datetime(row.get("date_last_updated")),
    }


def filter_volume_search_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("resource_type") in (None, "volume")]


@dataclass
class UniverseDiscoveryProgress:
    offset: int = 0
    volumes_in_db: int = 0
    number_of_total_results: int | None = None
    status: str = "idle"
    discovery_mode: str = DISCOVERY_MODE_LIST
    search_bucket_index: int = 0
    list_endpoint_forbidden: bool = False
    api_requests_this_run: int = 0
    pages_fetched_this_run: int = 0
    last_error: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> UniverseDiscoveryProgress:
        if not data:
            return cls()
        mode = str(data.get("discovery_mode") or DISCOVERY_MODE_LIST)
        if data.get("list_endpoint_forbidden") and mode == DISCOVERY_MODE_LIST:
            mode = DISCOVERY_MODE_SEARCH
        return cls(
            offset=int(data.get("offset") or 0),
            volumes_in_db=int(data.get("volumes_in_db") or 0),
            number_of_total_results=(
                int(data["number_of_total_results"])
                if data.get("number_of_total_results") is not None
                else None
            ),
            status=str(data.get("status") or "idle"),
            discovery_mode=mode,
            search_bucket_index=int(data.get("search_bucket_index") or 0),
            list_endpoint_forbidden=bool(data.get("list_endpoint_forbidden")),
            api_requests_this_run=int(data.get("api_requests_this_run") or 0),
            pages_fetched_this_run=int(data.get("pages_fetched_this_run") or 0),
            last_error=data.get("last_error"),
            updated_at=data.get("updated_at"),
        )

    def current_search_query(self) -> str | None:
        buckets = search_discovery_buckets()
        if self.search_bucket_index >= len(buckets):
            return None
        return buckets[self.search_bucket_index]


def load_discovery_progress(path: Path) -> UniverseDiscoveryProgress:
    if not path.is_file():
        return UniverseDiscoveryProgress()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return UniverseDiscoveryProgress()
    return UniverseDiscoveryProgress.from_dict(data if isinstance(data, dict) else None)


def save_discovery_progress(path: Path, progress: UniverseDiscoveryProgress) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    progress.updated_at = _utc_now().isoformat()
    path.write_text(json.dumps(progress.to_dict(), indent=2), encoding="utf-8")


@dataclass
class UniverseDiscoveryBatchResult:
    pages_fetched: int = 0
    api_requests: int = 0
    rows_seen: int = 0
    inserted: int = 0
    updated: int = 0
    offset_before: int = 0
    offset_after: int = 0
    number_of_total_results: int | None = None
    complete: bool = False
    throttled: bool = False
    endpoint_forbidden: bool = False
    switched_to_search: bool = False
    discovery_mode: str = DISCOVERY_MODE_LIST
    error: str | None = None


def upsert_universe_volume(session: Session, payload: dict[str, Any]) -> str:
    now = _utc_now()
    volume_id = int(payload["volume_id"])
    existing = session.exec(
        select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == volume_id)
    ).first()
    if existing is None:
        session.add(
            ComicVineVolumeUniverse(
                volume_id=volume_id,
                name=payload["name"],
                publisher=payload.get("publisher"),
                start_year=payload.get("start_year"),
                count_of_issues=payload.get("count_of_issues"),
                date_added=payload.get("date_added"),
                date_last_updated=payload.get("date_last_updated"),
                first_discovered_at=now,
                last_discovered_at=now,
            )
        )
        session.commit()
        return "inserted"
    existing.name = payload["name"]
    existing.publisher = payload.get("publisher")
    existing.start_year = payload.get("start_year")
    existing.count_of_issues = payload.get("count_of_issues")
    existing.date_added = payload.get("date_added")
    existing.date_last_updated = payload.get("date_last_updated")
    existing.last_discovered_at = now
    session.add(existing)
    session.commit()
    return "updated"


class ComicVineUniverseDiscoveryClient:
    """ComicVine fetcher using importer User-Agent and P97 request ledger budget."""

    def __init__(
        self,
        session: Session,
        budget: ComicVineRateBudget,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        user_agent: str | None = None,
        rate_limit_seconds: float | None = None,
        http_cache_enabled: bool | None = None,
        http_cache_dir: Path | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        self.session = session
        self.budget = budget
        self.settings = settings
        self.api_key = (api_key or settings.comicvine_api_key or "").strip()
        self.base_url = (base_url or comicvine_importer_base_url(settings)).rstrip("/")
        self.headers = comicvine_importer_request_headers(settings)
        if user_agent:
            self.headers = {"User-Agent": user_agent}
        self.rate_limit_seconds = max(
            float(rate_limit_seconds if rate_limit_seconds is not None else settings.catalog_import_sleep_seconds),
            COMICVINE_MIN_SECONDS_BETWEEN_REQUESTS,
        )
        self.http_cache_enabled = (
            settings.comicvine_http_cache_enabled if http_cache_enabled is None else http_cache_enabled
        )
        self.http_cache_dir = http_cache_dir
        self.sleep_fn = sleep_fn
        self._last_request_monotonic: float | None = None

    def _wait_before_request(self) -> None:
        gap = self.rate_limit_seconds
        if self._last_request_monotonic is not None:
            elapsed = time.monotonic() - self._last_request_monotonic
            remaining = gap - elapsed
            if remaining > 0:
                self.sleep_fn(remaining)
        self._last_request_monotonic = time.monotonic()

    def _wait_for_budget(self) -> bool:
        while True:
            if self.budget.should_pause_for_420():
                return False
            decision = self.budget.evaluate()
            if decision.allowed:
                return True
            wait = min(decision.seconds_until_next_request, 300.0)
            if wait <= 0:
                return True
            self.sleep_fn(wait)

    def _get_json(
        self,
        path: str,
        *,
        params: dict[str, Any],
        endpoint_label: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("COMICVINE_API_KEY is required for universe discovery")
        if not self._wait_for_budget():
            raise ComicVineThrottleError("ComicVine budget paused for HTTP 420")

        query = {"api_key": self.api_key, "format": "json", **params}
        cache_key = comicvine_cache_key(path, query)
        if self.http_cache_enabled and self.http_cache_dir is not None:
            cached = read_comicvine_cache(self.http_cache_dir, cache_key)
            if cached is not None:
                return parse_comicvine_payload(cached)

        self._wait_before_request()
        response = httpx.get(
            f"{self.base_url}/{path.lstrip('/')}",
            params=query,
            headers=self.headers,
            timeout=30.0,
        )

        if response.status_code == COMICVINE_THROTTLE_STATUS:
            self.budget.record_420(
                request_type=REQUEST_TYPE,
                endpoint=endpoint_label,
                metadata=metadata,
            )
            raise ComicVineThrottleError(f"ComicVine HTTP 420 on {endpoint_label}")

        self.budget.record_request(
            request_type=REQUEST_TYPE,
            endpoint=endpoint_label,
            status_code=response.status_code,
            metadata=metadata,
        )

        if response.status_code == 403:
            raise ComicVineEndpointForbiddenError(f"ComicVine HTTP 403 on {endpoint_label}")

        response.raise_for_status()
        payload = parse_comicvine_payload(response.json())
        if self.http_cache_enabled and self.http_cache_dir is not None:
            write_comicvine_cache(self.http_cache_dir, cache_key, payload)
        return payload

    def fetch_volume_list_page(self, *, offset: int, limit: int = 100) -> dict[str, Any]:
        page_limit = clamp_page_limit(limit, path=VOLUMES_ENDPOINT)
        return self._get_json(
            VOLUMES_ENDPOINT,
            params={
                "offset": int(offset),
                "limit": page_limit,
                "field_list": VOLUME_FIELD_LIST,
            },
            endpoint_label=VOLUMES_ENDPOINT,
            metadata={"offset": offset, "limit": page_limit, "mode": DISCOVERY_MODE_LIST},
        )

    def fetch_publisher_volumes_page(
        self,
        *,
        publisher_filter: str,
        offset: int,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List ComicVine volumes filtered by publisher name (targeted discovery)."""
        page_limit = clamp_page_limit(limit, path=VOLUMES_ENDPOINT)
        return self._get_json(
            VOLUMES_ENDPOINT,
            params={
                "offset": int(offset),
                "limit": page_limit,
                "field_list": VOLUME_FIELD_LIST,
                "filter": f"publisher:{publisher_filter}",
            },
            endpoint_label=VOLUMES_ENDPOINT,
            metadata={
                "offset": offset,
                "limit": page_limit,
                "mode": "publisher_filter",
                "publisher_filter": publisher_filter,
            },
        )

    def fetch_volume_search_page(
        self,
        *,
        query: str,
        offset: int,
        limit: int = 10,
        field_list: str | None = None,
    ) -> dict[str, Any]:
        page_limit = clamp_page_limit(limit, path=SEARCH_ENDPOINT)
        return self._get_json(
            SEARCH_ENDPOINT,
            params={
                "query": query,
                "resources": "volume",
                "offset": int(offset),
                "limit": page_limit,
                "field_list": field_list or SEARCH_FIELD_LIST,
            },
            endpoint_label=SEARCH_ENDPOINT,
            metadata={"query": query, "offset": offset, "limit": page_limit, "mode": DISCOVERY_MODE_SEARCH},
        )

    def fetch_volume_detail(self, *, volume_id: int) -> dict[str, Any]:
        path = f"volume/4050-{int(volume_id)}/"
        return self._get_json(
            path,
            params={"field_list": VOLUME_FIELD_LIST},
            endpoint_label=path,
            metadata={"volume_id": volume_id, "mode": "detail"},
        )

    def probe_endpoints(self, *, volume_id: int = DEFAULT_DIAGNOSTIC_VOLUME_ID) -> dict[str, Any]:
        """Probe list, search, and detail endpoints (one request each, no retries on 403)."""
        results: dict[str, Any] = {
            "base_url": self.base_url,
            "user_agent": self.headers.get("User-Agent"),
            "volume_id": volume_id,
        }

        def _probe(label: str, fn: Callable[[], dict[str, Any]]) -> None:
            try:
                payload = fn()
                rows = payload_results(payload)
                results[label] = {
                    "ok": True,
                    "status_code": 200,
                    "result_count": len(rows),
                    "number_of_total_results": payload.get("number_of_total_results"),
                }
            except ComicVineEndpointForbiddenError as exc:
                results[label] = {"ok": False, "status_code": 403, "error": str(exc)}
            except ComicVineThrottleError as exc:
                results[label] = {"ok": False, "status_code": 420, "error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                results[label] = {"ok": False, "status_code": None, "error": str(exc)}

        _probe("volumes_list", lambda: self.fetch_volume_list_page(offset=0, limit=1))
        _probe("search_volumes", lambda: self.fetch_volume_search_page(query="spider", offset=0, limit=1))
        _probe("volume_detail", lambda: self.fetch_volume_detail(volume_id=volume_id))
        return results


def _ingest_rows(session: Session, rows: list[dict[str, Any]], result: UniverseDiscoveryBatchResult) -> None:
    for row in rows:
        parsed = volume_row_from_api(row)
        if parsed is None:
            continue
        result.rows_seen += 1
        outcome = upsert_universe_volume(session, parsed)
        if outcome == "inserted":
            result.inserted += 1
        else:
            result.updated += 1


def _process_list_page(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    progress: UniverseDiscoveryProgress,
    result: UniverseDiscoveryBatchResult,
) -> bool:
    """Fetch one list page. Returns False to stop the batch loop."""
    try:
        payload = client.fetch_volume_list_page(offset=progress.offset, limit=100)
    except ComicVineEndpointForbiddenError as exc:
        progress.list_endpoint_forbidden = True
        progress.discovery_mode = DISCOVERY_MODE_SEARCH
        progress.offset = 0
        progress.search_bucket_index = 0
        result.switched_to_search = True
        result.discovery_mode = DISCOVERY_MODE_SEARCH
        LOGGER.warning("ComicVine /volumes/ forbidden (403); switching to search discovery: %s", exc)
        return True
    except ComicVineThrottleError as exc:
        result.throttled = True
        result.error = str(exc)
        return False
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)
        return False

    result.api_requests += 1
    result.pages_fetched += 1
    total_raw = payload.get("number_of_total_results")
    if total_raw is not None:
        try:
            result.number_of_total_results = int(total_raw)
            progress.number_of_total_results = result.number_of_total_results
        except (TypeError, ValueError):
            pass

    page_rows = payload_results(payload)
    if not page_rows:
        result.complete = True
        return False

    _ingest_rows(session, page_rows, result)
    progress.offset += len(page_rows)
    result.offset_after = progress.offset
    if len(page_rows) < 100:
        result.complete = True
        return False
    return True


def _process_search_page(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    progress: UniverseDiscoveryProgress,
    result: UniverseDiscoveryBatchResult,
) -> bool:
    query = progress.current_search_query()
    if query is None:
        result.complete = True
        return False

    try:
        payload = client.fetch_volume_search_page(query=query, offset=progress.offset, limit=10)
    except ComicVineEndpointForbiddenError as exc:
        result.endpoint_forbidden = True
        result.error = str(exc)
        progress.status = STATUS_ENDPOINT_FORBIDDEN
        return False
    except ComicVineThrottleError as exc:
        result.throttled = True
        result.error = str(exc)
        return False
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)
        return False

    result.api_requests += 1
    result.pages_fetched += 1
    result.discovery_mode = DISCOVERY_MODE_SEARCH
    page_rows = filter_volume_search_rows(payload_results(payload))
    if not page_rows:
        progress.search_bucket_index += 1
        progress.offset = 0
        if progress.current_search_query() is None:
            result.complete = True
        return progress.current_search_query() is not None

    _ingest_rows(session, page_rows, result)
    progress.offset += len(page_rows)
    result.offset_after = progress.offset
    if len(page_rows) < 10:
        progress.search_bucket_index += 1
        progress.offset = 0
        if progress.current_search_query() is None:
            result.complete = True
    return not result.complete and progress.current_search_query() is not None


def discover_universe_batch(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    progress: UniverseDiscoveryProgress,
    *,
    max_pages: int = 1,
) -> UniverseDiscoveryBatchResult:
    result = UniverseDiscoveryBatchResult(
        offset_before=int(progress.offset),
        offset_after=int(progress.offset),
        discovery_mode=progress.discovery_mode,
    )

    target_pages = max(1, int(max_pages))
    while result.pages_fetched < target_pages:
        if progress.discovery_mode == DISCOVERY_MODE_LIST:
            continue_loop = _process_list_page(session, client, progress, result)
        else:
            continue_loop = _process_search_page(session, client, progress, result)

        result.offset_after = progress.offset
        result.discovery_mode = progress.discovery_mode

        if result.switched_to_search:
            result.switched_to_search = False
            if result.endpoint_forbidden or result.throttled or result.error:
                break
            continue

        if result.endpoint_forbidden or result.throttled or result.error or result.complete:
            break
        if not continue_loop:
            break

    return result
