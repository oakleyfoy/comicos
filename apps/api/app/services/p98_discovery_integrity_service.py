"""P98/P97 bridge integrity — probe rows and dual-table membership."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseVolume
from app.services.comicvine_api_response import payload_results
from app.services.p97_comicvine_universe_discovery_service import (
    ComicVineUniverseDiscoveryClient,
    volume_row_from_api,
)
from app.services.p98_major_publisher_registry import MajorPublisherConfig, resolve_major_publisher


@dataclass
class VolumeMembership:
    in_comicvine_volume_universe: bool
    in_universe_volume: bool

    @property
    def missing_from_both(self) -> bool:
        return not self.in_comicvine_volume_universe and not self.in_universe_volume

    @property
    def missing_from_p98_only(self) -> bool:
        return self.in_comicvine_volume_universe and not self.in_universe_volume


def comicvine_universe_volume_ids(session: Session) -> set[int]:
    return {int(v) for v in session.exec(select(ComicVineVolumeUniverse.volume_id)).all()}


def p98_universe_volume_ids(session: Session) -> set[int]:
    return {int(v) for v in session.exec(select(UniverseVolume.comicvine_volume_id)).all()}


def membership_for(session: Session, comicvine_volume_id: int) -> VolumeMembership:
    cv_ids = comicvine_universe_volume_ids(session)
    p98_ids = p98_universe_volume_ids(session)
    return VolumeMembership(
        in_comicvine_volume_universe=int(comicvine_volume_id) in cv_ids,
        in_universe_volume=int(comicvine_volume_id) in p98_ids,
    )


@dataclass
class PublisherVolumeProbeRow:
    comicvine_volume_id: int
    name: str
    publisher_name: str | None
    start_year: int | None
    issue_count: int
    date_added: str | None
    date_last_updated: str | None
    in_comicvine_volume_universe: bool
    in_universe_volume: bool
    api_publisher_raw: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "name": self.name,
            "publisher_name": self.publisher_name,
            "start_year": self.start_year,
            "issue_count": self.issue_count,
            "date_added": self.date_added,
            "date_last_updated": self.date_last_updated,
            "in_comicvine_volume_universe": self.in_comicvine_volume_universe,
            "in_universe_volume": self.in_universe_volume,
            "api_publisher_raw": self.api_publisher_raw,
        }


@dataclass
class PublisherVolumeProbeReport:
    publisher: str
    comicvine_filter: str
    rows: list[PublisherVolumeProbeRow] = field(default_factory=list)
    total_scanned: int = 0
    distinct_comicvine_ids: int = 0
    publishers_observed: list[str] = field(default_factory=list)
    in_cv_universe: int = 0
    in_p98_universe: int = 0
    missing_from_both: int = 0
    missing_from_p98_only: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "comicvine_filter": self.comicvine_filter,
            "total_scanned": self.total_scanned,
            "distinct_comicvine_ids": self.distinct_comicvine_ids,
            "publishers_observed": self.publishers_observed,
            "in_cv_universe": self.in_cv_universe,
            "in_p98_universe": self.in_p98_universe,
            "missing_from_both": self.missing_from_both,
            "missing_from_p98_only": self.missing_from_p98_only,
            "error": self.error,
            "rows": [r.as_dict() for r in self.rows],
        }


def _format_dt(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def probe_publisher_volumes(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    *,
    publisher: str,
    limit_pages: int = 1,
    max_display_rows: int = 25,
) -> PublisherVolumeProbeReport:
    config = resolve_major_publisher(publisher)
    if config is None:
        return PublisherVolumeProbeReport(
            publisher=publisher,
            comicvine_filter="",
            error=f"Not a major publisher: {publisher!r}",
        )
    filter_name = config.expected_comicvine_publisher_names[0]
    report = PublisherVolumeProbeReport(publisher=config.canonical, comicvine_filter=filter_name)
    cv_ids = comicvine_universe_volume_ids(session)
    p98_ids = p98_universe_volume_ids(session)
    seen_ids: set[int] = set()
    publishers_seen: set[str] = set()
    all_rows: list[PublisherVolumeProbeRow] = []

    offset = 0
    pages = max(1, int(limit_pages))
    page_size = 100
    for _ in range(pages):
        try:
            payload = client.fetch_publisher_volumes_page(
                publisher_filter=filter_name,
                offset=offset,
                limit=page_size,
            )
        except Exception as exc:  # noqa: BLE001
            report.error = str(exc)
            break
        api_rows = payload_results(payload)
        if not api_rows:
            break
        for raw in api_rows:
            parsed = volume_row_from_api(raw)
            if parsed is None:
                continue
            cv_id = int(parsed["volume_id"])
            pub_name = parsed.get("publisher")
            if pub_name:
                publishers_seen.add(str(pub_name))
            seen_ids.add(cv_id)
            in_cv = cv_id in cv_ids
            in_p98 = cv_id in p98_ids
            if in_cv:
                report.in_cv_universe += 1
            if in_p98:
                report.in_p98_universe += 1
            if not in_cv and not in_p98:
                report.missing_from_both += 1
            elif in_cv and not in_p98:
                report.missing_from_p98_only += 1
            all_rows.append(
                PublisherVolumeProbeRow(
                    comicvine_volume_id=cv_id,
                    name=str(parsed["name"]),
                    publisher_name=str(pub_name) if pub_name else None,
                    start_year=parsed.get("start_year"),
                    issue_count=int(parsed.get("count_of_issues") or 0),
                    date_added=_format_dt(parsed.get("date_added")),
                    date_last_updated=_format_dt(parsed.get("date_last_updated")),
                    in_comicvine_volume_universe=in_cv,
                    in_universe_volume=in_p98,
                    api_publisher_raw=str(pub_name) if pub_name else None,
                )
            )
        offset += len(api_rows)
        report.total_scanned += len(api_rows)
        if len(api_rows) < page_size:
            break

    report.distinct_comicvine_ids = len(seen_ids)
    report.publishers_observed = sorted(publishers_seen)
    report.rows = all_rows[: max(1, int(max_display_rows))]
    return report
