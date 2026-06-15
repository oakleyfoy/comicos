"""P97-23A ComicVine volume universe discovery (metadata only, no issue import)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.services.comicvine_api_limits import (
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
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://comicvine.gamespot.com/api"
VOLUME_FIELD_LIST = "id,name,start_year,publisher,count_of_issues,date_added,date_last_updated"
REQUEST_TYPE = "universe_discovery"
VOLUMES_ENDPOINT = "volumes/"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


@dataclass
class UniverseDiscoveryProgress:
    offset: int = 0
    volumes_in_db: int = 0
    number_of_total_results: int | None = None
    status: str = "idle"
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
        return cls(
            offset=int(data.get("offset") or 0),
            volumes_in_db=int(data.get("volumes_in_db") or 0),
            number_of_total_results=(
                int(data["number_of_total_results"])
                if data.get("number_of_total_results") is not None
                else None
            ),
            status=str(data.get("status") or "idle"),
            api_requests_this_run=int(data.get("api_requests_this_run") or 0),
            pages_fetched_this_run=int(data.get("pages_fetched_this_run") or 0),
            last_error=data.get("last_error"),
            updated_at=data.get("updated_at"),
        )


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
    stopped_for_budget: bool = False
    error: str | None = None


def upsert_universe_volume(session: Session, payload: dict[str, Any]) -> str:
    """Insert or update a universe row. Returns ``inserted`` or ``updated``."""
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
    """ComicVine list fetcher that respects the P97 request ledger budget."""

    def __init__(
        self,
        session: Session,
        budget: ComicVineRateBudget,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        http_cache_enabled: bool | None = None,
        http_cache_dir: Path | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        self.session = session
        self.budget = budget
        self.api_key = (api_key or settings.comicvine_api_key or "").strip()
        self.base_url = (base_url or settings.comicvine_api_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.http_cache_enabled = (
            settings.comicvine_http_cache_enabled if http_cache_enabled is None else http_cache_enabled
        )
        self.http_cache_dir = http_cache_dir
        self.sleep_fn = sleep_fn

    def _wait_for_budget(self) -> bool:
        """Wait until a request is allowed. Returns False if paused for 420."""
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

    def fetch_volume_page(self, *, offset: int, limit: int = 100) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("COMICVINE_API_KEY is required for universe discovery")
        if not self._wait_for_budget():
            raise ComicVineThrottleError("ComicVine budget paused for HTTP 420")
        page_limit = clamp_page_limit(limit, path=VOLUMES_ENDPOINT)
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "format": "json",
            "offset": int(offset),
            "limit": page_limit,
            "field_list": VOLUME_FIELD_LIST,
        }
        cache_key = comicvine_cache_key(VOLUMES_ENDPOINT, params)
        if self.http_cache_enabled and self.http_cache_dir is not None:
            cached = read_comicvine_cache(self.http_cache_dir, cache_key)
            if cached is not None:
                return parse_comicvine_payload(cached)

        try:
            response = httpx.get(
                f"{self.base_url}/{VOLUMES_ENDPOINT}",
                params=params,
                timeout=30.0,
            )
            if response.status_code == COMICVINE_THROTTLE_STATUS:
                self.budget.record_420(
                    request_type=REQUEST_TYPE,
                    endpoint=VOLUMES_ENDPOINT,
                    metadata={"offset": offset},
                )
                raise ComicVineThrottleError(f"ComicVine HTTP 420 on {VOLUMES_ENDPOINT}")
            self.budget.record_request(
                request_type=REQUEST_TYPE,
                endpoint=VOLUMES_ENDPOINT,
                status_code=response.status_code,
                metadata={"offset": offset, "limit": page_limit},
            )
            response.raise_for_status()
            payload = parse_comicvine_payload(response.json())
        except ComicVineThrottleError:
            raise
        except ComicVineApiError:
            raise
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(str(exc)) from exc

        if self.http_cache_enabled and self.http_cache_dir is not None:
            write_comicvine_cache(self.http_cache_dir, cache_key, payload)
        return payload


def discover_universe_batch(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    *,
    offset: int,
    max_pages: int = 1,
) -> UniverseDiscoveryBatchResult:
    result = UniverseDiscoveryBatchResult(offset_before=int(offset), offset_after=int(offset))
    current_offset = int(offset)

    for _ in range(max(1, int(max_pages))):
        try:
            payload = client.fetch_volume_page(offset=current_offset, limit=100)
        except ComicVineThrottleError as exc:
            result.throttled = True
            result.error = str(exc)
            break
        except Exception as exc:  # noqa: BLE001
            result.error = str(exc)
            break

        result.api_requests += 1
        result.pages_fetched += 1
        total_raw = payload.get("number_of_total_results")
        if total_raw is not None:
            try:
                result.number_of_total_results = int(total_raw)
            except (TypeError, ValueError):
                pass

        page_rows = payload_results(payload)
        if not page_rows:
            result.complete = True
            break

        for row in page_rows:
            parsed = volume_row_from_api(row)
            if parsed is None:
                continue
            result.rows_seen += 1
            outcome = upsert_universe_volume(session, parsed)
            if outcome == "inserted":
                result.inserted += 1
            else:
                result.updated += 1

        current_offset += len(page_rows)
        result.offset_after = current_offset
        if len(page_rows) < 100:
            result.complete = True
            break

    return result
