"""P98 skeleton health metrics (read-only)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.universe import (
    UNIVERSE_ISSUE_STATUS_CATALOGED,
    UNIVERSE_ISSUE_STATUS_DISCOVERED,
    UniverseIssue,
    UniversePublisher,
    UniverseVariant,
    UniverseVolume,
)
from app.services.universe.universe_issue_service import VOLUME_STATUS_VOLUME_ONLY


@dataclass
class SkeletonHealth:
    publishers: int
    volumes: int
    issues: int
    variants: int
    issues_without_variants: int
    catalog_linked_issues: int
    discovered_only_issues: int
    volume_only_volumes: int

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def compute_skeleton_health(session: Session) -> SkeletonHealth:
    publishers = int(session.exec(select(func.count()).select_from(UniversePublisher)).one())
    volumes = int(session.exec(select(func.count()).select_from(UniverseVolume)).one())
    issues = int(session.exec(select(func.count()).select_from(UniverseIssue)).one())
    variants = int(session.exec(select(func.count()).select_from(UniverseVariant)).one())

    issue_ids_with_variants = select(UniverseVariant.issue_id).distinct().subquery()
    issues_without_variants = int(
        session.exec(
            select(func.count())
            .select_from(UniverseIssue)
            .where(UniverseIssue.id.not_in(select(issue_ids_with_variants.c.issue_id)))
        ).one()
    )

    catalog_linked = int(
        session.exec(
            select(func.count())
            .select_from(UniverseIssue)
            .where(UniverseIssue.status == UNIVERSE_ISSUE_STATUS_CATALOGED)
        ).one()
    )
    discovered_only = int(
        session.exec(
            select(func.count())
            .select_from(UniverseIssue)
            .where(UniverseIssue.status == UNIVERSE_ISSUE_STATUS_DISCOVERED)
        ).one()
    )
    volume_only = int(
        session.exec(
            select(func.count())
            .select_from(UniverseVolume)
            .where(UniverseVolume.volume_status == VOLUME_STATUS_VOLUME_ONLY)
        ).one()
    )

    return SkeletonHealth(
        publishers=publishers,
        volumes=volumes,
        issues=issues,
        variants=variants,
        issues_without_variants=issues_without_variants,
        catalog_linked_issues=catalog_linked,
        discovered_only_issues=discovered_only,
        volume_only_volumes=volume_only,
    )
