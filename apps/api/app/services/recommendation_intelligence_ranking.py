"""Apply collector-significance boosts to cross-system ranking priority."""

from __future__ import annotations

from typing import Protocol

from sqlmodel import Session

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.recommendation_intelligence_enrichment import (
    CollectorSignificanceScoreBreakdown,
    build_collector_significance_with_breakdown,
)
from app.services.recommendation_priority_enrichment import (
    build_owned_series_inventory_stats,
    build_recommendation_priority_enrichment,
)
from app.services.recommendation_v2_scoring_context import build_recommendation_v2_scoring_context
from app.services.recommendation_title_index import resolve_release_pair
from app.services.recommendation_title_normalize import normalize_recommendation_title_key


class _RankingCandidate(Protocol):
    title: str
    rationale: str
    recommendation_type: str
    raw_priority_score: float
    priority_score: float
    collector_score_breakdown: CollectorSignificanceScoreBreakdown | None

    @property
    def title_key(self) -> str: ...


def _resolve_title_key(title: str) -> str:
    return normalize_recommendation_title_key(title)


def apply_collector_significance_priority_boost(
    session: Session,
    *,
    owner_user_id: int,
    candidates: list[_RankingCandidate],
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
    signals_by_issue: dict[int, list[str]],
    variants_by_issue: dict[int, list[ReleaseVariant]] | None = None,
) -> None:
    if not candidates:
        return
    owned_stats = build_owned_series_inventory_stats(session, owner_user_id=owner_user_id)
    variants_by_issue = variants_by_issue or {}
    boost_issue_ids: list[int] = []
    for cand in candidates:
        pair = resolve_release_pair(cand.title, release_index)
        if pair is None or pair[0].id is None:
            continue
        boost_issue_ids.append(int(pair[0].id))
    scoring_ctx = build_recommendation_v2_scoring_context(
        session,
        owner_user_id=owner_user_id,
        issue_ids=list(dict.fromkeys(boost_issue_ids)),
    )

    for cand in candidates:
        pair = resolve_release_pair(cand.title, release_index)
        if pair is None:
            continue
        issue, series = pair
        issue_id = int(issue.id) if issue.id is not None else 0
        if issue_id <= 0:
            continue
        signals = signals_by_issue.get(issue_id, [])
        variants = variants_by_issue.get(issue_id, [])
        base = float(cand.raw_priority_score or cand.priority_score)
        priority_enrichment = build_recommendation_priority_enrichment(
            session,
            owner_user_id=owner_user_id,
            series_name=series.series_name,
            issue_title=issue.title,
            publisher=series.publisher,
            key_signals=signals,
            v2_confidence=float(getattr(cand, "confidence_score", 0.58) or 0.58),
            spec_type=None,
            owns_series_run=False,
            owned_stats=owned_stats,
            scoring_ctx=scoring_ctx,
            issue_id=issue_id,
            issue=issue,
            series=series,
        )
        _enrichment, breakdown = build_collector_significance_with_breakdown(
            session,
            series=series,
            issue=issue,
            variants=variants,
            rationale=cand.rationale,
            key_signals=signals,
            priority_enrichment=priority_enrichment,
            owned_stats=owned_stats,
            base_score=base,
        )
        boost = breakdown.ranking_boost
        if boost <= 0:
            cand.collector_score_breakdown = breakdown
            continue
        new_raw = round(base + boost, 2)
        cand.raw_priority_score = new_raw
        cand.priority_score = new_raw
        cand.collector_score_breakdown = breakdown


def raw_priority_without_collector_boost(cand: _RankingCandidate) -> float:
    breakdown = getattr(cand, "collector_score_breakdown", None)
    raw = float(cand.raw_priority_score or cand.priority_score)
    if breakdown is None:
        return raw
    return round(max(0.0, raw - breakdown.ranking_boost), 2)


def rank_order_changed_by_collector_boost(candidates: list[_RankingCandidate]) -> bool:
    if len(candidates) < 2:
        return False

    def _key_with(c: _RankingCandidate) -> tuple[float, str]:
        return (float(c.raw_priority_score or c.priority_score), c.title_key)

    def _key_without(c: _RankingCandidate) -> tuple[float, str]:
        return (raw_priority_without_collector_boost(c), c.title_key)

    ordered_with = [c.title for c in sorted(candidates, key=_key_with, reverse=True)]
    ordered_without = [c.title for c in sorted(candidates, key=_key_without, reverse=True)]
    return ordered_with != ordered_without
