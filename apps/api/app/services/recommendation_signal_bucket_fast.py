"""Fast-path helpers for signal-bucket diagnostics (no ranking/rebuild/decision recompute)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.creator_intelligence import CreatorProfile
from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.services.cross_system_recommendation_engine import _latest_snapshot_rows

STORED_RECOMMENDATION_CANDIDATE_LIMIT = 25
TOP_STORED_SNAPSHOT_SCAN_LIMIT = 200


@dataclass
class SignalBucketDiagnosticCaches:
    """Per-run caches and performance counters for diagnostic scripts."""

    title_index_build_count: int = 0
    creator_profile_load_count: int = 0
    market_demand_load_count: int = 0
    recommendation_rows_scanned: int = 0
    catalog_rows_scanned: int = 0
    _active_creators: list[CreatorProfile] | None = field(default=None, repr=False)
    _market_profiles: list[MarketDemandProfile] | None = field(default=None, repr=False)
    _started: float = field(default_factory=time.monotonic)

    def elapsed_ms(self) -> float:
        return round((time.monotonic() - self._started) * 1000.0, 2)

    def performance_payload(self) -> dict[str, Any]:
        return {
            "total_runtime_ms": self.elapsed_ms(),
            "title_index_build_count": self.title_index_build_count,
            "recommendation_rows_scanned": self.recommendation_rows_scanned,
            "catalog_rows_scanned": self.catalog_rows_scanned,
            "creator_profile_load_count": self.creator_profile_load_count,
            "market_demand_load_count": self.market_demand_load_count,
        }

    def get_active_creators(self, session: Session) -> list[CreatorProfile]:
        if self._active_creators is None:
            self._active_creators = list(
                session.exec(
                    select(CreatorProfile).where(CreatorProfile.status == "ACTIVE").limit(400)
                ).all()
            )
            self.creator_profile_load_count += 1
        return self._active_creators

    def get_market_profiles(self, session: Session, *, search_blob: str) -> list[MarketDemandProfile]:
        if self._market_profiles is not None:
            return self._market_profiles
        tokens = _entity_tokens_from_blob(search_blob)
        if tokens:
            clauses = []
            for tok in tokens[:8]:
                clauses.append(func.lower(MarketDemandProfile.entity_name).contains(tok))
            if clauses:
                from sqlalchemy import or_

                stmt = select(MarketDemandProfile).where(or_(*clauses)).limit(200)
                rows = list(session.exec(stmt).all())
                self.market_demand_load_count += 1
                self._market_profiles = rows
                return rows
        rows = list(session.exec(select(MarketDemandProfile).limit(500)).all())
        self.market_demand_load_count += 1
        self._market_profiles = rows
        return rows


def _entity_tokens_from_blob(blob: str) -> list[str]:
    import re

    lower = blob.lower()
    tokens: list[str] = []
    for part in re.split(r"[^a-z0-9]+", lower):
        if len(part) >= 4:
            tokens.append(part)
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:12]


def _row_to_recommendation_dict(row: CrossSystemRecommendation) -> dict[str, Any]:
    return {
        "found": True,
        "title": row.title,
        "recommendation_type": row.recommendation_type,
        "priority_score": float(row.priority_score),
        "confidence_score": float(row.confidence_score),
        "recommendation_rank": int(row.recommendation_rank),
        "source_systems": list(row.source_systems or []),
        "rationale": row.rationale or "",
    }


def fetch_stored_recommendation_by_title(
    session: Session,
    *,
    owner_user_id: int,
    title_query: str,
    caches: SignalBucketDiagnosticCaches,
    candidate_limit: int = STORED_RECOMMENDATION_CANDIDATE_LIMIT,
) -> tuple[dict[str, Any] | None, int]:
    """Match title against latest stored cross-system snapshot rows only (no decision pipeline)."""
    needle = title_query.strip().lower()
    if not needle:
        caches.recommendation_rows_scanned = 0
        return None, 0

    snapshot = _latest_snapshot_rows(
        session,
        owner_user_id=owner_user_id,
        scan_limit=TOP_STORED_SNAPSHOT_SCAN_LIMIT,
    )
    rows = list(snapshot.values())
    caches.recommendation_rows_scanned = len(rows)

    matches = [r for r in rows if needle in (r.title or "").lower()]
    if not matches:
        stmt = (
            select(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
            .where(func.lower(CrossSystemRecommendation.title).contains(needle))
            .order_by(
                CrossSystemRecommendation.created_at.desc(),
                CrossSystemRecommendation.priority_score.desc(),
            )
            .limit(candidate_limit)
        )
        db_rows = list(session.exec(stmt).all())
        caches.recommendation_rows_scanned += len(db_rows)
        matches = db_rows

    matches.sort(
        key=lambda r: (
            -float(r.priority_score),
            int(r.recommendation_rank),
        )
    )
    candidates = matches[:candidate_limit]
    caches.recommendation_rows_scanned = max(caches.recommendation_rows_scanned, len(candidates))
    if not candidates:
        return None, 0
    return _row_to_recommendation_dict(candidates[0]), len(candidates)


def fetch_top_stored_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    caches: SignalBucketDiagnosticCaches,
) -> list[dict[str, Any]]:
    """Top N by stored recommendation_rank from latest snapshot (no decision recompute)."""
    snapshot = _latest_snapshot_rows(
        session,
        owner_user_id=owner_user_id,
        scan_limit=TOP_STORED_SNAPSHOT_SCAN_LIMIT,
    )
    rows = sorted(snapshot.values(), key=lambda r: int(r.recommendation_rank))
    caches.recommendation_rows_scanned = len(rows)
    picked = rows[: min(max(limit, 1), 50)]
    return [_row_to_recommendation_dict(r) for r in picked]
