from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from sqlmodel import Session, select

from app.models.cross_system_recommendation import CrossSystemRecommendation, utc_now
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows
from app.services.grade_before_sell import _latest_rows as _latest_grade_rows
from app.services.hold_sell_intelligence import _latest_hold_sell_rows
from app.services.purchase_budgets import get_purchase_budget_row
from app.services.cross_system_build_timing import CrossSystemBuildTiming
from app.services.unified_collector_intelligence import (
    _latest_recommendation_rows as _latest_unified_rows,
)
from app.services.recommendation_latest_rows import latest_by_key_bounded_scan
from app.services.recommendation_priority_spread import (
    apply_confidence_spread_inplace,
    apply_priority_spread_inplace,
)
from app.services.recommendation_catalog_quality import (
    build_forward_release_title_index,
    quality_for_recommendation_title,
    should_include_in_top_recommendations,
    title_passes_top_recommendation_quality,
)
from app.services.recommendation_intelligence_enrichment import CollectorSignificanceScoreBreakdown
from app.services.recommendation_intelligence_ranking import (
    apply_collector_significance_priority_boost,
)

SRC_UNIFIED = "P57_UNIFIED"
SRC_DAILY = "P57_DAILY"
SRC_PULL = "P52_PULL_LIST"
SRC_PURCHASE = "P53_PURCHASE"
SRC_PORTFOLIO = "P54_PORTFOLIO"
SRC_ACQUISITION = "P55_ACQUISITION"
SRC_EXIT = "P56_EXIT"

TYPE_PREORDER = "PREORDER"
TYPE_ACQUIRE = "ACQUIRE"
TYPE_GRADE = "GRADE"
TYPE_SELL = "SELL"
TYPE_REBALANCE = "REBALANCE"
TYPE_WATCH = "WATCH"

_TYPE_RANK = {
    TYPE_ACQUIRE: 6,
    TYPE_PREORDER: 5,
    TYPE_GRADE: 4,
    TYPE_SELL: 3,
    TYPE_REBALANCE: 2,
    "REVIEW": 2,
    TYPE_WATCH: 1,
}


@dataclass
class _Candidate:
    recommendation_type: str
    title: str
    priority_score: float
    confidence_score: float
    estimated_value: float | None
    source_systems: set[str] = field(default_factory=set)
    rationale: str = ""
    raw_priority_score: float = 0.0
    normalized_priority_score: float = 0.0
    raw_confidence_score: float = 0.0
    normalized_confidence_score: float = 0.0
    budget_priority_adjusted: bool = False
    collector_score_breakdown: CollectorSignificanceScoreBreakdown | None = None

    @property
    def title_key(self) -> str:
        from app.services.recommendation_title_normalize import normalize_recommendation_title_key

        return normalize_recommendation_title_key(self.title)


def _clamp_priority(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


def _clamp_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _confidence_boost(base: float, source_count: int, *, consistent: bool) -> float:
    boost = min(0.08, 0.022 * max(0, source_count - 1))
    if consistent:
        boost += 0.012
    return _clamp_confidence(min(0.96, base + boost))


def _list_daily_collector_actions(
    session: Session,
    *,
    owner_user_id: int,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]] | None = None,
) -> list[_Candidate]:
    from app.models.daily_action_engine import DailyCollectorAction

    index = release_index or build_forward_release_title_index(session, owner_user_id=owner_user_id)
    latest = latest_by_key_bounded_scan(
        session,
        model=DailyCollectorAction,
        owner_user_id=owner_user_id,
        owner_field="owner_user_id",
        key_fn=lambda row: (row.action_type, row.title.strip().lower()),
    )
    out: list[_Candidate] = []
    for row in latest.values():
        if not title_passes_top_recommendation_quality(
            row.title,
            session=session,
            owner_user_id=owner_user_id,
            release_index=index,
        ):
            continue
        action_type = row.action_type.strip().upper()
        rec_type = action_type if action_type in _TYPE_RANK else TYPE_WATCH
        systems = {str(s) for s in (row.source_systems or [])}
        systems.add(SRC_DAILY)
        out.append(
            _Candidate(
                recommendation_type=rec_type,
                title=row.title,
                priority_score=_clamp_priority(float(row.priority_score)),
                confidence_score=_clamp_confidence(float(row.confidence_score)),
                estimated_value=None,
                source_systems=systems,
                rationale=row.rationale or "Daily action priority item.",
                raw_priority_score=float(row.priority_score),
                raw_confidence_score=float(row.confidence_score),
            )
        )
    return out


def _unified_candidates(
    session: Session,
    *,
    owner_user_id: int,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]] | None = None,
) -> list[_Candidate]:
    index = release_index or build_forward_release_title_index(session, owner_user_id=owner_user_id)
    out: list[_Candidate] = []
    for row in _latest_unified_rows(session, owner_user_id=owner_user_id).values():
        if not title_passes_top_recommendation_quality(
            row.title,
            session=session,
            owner_user_id=owner_user_id,
            release_index=index,
        ):
            continue
        systems = {str(s) for s in (row.source_systems or [])}
        systems.add(SRC_UNIFIED)
        out.append(
            _Candidate(
                recommendation_type=row.recommendation_type,
                title=row.title,
                priority_score=float(row.priority_score),
                confidence_score=float(row.confidence_score),
                estimated_value=None,
                source_systems=systems,
                rationale=row.rationale,
                raw_priority_score=float(row.priority_score),
                raw_confidence_score=float(row.confidence_score),
            )
        )
    return out


def _enrich_estimated_values(session: Session, *, owner_user_id: int, candidates: list[_Candidate]) -> None:
    opps = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    opp_by_title: dict[tuple[str, str], object] = {}
    for row in opps.values():
        key = (row.series_name.strip().lower(), row.issue_number.strip())
        opp_by_title[key] = row
    grade_rows = _latest_grade_rows(session, owner_user_id=owner_user_id)
    hold_rows = _latest_hold_sell_rows(session, owner_user_id=owner_user_id)

    for cand in candidates:
        if cand.estimated_value is not None:
            continue
        parts = cand.title.split("#", 1)
        series = parts[0].strip().lower()
        issue = parts[1].strip() if len(parts) > 1 else ""
        row = opp_by_title.get((series, issue))
        if row is not None:
            if row.value_gap is not None:
                cand.estimated_value = round(float(row.value_gap), 2)
            elif row.target_price is not None:
                cand.estimated_value = round(float(row.target_price), 2)
        if cand.recommendation_type == TYPE_GRADE:
            for grow in grade_rows.values():
                if grow.recommendation == "GRADE_BEFORE_SELL" and grow.expected_value_gain > 0:
                    cand.estimated_value = round(float(grow.expected_value_gain), 2)
                    break
        if cand.recommendation_type == TYPE_SELL:
            for hrow in hold_rows.values():
                if hrow.recommendation == "SELL" and hrow.unrealized_gain > 0:
                    cand.estimated_value = round(float(hrow.unrealized_gain), 2)
                    break


def _resolve_conflicts(group: list[_Candidate]) -> _Candidate:
    types = {c.recommendation_type for c in group}
    merged_sources: set[str] = set()
    for c in group:
        merged_sources.update(c.source_systems)
    best_priority = max(c.priority_score for c in group)
    best_raw = max(c.raw_priority_score or c.priority_score for c in group)
    best_raw_conf = max(c.raw_confidence_score or c.confidence_score for c in group)
    best_confidence = max(c.confidence_score for c in group)
    est = next((c.estimated_value for c in group if c.estimated_value is not None), None)
    rationales = [c.rationale for c in group if c.rationale]

    winner_type = max(group, key=lambda c: (c.priority_score, _TYPE_RANK.get(c.recommendation_type, 0))).recommendation_type
    conflict_note = ""

    if TYPE_GRADE in types and TYPE_SELL in types:
        winner_type = TYPE_GRADE
        conflict_note = "Resolved GRADE vs SELL conflict; grading upside evaluated before exit."
    elif TYPE_ACQUIRE in types and TYPE_PREORDER in types:
        acquire = next(c for c in group if c.recommendation_type == TYPE_ACQUIRE)
        preorder = next(c for c in group if c.recommendation_type == TYPE_PREORDER)
        if acquire.priority_score >= preorder.priority_score:
            winner_type = TYPE_ACQUIRE
            conflict_note = "Merged acquisition and preorder signals; acquisition prioritized."
        else:
            winner_type = TYPE_PREORDER
            conflict_note = "Merged acquisition and preorder signals; preorder timing prioritized."
    elif len(types) > 1:
        winner_type = max(group, key=lambda c: (c.priority_score, _TYPE_RANK.get(c.recommendation_type, 0))).recommendation_type
        conflict_note = f"Resolved conflicting signals; retained {winner_type}."

    winner = next(c for c in group if c.recommendation_type == winner_type)
    rationale_parts = [r for r in rationales if r]
    if conflict_note:
        rationale_parts.append(conflict_note)
    elif len(merged_sources) > 1:
        labels = ", ".join(sorted(merged_sources))
        rationale_parts.append(f"Supported by {labels} systems.")
    rationale = " ".join(dict.fromkeys(rationale_parts)) or winner.rationale or "Cross-system recommendation."

    consistent = len(types) == 1
    confidence = _confidence_boost(best_confidence, len(merged_sources), consistent=consistent)
    merge_boost = min(3.0, max(0, len(merged_sources) - 1) * 1.0)
    priority = best_priority + merge_boost
    raw_priority = best_raw + merge_boost

    return _Candidate(
        recommendation_type=winner_type,
        title=group[0].title,
        priority_score=priority,
        confidence_score=confidence,
        estimated_value=est,
        source_systems=merged_sources,
        rationale=rationale,
        raw_priority_score=raw_priority,
        raw_confidence_score=best_raw_conf,
    )


def _apply_budget_awareness(session: Session, *, owner_user_id: int, candidates: list[_Candidate]) -> None:
    budget = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    constrained = budget.is_active and budget.monthly_budget > 0 and budget.monthly_budget < 150.0
    if not constrained:
        return
    critical_acquire = any(c.recommendation_type == TYPE_ACQUIRE for c in candidates)
    if not critical_acquire:
        return
    top_preorder = max(
        (c.priority_score for c in candidates if c.recommendation_type == TYPE_PREORDER),
        default=0.0,
    )
    for cand in candidates:
        if cand.recommendation_type == TYPE_PREORDER and top_preorder > 0 and cand.priority_score < top_preorder + 1:
            cand.priority_score = _clamp_priority(cand.priority_score - 14.0)
            cand.budget_priority_adjusted = True
            cand.rationale = f"{cand.rationale} Budget constrained; critical acquisition preferred over low-priority preorder.".strip()
        if cand.recommendation_type == TYPE_ACQUIRE:
            floor = top_preorder + 2.0 if top_preorder > 0 else cand.priority_score + 6.0
            cand.priority_score = _clamp_priority(max(cand.priority_score + 6.0, floor))
            cand.budget_priority_adjusted = True
            cand.rationale = f"{cand.rationale} Budget constrained; critical acquisition prioritized.".strip()


def _candidate_passes_quality_filter(
    cand: _Candidate,
    *,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
    signals_by_issue: dict[int, list[str]],
) -> bool:
    from app.services.recommendation_title_index import resolve_release_pair

    issue_id = None
    pair = resolve_release_pair(cand.title, release_index)
    if pair is not None:
        issue_id = int(pair[0].id or 0)
    signals = signals_by_issue.get(issue_id, []) if issue_id else None
    quality = quality_for_recommendation_title(
        cand.title,
        release_index=release_index,
        key_signals=signals,
        confidence_score=cand.confidence_score,
    )
    return should_include_in_top_recommendations(quality)


def _sort_key(c: _Candidate, *, created_ord: int, row_id: int) -> tuple:
    est = c.estimated_value if c.estimated_value is not None else 0.0
    return (-c.priority_score, -c.confidence_score, -est, created_ord, row_id)


def _stable_tiebreak_token(title_key: str) -> int:
    """Deterministic tie-breaker that does not sort alphabetically by title."""
    acc = 0
    for idx, ch in enumerate(title_key):
        acc = (acc + (ord(ch) * (idx + 17))) % 10007
    return acc


def _candidate_sort_key(c: _Candidate) -> tuple:
    return (
        -c.priority_score,
        -c.confidence_score,
        -(c.estimated_value or 0.0),
        -len(c.source_systems),
        _stable_tiebreak_token(c.title_key),
    )


def build_cross_system_candidates(
    session: Session,
    *,
    owner_user_id: int,
    refresh_upstream: bool = False,
    build_timings: CrossSystemBuildTiming | None = None,
    index_cache: "RecommendationPipelineIndexCache | None" = None,
) -> list[_Candidate]:
    """Merge latest Unified + Daily rows into ranked cross-system candidates.

    When ``refresh_upstream`` is False (default), reads existing Unified/Daily output only —
    use after explicit unified/daily generation in rebuild pipelines.
    """
    from app.services.daily_action_engine import generate_daily_actions
    from app.services.recommendation_forward_window import _key_signals_by_issue
    from app.services.recommendation_title_index import RecommendationPipelineIndexCache
    from app.services.unified_collector_intelligence import generate_unified_collector_recommendations

    cache = index_cache or RecommendationPipelineIndexCache(owner_user_id=owner_user_id)
    timer = build_timings or CrossSystemBuildTiming()
    timer.attach_session(session)

    if refresh_upstream:
        timer.run(
            "refresh_unified",
            lambda: generate_unified_collector_recommendations(
                session,
                owner_user_id=owner_user_id,
                index_cache=cache,
            ),
        )
        timer.run(
            "refresh_daily",
            lambda: generate_daily_actions(
                session,
                owner_user_id=owner_user_id,
                refresh_unified=False,
                index_cache=cache,
            ),
        )

    def _load_index():
        return build_forward_release_title_index(
            session,
            owner_user_id=owner_user_id,
            pipeline_cache=cache,
        )

    release_index = timer.run("load_release_index", _load_index)

    unified = timer.run(
        "read_unified_candidates",
        lambda: _unified_candidates(session, owner_user_id=owner_user_id, release_index=release_index),
    )
    daily = timer.run(
        "read_daily_candidates",
        lambda: _list_daily_collector_actions(
            session, owner_user_id=owner_user_id, release_index=release_index
        ),
    )
    raw = unified + daily
    timer.run(
        "merge_unified_daily_lists",
        lambda: raw,
    )

    timer.run("enrich_estimated_values", lambda: _enrich_estimated_values(session, owner_user_id=owner_user_id, candidates=raw))

    resolved = timer.run("merge_candidates", lambda: _merge_raw_candidates(raw))

    def _issue_ids_for_resolved() -> list[int]:
        from app.services.recommendation_title_index import resolve_release_pair

        ids: list[int] = []
        for cand in resolved:
            pair = resolve_release_pair(cand.title, release_index)
            if pair is None or pair[0].id is None:
                continue
            ids.append(int(pair[0].id))
        return list(dict.fromkeys(ids))

    issue_ids = timer.run("resolve_issue_ids", _issue_ids_for_resolved)
    signals_by_issue = timer.run(
        "load_key_signals",
        lambda: _key_signals_by_issue(session, issue_ids=issue_ids),
    )

    def _quality_filter() -> list[_Candidate]:
        return [
            c
            for c in resolved
            if _candidate_passes_quality_filter(c, release_index=release_index, signals_by_issue=signals_by_issue)
        ]

    resolved = timer.run("quality_filter", _quality_filter)

    def _collector_significance_boost() -> None:
        apply_collector_significance_priority_boost(
            session,
            owner_user_id=owner_user_id,
            candidates=resolved,
            release_index=release_index,
            signals_by_issue=signals_by_issue,
        )

    timer.run("collector_significance_boost", _collector_significance_boost)
    timer.run(
        "priority_spread",
        lambda: apply_priority_spread_inplace(resolved),
    )
    timer.run(
        "confidence_spread",
        lambda: apply_confidence_spread_inplace(resolved),
    )
    timer.run(
        "budget_awareness",
        lambda: _apply_budget_awareness(session, owner_user_id=owner_user_id, candidates=resolved),
    )
    timer.run(
        "rank_candidates",
        lambda: resolved.sort(key=_candidate_sort_key) or resolved,
    )
    timer.run(
        "candidate_count",
        lambda: resolved,
    )
    session.expire_all()
    if build_timings is None:
        timer.log_summary()
    return resolved


def build_cross_system_candidates_timings(
    session: Session,
    *,
    owner_user_id: int,
    refresh_upstream: bool = False,
) -> tuple[list[_Candidate], dict[str, float]]:
    timer = CrossSystemBuildTiming()
    candidates = build_cross_system_candidates(
        session,
        owner_user_id=owner_user_id,
        refresh_upstream=refresh_upstream,
        build_timings=timer,
    )
    timer.log_summary()
    return candidates, dict(timer.steps_ms)


def _merge_raw_candidates(raw: list[_Candidate]) -> list[_Candidate]:
    by_type_title: dict[tuple[str, str], _Candidate] = {}
    for cand in raw:
        key = (cand.title_key, cand.recommendation_type)
        existing = by_type_title.get(key)
        if existing is None:
            by_type_title[key] = cand
            continue
        existing.source_systems.update(cand.source_systems)
        existing.priority_score = max(existing.priority_score, cand.priority_score)
        existing.raw_priority_score = max(
            existing.raw_priority_score or existing.priority_score,
            cand.raw_priority_score or cand.priority_score,
        )
        existing.raw_confidence_score = max(
            existing.raw_confidence_score or existing.confidence_score,
            cand.raw_confidence_score or cand.confidence_score,
        )
        existing.confidence_score = max(existing.confidence_score, cand.confidence_score)
        if cand.estimated_value is not None:
            existing.estimated_value = max(existing.estimated_value or 0.0, cand.estimated_value)
        if cand.rationale and cand.rationale not in existing.rationale:
            existing.rationale = f"{existing.rationale} {cand.rationale}".strip()

    merged = list(by_type_title.values())
    by_title: dict[str, list[_Candidate]] = {}
    for cand in merged:
        by_title.setdefault(cand.title_key, []).append(cand)

    resolved: list[_Candidate] = []
    for group in by_title.values():
        if len(group) == 1:
            c = group[0]
            if len(c.source_systems) > 1:
                c.confidence_score = _confidence_boost(c.confidence_score, len(c.source_systems), consistent=True)
                labels = ", ".join(sorted(c.source_systems))
                if "Supported by" not in c.rationale:
                    c.rationale = f"{c.rationale} Supported by {labels} systems.".strip()
            resolved.append(c)
        else:
            resolved.append(_resolve_conflicts(group))
    return resolved


# Bump when quality/ranking logic changes so persisted snapshots refresh after deploy.
RECOMMENDATION_PIPELINE_EPOCH = 11


def _snapshot_rows_sorted(snapshot: dict[int, CrossSystemRecommendation]) -> list[CrossSystemRecommendation]:
    return [snapshot[r] for r in sorted(snapshot.keys())]


def _snapshot_confidence_saturated(snapshot: dict[int, CrossSystemRecommendation]) -> bool:
    rows = _snapshot_rows_sorted(snapshot)
    if not rows:
        return False
    scores = [float(row.confidence_score) for row in rows[: min(20, len(rows))]]
    if not scores:
        return False
    if len(scores) == 1:
        return scores[0] >= 0.999
    return len({round(s, 3) for s in scores}) <= 1 and max(scores) >= 0.999


def _confidence_for_persist(cand: _Candidate) -> float:
    norm = float(cand.normalized_confidence_score or 0.0)
    if norm > 0.0:
        return _clamp_confidence(norm)
    return _clamp_confidence(float(cand.confidence_score))


def _finalize_confidence_for_persist(candidates: list[_Candidate]) -> None:
    for cand in candidates:
        norm = float(cand.normalized_confidence_score or 0.0)
        if norm <= 0.0:
            continue
        if cand.confidence_score >= 0.999 or abs(float(cand.confidence_score) - norm) >= 0.01:
            cand.confidence_score = _clamp_confidence(norm)


def _priority_for_persist(cand: _Candidate) -> float:
    """Score written to cross_system_recommendation.priority_score."""
    if cand.budget_priority_adjusted:
        return _clamp_priority(float(cand.priority_score))
    norm = float(cand.normalized_priority_score or 0.0)
    if norm > 0.0:
        return _clamp_priority(norm)
    return _clamp_priority(float(cand.priority_score))


def _finalize_candidate_priorities_for_persist(candidates: list[_Candidate]) -> None:
    """Ensure spread-normalized scores are on candidate.priority_score before persist."""
    for cand in candidates:
        if cand.budget_priority_adjusted:
            continue
        norm = float(cand.normalized_priority_score or 0.0)
        if norm <= 0.0:
            continue
        if cand.priority_score >= 99.0 or abs(float(cand.priority_score) - norm) >= 0.05:
            cand.priority_score = _clamp_priority(norm)


def _snapshot_scores_by_title(
    snapshot: dict[int, CrossSystemRecommendation],
) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for row in snapshot.values():
        key = (row.recommendation_type.strip().upper(), row.title.strip().lower())
        out[key] = float(row.priority_score)
    return out


def _persisted_priorities_stale(
    snapshot: dict[int, CrossSystemRecommendation],
    candidates: list[_Candidate],
) -> bool:
    if not candidates:
        return False
    if not snapshot:
        return True
    db_by_title = _snapshot_scores_by_title(snapshot)
    for cand in candidates:
        key = (cand.recommendation_type.strip().upper(), cand.title_key)
        db_score = db_by_title.get(key)
        if db_score is None:
            return True
        expected = _priority_for_persist(cand)
        if abs(db_score - expected) >= 0.05:
            return True
    return False


def _persisted_confidence_stale(
    snapshot: dict[int, CrossSystemRecommendation],
    candidates: list[_Candidate],
) -> bool:
    if not candidates:
        return False
    if not snapshot:
        return True
    if _snapshot_confidence_saturated(snapshot):
        return any(float(c.normalized_confidence_score or 0.0) < 0.99 for c in candidates)
    conf_by_title: dict[tuple[str, str], float] = {}
    for row in snapshot.values():
        key = (row.recommendation_type.strip().upper(), row.title.strip().lower())
        conf_by_title[key] = float(row.confidence_score)
    for cand in candidates:
        key = (cand.recommendation_type.strip().upper(), cand.title_key)
        db_conf = conf_by_title.get(key)
        if db_conf is None:
            return True
        expected = _confidence_for_persist(cand)
        if abs(db_conf - expected) >= 0.01:
            return True
    top_db = [float(row.confidence_score) for row in _snapshot_rows_sorted(snapshot)[:20]]
    if len(top_db) >= 2 and len({round(c, 3) for c in top_db}) <= 1 and top_db[0] >= 0.999:
        return True
    return False


def _candidate_signature(candidates: list[_Candidate]) -> list[tuple]:
    return [
        (
            RECOMMENDATION_PIPELINE_EPOCH,
            rank,
            c.recommendation_type,
            c.title,
            _priority_for_persist(c),
            _confidence_for_persist(c),
            c.rationale,
        )
        for rank, c in enumerate(candidates, start=1)
    ]


def _prior_snapshot_signature(session: Session, *, owner_user_id: int) -> list[tuple] | None:
    snapshot = _latest_snapshot_rows(session, owner_user_id=owner_user_id)
    if not snapshot:
        return None
    rows = [snapshot[r] for r in sorted(snapshot.keys())]
    return [
        (
            RECOMMENDATION_PIPELINE_EPOCH,
            int(row.recommendation_rank),
            row.recommendation_type,
            row.title,
            float(row.priority_score),
            float(row.confidence_score),
            row.rationale,
        )
        for row in rows
    ]


def generate_cross_system_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    refresh_upstream: bool = False,
    build_timings: CrossSystemBuildTiming | None = None,
    persist_timings: dict[str, float] | None = None,
    persist_audit: dict[str, object] | None = None,
    pipeline_report: dict[str, object] | None = None,
    index_cache: "RecommendationPipelineIndexCache | None" = None,
) -> int:
    from app.services.recommendation_pipeline_diagnostics import process_rss_mb

    timer = build_timings or CrossSystemBuildTiming()
    owned_timer = build_timings is None
    memory_before_mb = round(process_rss_mb(), 2)

    candidates = build_cross_system_candidates(
        session,
        owner_user_id=owner_user_id,
        refresh_upstream=refresh_upstream,
        build_timings=timer,
        index_cache=index_cache,
    )

    new_sig = timer.run("candidate_signature", lambda: _candidate_signature(candidates))
    prior_sig = timer.run(
        "prior_snapshot_signature",
        lambda: _prior_snapshot_signature(session, owner_user_id=owner_user_id),
    )
    snapshot = _latest_snapshot_rows(session, owner_user_id=owner_user_id)
    must_repersist = _persisted_priorities_stale(snapshot, candidates) or _persisted_confidence_stale(
        snapshot, candidates
    )
    if _snapshot_confidence_saturated(snapshot) and candidates:
        must_repersist = True
    top_expected_conf = [_confidence_for_persist(c) for c in candidates[:20]]
    if (
        top_expected_conf
        and len({round(c, 4) for c in top_expected_conf}) >= 2
        and _snapshot_confidence_saturated(snapshot)
    ):
        must_repersist = True
    if prior_sig is not None and prior_sig == new_sig and not must_repersist:
        if persist_timings is not None:
            persist_timings.update(timer.steps_ms)
            persist_timings["rows_inserted"] = 0.0
        elif owned_timer:
            timer.log_summary()
        return 0
    created = 0

    def _persist() -> int:
        nonlocal created
        apply_confidence_spread_inplace(candidates)
        _finalize_candidate_priorities_for_persist(candidates)
        _finalize_confidence_for_persist(candidates)
        batch_ts = utc_now()
        pre_insert: list[dict[str, object]] = []
        for rank, cand in enumerate(candidates, start=1):
            priority = _priority_for_persist(cand)
            confidence = _confidence_for_persist(cand)
            pre_insert.append(
                {
                    "rank": rank,
                    "title": cand.title,
                    "normalized_confidence_score": round(float(cand.normalized_confidence_score or 0.0), 4),
                    "confidence_for_persist": round(float(confidence), 4),
                    "row_confidence_score": round(float(confidence), 4),
                }
            )
            row = CrossSystemRecommendation(
                owner_user_id=owner_user_id,
                recommendation_type=cand.recommendation_type,
                priority_score=priority,
                confidence_score=confidence,
                title=cand.title,
                estimated_value=cand.estimated_value,
                recommendation_rank=rank,
                source_systems=sorted(cand.source_systems),
                rationale=cand.rationale,
                created_at=batch_ts,
            )
            session.add(row)
            created += 1
        if created:
            session.commit()
            session.expire_all()
        if persist_audit is not None:
            persist_audit["pipeline_epoch"] = RECOMMENDATION_PIPELINE_EPOCH
            persist_audit["pre_insert_sample"] = pre_insert[:12]
            persist_audit["pre_insert_distinct_confidence"] = len(
                {entry["row_confidence_score"] for entry in pre_insert}
            )
            post_snapshot = _latest_snapshot_rows(session, owner_user_id=owner_user_id)
            post_rows = _snapshot_rows_sorted(post_snapshot)
            post_scores = [round(float(row.confidence_score), 4) for row in post_rows[:20]]
            persist_audit["post_snapshot_distinct_confidence"] = len(set(post_scores))
            persist_audit["post_snapshot_confidence_sample"] = post_scores[:12]
            persist_audit["post_snapshot_matches_pre_insert"] = bool(pre_insert) and bool(post_rows) and all(
                abs(float(entry["row_confidence_score"]) - float(post_rows[idx].confidence_score)) < 0.001
                for idx, entry in enumerate(pre_insert[: min(len(pre_insert), len(post_rows))])
            )
        return created

    timer.run("persist_snapshot", _persist)
    memory_after_mb = round(process_rss_mb(), 2)
    build_memory = timer.memory_report() if hasattr(timer, "memory_report") else {}
    peak_memory_mb = float(build_memory.get("peak_memory_mb", memory_after_mb) or memory_after_mb)
    memory_payload = {
        "memory_before_mb": memory_before_mb,
        "memory_after_mb": memory_after_mb,
        "peak_memory_mb": peak_memory_mb,
        "build_stages": build_memory.get("stages"),
    }
    if persist_audit is not None:
        persist_audit.update(memory_payload)
        if index_cache is not None:
            persist_audit.update(index_cache.diagnostics())
    if pipeline_report is not None:
        pipeline_report["cross_system_recommendations"] = memory_payload
        if index_cache is not None:
            pipeline_report.update(index_cache.diagnostics())
    if persist_timings is not None:
        persist_timings.update(timer.steps_ms)
        persist_timings["rows_inserted"] = float(created)
        persist_timings["memory_before_mb"] = memory_before_mb
        persist_timings["memory_after_mb"] = memory_after_mb
        persist_timings["peak_memory_mb"] = peak_memory_mb
    elif owned_timer:
        timer.log_summary()
    session.expire_all()
    return created


def _latest_snapshot_rows(
    session: Session,
    *,
    owner_user_id: int,
    scan_limit: int = 1000,
) -> dict[int, CrossSystemRecommendation]:
    """Latest snapshot batch: rows sharing the newest created_at, else id chain fallback."""
    anchor = session.exec(
        select(CrossSystemRecommendation)
        .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
        .order_by(
            CrossSystemRecommendation.created_at.desc(),
            CrossSystemRecommendation.id.desc(),
        )
        .limit(1)
    ).first()
    if anchor is None:
        return {}

    anchor_ts = anchor.created_at
    batch_rows = list(
        session.exec(
            select(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
            .where(CrossSystemRecommendation.created_at == anchor_ts)
            .order_by(CrossSystemRecommendation.recommendation_rank.asc())
            .limit(max(1, int(scan_limit)))
        ).all()
    )
    if batch_rows:
        snapshot: dict[int, CrossSystemRecommendation] = {}
        for row in batch_rows:
            snapshot[int(row.recommendation_rank)] = row
        return snapshot

    window_start = anchor_ts - timedelta(seconds=2)
    window_end = anchor_ts + timedelta(seconds=2)
    batch_rows = list(
        session.exec(
            select(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
            .where(CrossSystemRecommendation.created_at >= window_start)
            .where(CrossSystemRecommendation.created_at <= window_end)
            .order_by(CrossSystemRecommendation.recommendation_rank.asc())
            .limit(max(1, int(scan_limit)))
        ).all()
    )
    if batch_rows:
        snapshot = {}
        for row in batch_rows:
            snapshot[int(row.recommendation_rank)] = row
        return snapshot

    max_id = int(anchor.id or 0)
    if max_id <= 0:
        return {}
    rows = session.exec(
        select(CrossSystemRecommendation)
        .where(
            CrossSystemRecommendation.owner_user_id == owner_user_id,
            CrossSystemRecommendation.id <= max_id,
        )
        .order_by(CrossSystemRecommendation.id.desc())
        .limit(max(1, int(scan_limit)))
    ).all()
    if not rows:
        return {}
    chain: list[CrossSystemRecommendation] = [rows[0]]
    for row in rows[1:]:
        if int(row.id or 0) != int(chain[-1].id or 0) - 1:
            break
        chain.append(row)
    snapshot = {}
    for row in chain:
        snapshot[int(row.recommendation_rank)] = row
    return snapshot


def _matches_idempotency(prior: CrossSystemRecommendation, cand: _Candidate, *, rank: int) -> bool:
    return (
        prior.recommendation_type == cand.recommendation_type
        and prior.title == cand.title
        and abs(float(prior.priority_score) - float(cand.priority_score)) < 1e-9
        and abs(float(prior.confidence_score) - float(cand.confidence_score)) < 1e-9
        and int(prior.recommendation_rank) == rank
        and prior.rationale == cand.rationale
    )
