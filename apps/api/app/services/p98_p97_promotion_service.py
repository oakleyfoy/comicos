"""P98 -> P97 promotion (planning -> import queue).

Promotes ONLY action-queue rows whose recommended_action is
IMPORT_CATALOG_METADATA into ``p97_volume_issue_import_queue``. It never calls
ComicVine, never imports, never deletes. It only inserts/updates queue rows, and
only when ``apply=True``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.catalog_p97 import P97VolumeIssueImportQueue

PROMOTABLE_ACTION = "IMPORT_CATALOG_METADATA"


@dataclass
class PromotionResult:
    considered: int = 0
    promotable: int = 0
    created: int = 0
    updated: int = 0
    skipped_non_pending: int = 0
    applied: bool = False
    created_volume_ids: list[int] = field(default_factory=list)
    updated_volume_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "considered": self.considered,
            "promotable": self.promotable,
            "created": self.created,
            "updated": self.updated,
            "skipped_non_pending": self.skipped_non_pending,
            "applied": self.applied,
            "created_volume_ids": list(self.created_volume_ids),
            "updated_volume_ids": list(self.updated_volume_ids),
        }


def _coverage_percent(catalog: int, universe: int) -> float:
    if universe <= 0:
        return 0.0
    return round(100.0 * catalog / universe, 2)


def promote_import_rows(
    session: Session,
    rows: list[dict],
    *,
    apply: bool = False,
) -> PromotionResult:
    result = PromotionResult(applied=apply)
    result.considered = len(rows)
    now = datetime.now(timezone.utc)

    for row in rows:
        if row.get("recommended_action") != PROMOTABLE_ACTION:
            continue
        result.promotable += 1
        cv_id = int(row.get("comicvine_volume_id") or 0)
        if cv_id <= 0:
            continue
        universe = int(row.get("universe_issue_count") or 0)
        catalog = int(row.get("catalog_issue_count") or 0)
        missing = int(row.get("missing_issue_count") or 0)
        priority = float(row.get("priority_score") or 0)

        existing = session.exec(
            select(P97VolumeIssueImportQueue).where(
                P97VolumeIssueImportQueue.comicvine_volume_id == cv_id
            )
        ).first()

        if existing is None:
            result.created += 1
            result.created_volume_ids.append(cv_id)
            if apply:
                session.add(
                    P97VolumeIssueImportQueue(
                        comicvine_volume_id=cv_id,
                        name=str(row.get("volume") or ""),
                        publisher=row.get("publisher"),
                        count_of_issues=universe,
                        existing_issue_count=catalog,
                        missing_issue_count=missing,
                        coverage_percent=_coverage_percent(catalog, universe),
                        priority_score=priority,
                        request_notes="p98_major_publisher_gap_promotion",
                        status="pending",
                    )
                )
            continue

        # Only refresh rows still pending; never disturb in-progress/completed work.
        if existing.status != "pending":
            result.skipped_non_pending += 1
            continue
        result.updated += 1
        result.updated_volume_ids.append(cv_id)
        if apply:
            existing.name = str(row.get("volume") or existing.name)
            existing.publisher = row.get("publisher") or existing.publisher
            existing.count_of_issues = universe
            existing.existing_issue_count = catalog
            existing.missing_issue_count = missing
            existing.coverage_percent = _coverage_percent(catalog, universe)
            existing.priority_score = priority
            existing.updated_at = now
            session.add(existing)

    if apply:
        session.commit()
    else:
        session.rollback()
    return result
