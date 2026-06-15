"""Manual ComicVine volume search and issue-import queue requests (P97)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.comicvine_api_response import payload_results
from app.services.p97_comicvine_universe_discovery_service import (
    MANUAL_VOLUME_SEARCH_FIELD_LIST,
    ComicVineUniverseDiscoveryClient,
    filter_volume_search_rows,
    upsert_universe_volume,
    volume_row_from_api,
)
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
    volume_coverage_percent,
)
from app.services.p97_volume_issue_import_queue_service import STATUS_PENDING, STATUS_RUNNING
from app.services.p97_volume_issue_queue_priority import (
    TIER_0_MANUAL,
    compute_manual_request_priority,
)

REQUEST_TYPE_MANUAL_SEARCH = "manual_volume_search"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def publisher_filter_matches(candidate: str | None, publisher_filter: str | None) -> bool:
    if not publisher_filter or not str(publisher_filter).strip():
        return True
    needle = normalize_series_name(publisher_filter)
    hay = normalize_series_name(candidate or "")
    if not needle:
        return True
    if not hay:
        return False
    if hay == needle:
        return True
    if hay.startswith(f"{needle} ") or needle.startswith(f"{hay} "):
        return True
    return False


@dataclass(frozen=True)
class VolumeSearchCandidate:
    volume_id: int
    name: str
    publisher: str | None
    start_year: int | None
    count_of_issues: int | None
    site_detail_url: str | None


def _site_detail_url_from_row(row: dict[str, Any]) -> str | None:
    url = row.get("site_detail_url")
    if url is None:
        return None
    text = str(url).strip()
    return text or None


def parse_volume_search_candidate(row: dict[str, Any]) -> VolumeSearchCandidate | None:
    payload = volume_row_from_api(row)
    if payload is None:
        return None
    return VolumeSearchCandidate(
        volume_id=int(payload["volume_id"]),
        name=str(payload["name"]),
        publisher=payload.get("publisher"),
        start_year=payload.get("start_year"),
        count_of_issues=payload.get("count_of_issues"),
        site_detail_url=_site_detail_url_from_row(row),
    )


def search_comicvine_volumes_for_request(
    client: ComicVineUniverseDiscoveryClient,
    *,
    query: str,
    publisher: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[VolumeSearchCandidate]:
    payload = client.fetch_volume_search_page(
        query=query.strip(),
        offset=max(0, int(offset)),
        limit=max(1, min(int(limit), 100)),
        field_list=MANUAL_VOLUME_SEARCH_FIELD_LIST,
    )
    rows = filter_volume_search_rows(payload_results(payload))
    candidates: list[VolumeSearchCandidate] = []
    for row in rows:
        candidate = parse_volume_search_candidate(row)
        if candidate is None:
            continue
        if not publisher_filter_matches(candidate.publisher, publisher):
            continue
        candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def volume_payload_from_detail(detail: dict[str, Any], *, volume_id: int) -> dict[str, Any]:
    row = dict(detail)
    row.setdefault("id", volume_id)
    parsed = volume_row_from_api(row)
    if parsed is None:
        raise ValueError(f"Invalid ComicVine volume detail for id {volume_id}")
    return parsed


@dataclass
class ManualVolumeRequestResult:
    volume_id: int
    universe_action: str
    queue_action: str
    queue_row: P97VolumeIssueImportQueue


def enqueue_manual_volume_request(
    session: Session,
    *,
    volume_id: int,
    notes: str | None = None,
    urgent: bool = False,
    volume_payload: dict[str, Any] | None = None,
) -> ManualVolumeRequestResult:
    if volume_payload is None:
        universe = session.exec(
            select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == volume_id)
        ).first()
        if universe is None:
            raise ValueError(
                f"Volume {volume_id} is not in comicvine_volume_universe; "
                "fetch detail via ComicVine client first"
            )
        volume_payload = {
            "volume_id": volume_id,
            "name": universe.name,
            "publisher": universe.publisher,
            "start_year": universe.start_year,
            "count_of_issues": universe.count_of_issues,
            "date_added": universe.date_added,
            "date_last_updated": universe.date_last_updated,
        }

    universe_action = upsert_universe_volume(session, volume_payload)
    indexes = build_catalog_coverage_indexes(session)
    name = str(volume_payload["name"])
    publisher = volume_payload.get("publisher")
    count_of_issues = int(volume_payload.get("count_of_issues") or 0)
    existing = existing_issue_count_for_volume(
        volume_id=volume_id,
        name=name,
        publisher=publisher,
        indexes=indexes,
    )
    missing = max(count_of_issues - existing, 0)
    coverage = volume_coverage_percent(
        count_of_issues=count_of_issues,
        existing_issue_count=existing,
    )
    priority = compute_manual_request_priority(urgent=urgent)
    now = _utc_now()

    existing_row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == volume_id
        )
    ).first()

    if existing_row is None:
        row = P97VolumeIssueImportQueue(
            comicvine_volume_id=volume_id,
            name=name,
            publisher=publisher,
            count_of_issues=count_of_issues,
            existing_issue_count=existing,
            missing_issue_count=missing,
            coverage_percent=coverage,
            priority_score=priority.priority_score,
            launch_priority_tier=priority.launch_priority_tier,
            request_notes=(notes or "").strip() or None,
            status=STATUS_PENDING,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return ManualVolumeRequestResult(
            volume_id=volume_id,
            universe_action=universe_action,
            queue_action="inserted",
            queue_row=row,
        )

    existing_row.name = name
    existing_row.publisher = publisher
    existing_row.count_of_issues = count_of_issues
    existing_row.existing_issue_count = existing
    existing_row.missing_issue_count = missing
    existing_row.coverage_percent = coverage
    existing_row.priority_score = priority.priority_score
    existing_row.launch_priority_tier = TIER_0_MANUAL
    if notes is not None and str(notes).strip():
        existing_row.request_notes = str(notes).strip()
    if existing_row.status != STATUS_RUNNING:
        existing_row.status = STATUS_PENDING
    existing_row.updated_at = now
    session.add(existing_row)
    session.commit()
    session.refresh(existing_row)
    return ManualVolumeRequestResult(
        volume_id=volume_id,
        universe_action=universe_action,
        queue_action="updated",
        queue_row=existing_row,
    )


def _volume_detail_dict(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results")
    if isinstance(results, dict):
        return results
    rows = payload_results(payload)
    if rows:
        return rows[0]
    raise ValueError("ComicVine volume detail missing results")


def fetch_and_enqueue_manual_volume_request(
    client: ComicVineUniverseDiscoveryClient,
    session: Session,
    *,
    volume_id: int,
    notes: str | None = None,
    urgent: bool = False,
) -> ManualVolumeRequestResult:
    detail_payload = client.fetch_volume_detail(volume_id=volume_id)
    detail = _volume_detail_dict(detail_payload)
    volume_payload = volume_payload_from_detail(detail, volume_id=volume_id)
    return enqueue_manual_volume_request(
        session,
        volume_id=volume_id,
        notes=notes,
        urgent=urgent,
        volume_payload=volume_payload,
    )
