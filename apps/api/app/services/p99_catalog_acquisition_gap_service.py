"""P99-01 — Catalog acquisition / import gap analysis (read-only)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import CatalogImportError, ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.models.universe import (
    UNIVERSE_ISSUE_STATUS_CATALOGED,
    UNIVERSE_ISSUE_STATUS_DISCOVERED,
    UniverseIssue,
    UniversePublisher,
    UniverseVolume,
)
from app.services.p98_gap_priority_service import major_publisher_for, score_volume
from app.services.p98_major_publisher_completeness_service import (
    OPTIONAL_PUBLISHERS,
    REQUIRED_PUBLISHERS,
    _resolve_publisher_label,
)
from app.services.p98_publisher_match_repair_service import VOLUME_STATUS_FOREIGN_SUPERSEDED
from app.services.p98_skeleton_gap_service import _issue_count_maps
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)
from app.services.p97_volume_issue_import_queue_service import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SKIPPED,
)
from app.services.universe.universe_health_service import compute_skeleton_health

REPORT_REL = Path("data/p99/catalog_acquisition_gap_report.json")
TOP_PUBLISHERS_REL = Path("data/p99/top_acquisition_gap_publishers.json")
TOP_VOLUMES_REL = Path("data/p99/top_acquisition_gap_volumes.json")

CATEGORY_NOT_QUEUED = "NOT_QUEUED"
CATEGORY_QUEUED_PENDING = "QUEUED_PENDING"
CATEGORY_QUEUED_RUNNING = "QUEUED_RUNNING"
CATEGORY_IMPORT_FAILED = "IMPORT_FAILED"
CATEGORY_IMPORT_SKIPPED = "IMPORT_SKIPPED"
CATEGORY_MISSING_SOURCE_DATA = "MISSING_SOURCE_DATA"
CATEGORY_MISSING_COMICVINE_DATA = "MISSING_COMICVINE_DATA"
CATEGORY_BLOCKED_BY_MATCHING = "BLOCKED_BY_MATCHING"
CATEGORY_UNKNOWN = "UNKNOWN"

HIGH_VALUE_PUBLISHER_LABELS: frozenset[str] = frozenset(
    (*REQUIRED_PUBLISHERS, *OPTIONAL_PUBLISHERS, "Titan Comics")
)

GAP_CATEGORIES: tuple[str, ...] = (
    CATEGORY_NOT_QUEUED,
    CATEGORY_QUEUED_PENDING,
    CATEGORY_QUEUED_RUNNING,
    CATEGORY_IMPORT_FAILED,
    CATEGORY_IMPORT_SKIPPED,
    CATEGORY_MISSING_SOURCE_DATA,
    CATEGORY_MISSING_COMICVINE_DATA,
    CATEGORY_BLOCKED_BY_MATCHING,
    CATEGORY_UNKNOWN,
)


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_report_path() -> Path:
    return _api_root() / REPORT_REL


def default_top_publishers_path() -> Path:
    return _api_root() / TOP_PUBLISHERS_REL


def default_top_volumes_path() -> Path:
    return _api_root() / TOP_VOLUMES_REL


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coverage_percent(catalog: int, shells: int) -> float:
    if shells <= 0:
        return 100.0 if catalog <= 0 else 0.0
    return round(min(100.0, catalog / shells * 100.0), 2)


def _queue_status_label(row: P97VolumeIssueImportQueue | None) -> str:
    if row is None:
        return "not_queued"
    return (row.status or "unknown").lower()


def _acquisition_status(
    issue_status: str,
    queue_row: P97VolumeIssueImportQueue | None,
) -> str:
    if issue_status == UNIVERSE_ISSUE_STATUS_CATALOGED:
        return "CATALOGED"
    q = _queue_status_label(queue_row)
    if q == "not_queued":
        return "SHELL_ONLY"
    if q in (STATUS_PENDING, STATUS_RUNNING):
        return "AWAITING_IMPORT"
    if q == STATUS_FAILED:
        return "IMPORT_FAILED"
    if q == STATUS_SKIPPED:
        return "IMPORT_SKIPPED"
    if q == STATUS_COMPLETE:
        return "IMPORT_COMPLETE_GAP_REMAINS"
    return "AWAITING_IMPORT"


def _import_error_index(session: Session) -> dict[str, list[CatalogImportError]]:
    by_ext: dict[str, list[CatalogImportError]] = defaultdict(list)
    for err in session.exec(select(CatalogImportError)).all():
        ext = (err.external_id or "").strip()
        if ext:
            by_ext[ext].append(err)
    return by_ext


def classify_gap_reason(
    *,
    comicvine_issue_id: int | None,
    queue_row: P97VolumeIssueImportQueue | None,
    import_errors_by_ext: dict[str, list[CatalogImportError]],
) -> str:
    if queue_row is None:
        if comicvine_issue_id is None:
            return CATEGORY_MISSING_SOURCE_DATA
        return CATEGORY_NOT_QUEUED

    status = (queue_row.status or "").lower()
    if status == STATUS_PENDING:
        return CATEGORY_QUEUED_PENDING
    if status == STATUS_RUNNING:
        return CATEGORY_QUEUED_RUNNING
    if status == STATUS_FAILED:
        return CATEGORY_IMPORT_FAILED
    if status == STATUS_SKIPPED:
        return CATEGORY_IMPORT_SKIPPED

    if comicvine_issue_id is None:
        return CATEGORY_MISSING_COMICVINE_DATA

    ext_key = str(comicvine_issue_id)
    errors = import_errors_by_ext.get(ext_key, [])
    if errors:
        for err in errors:
            et = (err.error_type or "").lower()
            msg = (err.error_message or "").lower()
            if "match" in et or "match" in msg or "duplicate" in msg or "conflict" in msg:
                return CATEGORY_BLOCKED_BY_MATCHING
        return CATEGORY_IMPORT_FAILED

    if status == STATUS_COMPLETE:
        notes = (queue_row.request_notes or "").lower()
        if "skip" in notes:
            return CATEGORY_IMPORT_SKIPPED
        if comicvine_issue_id is None:
            return CATEGORY_MISSING_COMICVINE_DATA
        return CATEGORY_UNKNOWN

    return CATEGORY_UNKNOWN


@dataclass
class AcquisitionGapIssueSample:
    publisher: str
    volume: str
    issue_number: str
    issue_name: str | None
    release_date: str | None
    shell_created_at: str | None
    queue_status: str
    acquisition_status: str
    gap_reason: str
    comicvine_volume_id: int
    comicvine_issue_id: int | None
    priority_score: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "volume": self.volume,
            "issue_number": self.issue_number,
            "issue_name": self.issue_name,
            "release_date": self.release_date,
            "shell_created_at": self.shell_created_at,
            "queue_status": self.queue_status,
            "acquisition_status": self.acquisition_status,
            "gap_reason": self.gap_reason,
            "comicvine_volume_id": self.comicvine_volume_id,
            "comicvine_issue_id": self.comicvine_issue_id,
            "priority_score": self.priority_score,
        }


@dataclass
class PublisherAcquisitionGap:
    publisher: str
    shells: int
    catalog_issues: int
    import_gap: int
    coverage_percent: float
    top_missing_volumes: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "shells": self.shells,
            "catalog_issues": self.catalog_issues,
            "import_gap": self.import_gap,
            "coverage_percent": self.coverage_percent,
            "top_missing_volumes": self.top_missing_volumes,
        }


@dataclass
class VolumeAcquisitionGap:
    publisher: str
    volume: str
    comicvine_volume_id: int
    shells: int
    catalog_issues: int
    gap: int
    queue_status: str
    collector_priority_score: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "volume": self.volume,
            "comicvine_volume_id": self.comicvine_volume_id,
            "shells": self.shells,
            "catalog_issues": self.catalog_issues,
            "gap": self.gap,
            "queue_status": self.queue_status,
            "collector_priority_score": self.collector_priority_score,
        }


@dataclass
class CatalogAcquisitionGapReport:
    generated_at: str
    global_summary: dict[str, Any]
    gap_by_category: list[dict[str, Any]]
    publishers: list[PublisherAcquisitionGap]
    high_value_gap_issues: list[dict[str, Any]]
    top_volumes: list[VolumeAcquisitionGap]
    issue_samples: list[AcquisitionGapIssueSample]
    final_answers: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "global_summary": self.global_summary,
            "gap_by_category": self.gap_by_category,
            "publishers": [p.as_dict() for p in self.publishers],
            "high_value_gap_issues": self.high_value_gap_issues,
            "top_volumes": [v.as_dict() for v in self.top_volumes],
            "issue_samples": [s.as_dict() for s in self.issue_samples],
            "final_answers": self.final_answers,
        }


def build_catalog_acquisition_gap_report(
    session: Session,
    *,
    issue_sample_limit: int = 500,
    top_publishers: int = 100,
    top_volumes: int = 250,
    high_value_issue_limit: int = 200,
) -> CatalogAcquisitionGapReport:
    health = compute_skeleton_health(session)
    import_gap_universe = health.discovered_only_issues
    shells_total = health.issues
    catalog_linked_universe = health.catalog_linked_issues

    indexes = build_catalog_coverage_indexes(session)
    catalog_series_total = 0
    for cv in session.exec(select(ComicVineVolumeUniverse)).all():
        catalog_series_total += existing_issue_count_for_volume(
            volume_id=int(cv.volume_id),
            name=cv.name,
            publisher=cv.publisher,
            indexes=indexes,
        )
    import_gap_headline = max(shells_total - catalog_series_total, 0)

    queue_by_cv = {
        int(r.comicvine_volume_id): r
        for r in session.exec(select(P97VolumeIssueImportQueue)).all()
    }
    import_errors = _import_error_index(session)

    pub_id_to_name = {
        int(pid): name
        for pid, name in session.exec(select(UniversePublisher.id, UniversePublisher.name)).all()
        if pid is not None
    }
    pub_id_to_norm = {
        int(pid): norm
        for pid, norm in session.exec(
            select(UniversePublisher.id, UniversePublisher.normalized_name)
        ).all()
        if pid is not None
    }

    total_by_vol, cataloged_by_vol = _issue_count_maps(session)

    category_counts: Counter[str] = Counter()
    high_value_rows: list[AcquisitionGapIssueSample] = []
    issue_samples: list[AcquisitionGapIssueSample] = []

    stmt = (
        select(UniverseIssue, UniverseVolume, UniversePublisher)
        .join(UniverseVolume, UniverseIssue.volume_id == UniverseVolume.id)
        .join(UniversePublisher, UniverseVolume.publisher_id == UniversePublisher.id)
        .where(UniverseIssue.status == UNIVERSE_ISSUE_STATUS_DISCOVERED)
    )
    for issue, vol, pub in session.exec(stmt).all():
        if (vol.volume_status or "").lower() == VOLUME_STATUS_FOREIGN_SUPERSEDED:
            continue
        cv_id = int(vol.comicvine_volume_id)
        queue_row = queue_by_cv.get(cv_id)
        reason = classify_gap_reason(
            comicvine_issue_id=issue.comicvine_issue_id,
            queue_row=queue_row,
            import_errors_by_ext=import_errors,
        )
        category_counts[reason] += 1

        pub_name = pub.name
        pub_norm = pub.normalized_name or ""
        priority = score_volume(
            publisher_normalized=pub_norm,
            volume_name=vol.name,
            start_year=vol.start_year,
            missing_issue_count=1,
            issue_count=int(vol.count_of_issues or 1),
        )
        sample = AcquisitionGapIssueSample(
            publisher=pub_name,
            volume=vol.name,
            issue_number=issue.issue_number,
            issue_name=issue.issue_title,
            release_date=issue.cover_date.isoformat() if issue.cover_date else None,
            shell_created_at=issue.created_at.isoformat() if issue.created_at else None,
            queue_status=_queue_status_label(queue_row),
            acquisition_status=_acquisition_status(issue.status, queue_row),
            gap_reason=reason,
            comicvine_volume_id=cv_id,
            comicvine_issue_id=issue.comicvine_issue_id,
            priority_score=priority,
        )
        if len(issue_samples) < max(0, int(issue_sample_limit)):
            issue_samples.append(sample)

        label = _resolve_publisher_label(pub_name) or (
            major_publisher_for(pub_norm).canonical if major_publisher_for(pub_norm) else None
        )
        if label in HIGH_VALUE_PUBLISHER_LABELS or major_publisher_for(pub_norm) is not None:
            high_value_rows.append(sample)

    high_value_rows.sort(key=lambda r: -r.priority_score)
    high_value_out = [r.as_dict() for r in high_value_rows[: max(1, int(high_value_issue_limit))]]

    gap_by_category: list[dict[str, Any]] = []
    classified_total = sum(category_counts.values())
    for cat in GAP_CATEGORIES:
        count = int(category_counts.get(cat, 0))
        pct = round(count / classified_total * 100.0, 2) if classified_total else 0.0
        gap_by_category.append({"category": cat, "issue_count": count, "percent": pct})

    pub_shells: dict[str, int] = defaultdict(int)
    pub_catalog: dict[str, int] = defaultdict(int)
    pub_gap: dict[str, int] = defaultdict(int)
    vol_gaps_by_pub: dict[str, list[VolumeAcquisitionGap]] = defaultdict(list)

    volumes = list(session.exec(select(UniverseVolume)).all())
    for vol in volumes:
        if (vol.volume_status or "").lower() == VOLUME_STATUS_FOREIGN_SUPERSEDED:
            continue
        uv_id = int(vol.id or 0)
        shells = total_by_vol.get(uv_id, 0)
        if shells <= 0:
            continue
        cataloged = cataloged_by_vol.get(uv_id, 0)
        gap = max(shells - cataloged, 0)
        pub_name = pub_id_to_name.get(int(vol.publisher_id), "Unknown")
        pub_norm = pub_id_to_norm.get(int(vol.publisher_id), "")
        pub_shells[pub_name] += shells
        pub_catalog[pub_name] += cataloged
        pub_gap[pub_name] += gap
        if gap <= 0:
            continue
        cv_id = int(vol.comicvine_volume_id)
        queue_row = queue_by_cv.get(cv_id)
        vol_gaps_by_pub[pub_name].append(
            VolumeAcquisitionGap(
                publisher=pub_name,
                volume=vol.name,
                comicvine_volume_id=cv_id,
                shells=shells,
                catalog_issues=cataloged,
                gap=gap,
                queue_status=_queue_status_label(queue_row),
                collector_priority_score=score_volume(
                    publisher_normalized=pub_norm,
                    volume_name=vol.name,
                    start_year=vol.start_year,
                    missing_issue_count=gap,
                    issue_count=int(vol.count_of_issues or shells),
                ),
            )
        )

    publisher_rows: list[PublisherAcquisitionGap] = []
    for pub_name in sorted(pub_gap.keys(), key=lambda p: -pub_gap[p]):
        shells = pub_shells[pub_name]
        cataloged = pub_catalog[pub_name]
        gap = pub_gap[pub_name]
        vols = vol_gaps_by_pub.get(pub_name, [])
        vols.sort(key=lambda v: -v.gap)
        publisher_rows.append(
            PublisherAcquisitionGap(
                publisher=pub_name,
                shells=shells,
                catalog_issues=cataloged,
                import_gap=gap,
                coverage_percent=_coverage_percent(cataloged, shells),
                top_missing_volumes=[v.as_dict() for v in vols[:5]],
            )
        )

    all_volume_gaps: list[VolumeAcquisitionGap] = []
    for vols in vol_gaps_by_pub.values():
        all_volume_gaps.extend(vols)
    all_volume_gaps.sort(key=lambda v: (-v.gap, -v.collector_priority_score))
    top_vol_rows = all_volume_gaps[: max(1, int(top_volumes))]
    top_pub_rows = publisher_rows[: max(1, int(top_publishers))]

    queued_pending = category_counts.get(CATEGORY_QUEUED_PENDING, 0)
    queued_running = category_counts.get(CATEGORY_QUEUED_RUNNING, 0)
    queued_total = queued_pending + queued_running
    failed = category_counts.get(CATEGORY_IMPORT_FAILED, 0)
    not_queued = category_counts.get(CATEGORY_NOT_QUEUED, 0)
    skipped = category_counts.get(CATEGORY_IMPORT_SKIPPED, 0)
    missing_cv = category_counts.get(CATEGORY_MISSING_COMICVINE_DATA, 0)
    missing_src = category_counts.get(CATEGORY_MISSING_SOURCE_DATA, 0)
    blocked = category_counts.get(CATEGORY_BLOCKED_BY_MATCHING, 0)
    unknown = category_counts.get(CATEGORY_UNKNOWN, 0)
    needs_new_logic = missing_cv + missing_src + blocked + unknown

    final_answers = {
        "why_shells_not_in_catalog": (
            "Issue shells exist in universe_issue with status DISCOVERED (no catalog link). "
            "Most gaps sit on volumes already in p97_volume_issue_import_queue (pending import) "
            "or volumes never queued after shell expansion."
        ),
        "import_gap_issue_count": import_gap_headline,
        "import_gap_universe_discovered_shells": import_gap_universe,
        "catalog_link_backlog": max(import_gap_universe - import_gap_headline, 0),
        "already_queued_pending_or_running": queued_total,
        "waiting_pending": queued_pending,
        "waiting_running": queued_running,
        "failed_import": failed,
        "not_queued": not_queued,
        "import_skipped": skipped,
        "require_new_acquisition_logic": needs_new_logic,
        "blocked_by_matching": blocked,
        "missing_comicvine_issue_id": missing_cv + missing_src,
        "fastest_path_summary": (
            "Drain P97 volume issue import queue (pending → running → complete) on highest-gap "
            "major-publisher volumes first; enqueue NOT_QUEUED volumes with shells; then address "
            "IMPORT_FAILED and matching blocks."
        ),
    }

    global_summary = {
        "publishers": health.publishers,
        "volumes": health.volumes,
        "discoverable_issues_note": "ComicVine universe ceiling (see P98 completeness)",
        "issue_shells": shells_total,
        "catalog_issues_series_linked": catalog_series_total,
        "catalog_issues_universe_linked": catalog_linked_universe,
        "import_gap_p98_headline": import_gap_headline,
        "import_gap_universe_discovered": import_gap_universe,
        "shell_to_catalog_coverage_percent": _coverage_percent(catalog_series_total, shells_total),
        "classified_gap_issues": classified_total,
    }

    return CatalogAcquisitionGapReport(
        generated_at=_utc_now_iso(),
        global_summary=global_summary,
        gap_by_category=gap_by_category,
        publishers=top_pub_rows,
        high_value_gap_issues=high_value_out,
        top_volumes=top_vol_rows,
        issue_samples=issue_samples,
        final_answers=final_answers,
    )


def save_catalog_acquisition_gap_outputs(
    report: CatalogAcquisitionGapReport,
    *,
    report_path: Path | None = None,
    top_publishers_path: Path | None = None,
    top_volumes_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    rp = report_path or default_report_path()
    pp = top_publishers_path or default_top_publishers_path()
    vp = top_volumes_path or default_top_volumes_path()
    for path in (rp, pp, vp):
        path.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    pp.write_text(json.dumps([p.as_dict() for p in report.publishers], indent=2), encoding="utf-8")
    vp.write_text(json.dumps([v.as_dict() for v in report.top_volumes], indent=2), encoding="utf-8")
    return rp, pp, vp
