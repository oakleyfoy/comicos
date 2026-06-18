"""P98 — Major publisher universe completeness (read-only reporting)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.models.universe import UniverseIssue, UniverseVolume
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p98_major_publisher_registry import (
    config_for_comicvine_publisher_name,
)
from app.services.p98_publisher_match_repair_service import VOLUME_STATUS_FOREIGN_SUPERSEDED
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)
from app.services.universe.universe_health_service import compute_skeleton_health

DEFAULT_REPORT_REL = Path("data/p98/major_publisher_completeness_report.json")

REQUIRED_PUBLISHERS: tuple[str, ...] = (
    "Marvel",
    "DC Comics",
    "IDW Publishing",
    "Image",
    "Dark Horse Comics",
    "Boom! Studios",
)

OPTIONAL_PUBLISHERS: tuple[str, ...] = (
    "Dynamite",
    "Valiant",
    "Titan Comics",
)

ACTIVE_QUEUE_STATUSES: frozenset[str] = frozenset({"pending", "running", "failed"})


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_report_path() -> Path:
    return _api_root() / DEFAULT_REPORT_REL


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coverage_percent(built: int, discoverable: int) -> float:
    if discoverable <= 0:
        return 100.0 if built <= 0 else 0.0
    return round(min(100.0, built / discoverable * 100.0), 2)


def _resolve_publisher_label(publisher: str | None) -> str | None:
    if not publisher:
        return None
    cfg = config_for_comicvine_publisher_name(publisher)
    if cfg is not None:
        return cfg.canonical
    norm = normalize_series_name(publisher)
    if norm == normalize_series_name("Titan Comics") or norm.startswith("titan "):
        return "Titan Comics"
    return None


@dataclass
class VolumeMissingRow:
    comicvine_volume_id: int
    volume_name: str
    publisher: str
    discoverable_issues: int
    issue_shells: int
    missing_count: int
    has_canonical_p98_volume: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "volume": self.volume_name,
            "publisher": self.publisher,
            "discoverable_issues": self.discoverable_issues,
            "issue_shells": self.issue_shells,
            "missing_count": self.missing_count,
            "has_canonical_p98_volume": self.has_canonical_p98_volume,
        }


@dataclass
class PublisherCompletenessMetrics:
    publisher: str
    comicvine_universe_volumes: int = 0
    canonical_p98_volumes: int = 0
    superseded_foreign_volumes: int = 0
    cv_volumes_without_canonical_p98: int = 0
    discoverable_issues: int = 0
    issue_shells_built: int = 0
    missing_issue_shells: int = 0
    queued_missing_issues: int = 0
    catalog_issue_count: int = 0
    import_gap_issues: int = 0
    coverage_percent: float = 0.0
    top_missing_volumes: list[VolumeMissingRow] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "comicvine_universe_volumes": self.comicvine_universe_volumes,
            "canonical_p98_volumes": self.canonical_p98_volumes,
            "superseded_foreign_volumes": self.superseded_foreign_volumes,
            "cv_volumes_without_canonical_p98": self.cv_volumes_without_canonical_p98,
            "discoverable_issues": self.discoverable_issues,
            "issue_shells_built": self.issue_shells_built,
            "missing_issue_shells": self.missing_issue_shells,
            "queued_missing_issues": self.queued_missing_issues,
            "catalog_issue_count": self.catalog_issue_count,
            "import_gap_issues": self.import_gap_issues,
            "coverage_percent": self.coverage_percent,
            "top_missing_volumes": [r.as_dict() for r in self.top_missing_volumes],
        }


@dataclass
class GlobalCompletenessSummary:
    publishers: int
    volumes: int
    discoverable_issues: int
    issue_shells: int
    missing_issue_shells: int
    coverage_percent: float
    catalog_issue_count: int
    import_gap_issues: int
    major_cv_volumes_without_p98: int
    gap_interpretation: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "publishers": self.publishers,
            "volumes": self.volumes,
            "discoverable_issues": self.discoverable_issues,
            "issue_shells": self.issue_shells,
            "missing_issue_shells": self.missing_issue_shells,
            "coverage_percent": self.coverage_percent,
            "catalog_issue_count": self.catalog_issue_count,
            "import_gap_issues": self.import_gap_issues,
            "major_cv_volumes_without_p98": self.major_cv_volumes_without_p98,
            "gap_interpretation": self.gap_interpretation,
        }


@dataclass
class MajorPublisherCompletenessReport:
    generated_at: str
    publishers: list[PublisherCompletenessMetrics]
    global_summary: GlobalCompletenessSummary

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "publishers": [p.as_dict() for p in self.publishers],
            "global_summary": self.global_summary.as_dict(),
        }


def _issue_shell_counts(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(UniverseVolume.comicvine_volume_id, func.count(UniverseIssue.id))
        .join(UniverseIssue, UniverseIssue.volume_id == UniverseVolume.id)
        .where(UniverseVolume.volume_status != VOLUME_STATUS_FOREIGN_SUPERSEDED)
        .group_by(UniverseVolume.comicvine_volume_id)
    ).all()
    return {int(cv_id): int(cnt) for cv_id, cnt in rows}


def _p98_volume_by_cv_id(session: Session) -> dict[int, UniverseVolume]:
    return {
        int(v.comicvine_volume_id): v
        for v in session.exec(select(UniverseVolume)).all()
    }


def _queued_missing_by_cv(session: Session) -> dict[int, int]:
    out: dict[int, int] = {}
    for row in session.exec(select(P97VolumeIssueImportQueue)).all():
        status = (row.status or "").lower()
        if status not in ACTIVE_QUEUE_STATUSES:
            continue
        missing = int(row.missing_issue_count or 0)
        if missing <= 0:
            continue
        out[int(row.comicvine_volume_id)] = missing
    return out


def build_major_publisher_completeness_report(
    session: Session,
    *,
    include_optional: bool = True,
    top_missing_per_publisher: int = 25,
) -> MajorPublisherCompletenessReport:
    targets = set(REQUIRED_PUBLISHERS)
    if include_optional:
        targets.update(OPTIONAL_PUBLISHERS)

    cv_rows = list(session.exec(select(ComicVineVolumeUniverse)).all())
    p98_by_cv = _p98_volume_by_cv_id(session)
    shell_by_cv = _issue_shell_counts(session)
    queued_by_cv = _queued_missing_by_cv(session)
    catalog_indexes = build_catalog_coverage_indexes(session)
    health = compute_skeleton_health(session)

    global_discoverable = sum(int(r.count_of_issues or 0) for r in cv_rows)
    global_shells = health.issues
    global_catalog = 0

    per_pub: dict[str, PublisherCompletenessMetrics] = {
        name: PublisherCompletenessMetrics(publisher=name) for name in sorted(targets)
    }
    volume_gaps: dict[str, list[VolumeMissingRow]] = {name: [] for name in targets}

    for cv in cv_rows:
        label = _resolve_publisher_label(cv.publisher)
        if label is None or label not in targets:
            continue
        metrics = per_pub[label]
        vid = int(cv.volume_id)
        discoverable = max(int(cv.count_of_issues or 0), 0)
        metrics.comicvine_universe_volumes += 1
        metrics.discoverable_issues += discoverable

        p98 = p98_by_cv.get(vid)
        is_superseded = (
            p98 is not None
            and (p98.volume_status or "").lower() == VOLUME_STATUS_FOREIGN_SUPERSEDED
        )
        if is_superseded:
            metrics.superseded_foreign_volumes += 1

        has_canonical = p98 is not None and not is_superseded
        if has_canonical:
            metrics.canonical_p98_volumes += 1
        else:
            metrics.cv_volumes_without_canonical_p98 += 1

        shells = shell_by_cv.get(vid, 0) if has_canonical else 0
        if has_canonical:
            metrics.issue_shells_built += shells

        missing = max(discoverable - shells, 0) if has_canonical else discoverable
        if has_canonical:
            metrics.missing_issue_shells += missing
        else:
            metrics.missing_issue_shells += discoverable

        catalog = existing_issue_count_for_volume(
            volume_id=vid,
            name=cv.name,
            publisher=cv.publisher,
            indexes=catalog_indexes,
        )
        metrics.catalog_issue_count += catalog
        if has_canonical:
            metrics.import_gap_issues += max(shells - catalog, 0)

        q_missing = queued_by_cv.get(vid, 0)
        metrics.queued_missing_issues += q_missing

        if missing > 0:
            volume_gaps[label].append(
                VolumeMissingRow(
                    comicvine_volume_id=vid,
                    volume_name=cv.name,
                    publisher=cv.publisher or label,
                    discoverable_issues=discoverable,
                    issue_shells=shells,
                    missing_count=missing if has_canonical else discoverable,
                    has_canonical_p98_volume=has_canonical,
                )
            )

    for label, metrics in per_pub.items():
        metrics.coverage_percent = _coverage_percent(
            metrics.issue_shells_built,
            metrics.discoverable_issues,
        )
        gaps = volume_gaps[label]
        gaps.sort(key=lambda r: r.missing_count, reverse=True)
        metrics.top_missing_volumes = gaps[: max(1, int(top_missing_per_publisher))]

    for cv in cv_rows:
        global_catalog += existing_issue_count_for_volume(
            volume_id=int(cv.volume_id),
            name=cv.name,
            publisher=cv.publisher,
            indexes=catalog_indexes,
        )

    major_missing_volumes = sum(m.cv_volumes_without_canonical_p98 for m in per_pub.values())
    major_missing_shells = sum(m.missing_issue_shells for m in per_pub.values())
    major_import_gap = sum(m.import_gap_issues for m in per_pub.values())

    global_summary = GlobalCompletenessSummary(
        publishers=health.publishers,
        volumes=health.volumes,
        discoverable_issues=global_discoverable,
        issue_shells=global_shells,
        missing_issue_shells=max(global_discoverable - global_shells, 0),
        coverage_percent=_coverage_percent(global_shells, global_discoverable),
        catalog_issue_count=global_catalog,
        import_gap_issues=max(global_shells - global_catalog, 0),
        major_cv_volumes_without_p98=major_missing_volumes,
        gap_interpretation={
            "missing_volume_rows_major_publishers": major_missing_volumes,
            "missing_issue_shells_major_publishers": major_missing_shells,
            "import_gap_from_shells_major_publishers": major_import_gap,
            "missing_issue_shells_all_publishers": max(global_discoverable - global_shells, 0),
        },
    )

    publisher_rows = [per_pub[name] for name in sorted(per_pub.keys()) if name in targets]
    return MajorPublisherCompletenessReport(
        generated_at=_utc_now_iso(),
        publishers=publisher_rows,
        global_summary=global_summary,
    )


def save_major_publisher_completeness_report(
    report: MajorPublisherCompletenessReport,
    path: Path | None = None,
) -> Path:
    out = path or default_report_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    return out
