from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows
from app.services.grade_before_sell import _latest_rows as _latest_grade_rows
from app.services.hold_sell_intelligence import _latest_hold_sell_rows
from app.services.purchase_budgets import get_purchase_budget_row
from app.services.unified_collector_intelligence import (
    _latest_recommendation_rows as _latest_unified_rows,
    generate_unified_collector_recommendations,
)
from app.services.recommendation_catalog_quality import (
    apply_price_discipline,
    build_forward_release_title_index,
    classify_catalog_text,
    classify_forward_release,
    should_include_in_top_recommendations,
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

    @property
    def title_key(self) -> str:
        return self.title.strip().lower()


def _clamp_priority(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


def _clamp_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _confidence_boost(base: float, source_count: int, *, consistent: bool) -> float:
    boost = min(0.25, 0.08 * max(0, source_count - 1))
    if consistent:
        boost += 0.04
    return _clamp_confidence(base + boost)


def _list_daily_collector_actions(session: Session, *, owner_user_id: int) -> list[_Candidate]:
    from app.models.daily_action_engine import DailyCollectorAction

    rows = session.exec(
        select(DailyCollectorAction)
        .where(DailyCollectorAction.owner_user_id == owner_user_id)
        .order_by(DailyCollectorAction.created_at.desc(), DailyCollectorAction.id.desc())
    ).all()
    latest: dict[tuple[str, str], DailyCollectorAction] = {}
    for row in rows:
        key = (row.action_type, row.title.strip().lower())
        if key not in latest:
            latest[key] = row
    out: list[_Candidate] = []
    for row in latest.values():
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
            )
        )
    return out


def _unified_candidates(session: Session, *, owner_user_id: int) -> list[_Candidate]:
    out: list[_Candidate] = []
    for row in _latest_unified_rows(session, owner_user_id=owner_user_id).values():
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
            )
        )
    return out


def _enrich_estimated_values(session: Session, *, owner_user_id: int, candidates: list[_Candidate]) -> None:
    opps = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    grade_rows = _latest_grade_rows(session, owner_user_id=owner_user_id)
    hold_rows = _latest_hold_sell_rows(session, owner_user_id=owner_user_id)

    for cand in candidates:
        if cand.estimated_value is not None:
            continue
        parts = cand.title.split("#", 1)
        series = parts[0].strip().lower()
        issue = parts[1].strip() if len(parts) > 1 else ""
        for row in opps.values():
            if row.series_name.strip().lower() == series and row.issue_number.strip() == issue:
                if row.value_gap is not None:
                    cand.estimated_value = round(float(row.value_gap), 2)
                elif row.target_price is not None:
                    cand.estimated_value = round(float(row.target_price), 2)
                break
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
    priority = _clamp_priority(best_priority + min(8.0, max(0, len(merged_sources) - 1) * 2.0))

    return _Candidate(
        recommendation_type=winner_type,
        title=group[0].title,
        priority_score=priority,
        confidence_score=confidence,
        estimated_value=est,
        source_systems=merged_sources,
        rationale=rationale,
    )


def _apply_budget_awareness(session: Session, *, owner_user_id: int, candidates: list[_Candidate]) -> None:
    budget = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    constrained = budget.is_active and budget.monthly_budget > 0 and budget.monthly_budget < 150.0
    if not constrained:
        return
    for cand in candidates:
        if cand.recommendation_type == TYPE_PREORDER and cand.priority_score < 90.0:
            cand.priority_score = _clamp_priority(cand.priority_score - 12.0)
            cand.rationale = f"{cand.rationale} Budget constrained; critical acquisition preferred over low-priority preorder.".strip()
        if cand.recommendation_type == TYPE_ACQUIRE and cand.priority_score >= 88.0:
            cand.priority_score = _clamp_priority(cand.priority_score + 4.0)
            cand.rationale = f"{cand.rationale} Budget constrained; critical acquisition prioritized.".strip()


def _parse_title_for_quality(title: str) -> tuple[str, str | None]:
    if "#" in title:
        series, issue = title.split("#", 1)
        return series.strip(), issue.strip()
    return title.strip(), None


def _candidate_passes_quality_filter(
    cand: _Candidate,
    *,
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
    signals_by_issue: dict[int, list[str]],
) -> bool:
    title_key = cand.title.strip().lower()
    if title_key.endswith(" (variants)"):
        title_key = title_key[: -len(" (variants)")]
    pair = release_index.get(title_key)
    if pair is not None:
        issue, series = pair
        issue_id = int(issue.id or 0)
        signals = signals_by_issue.get(issue_id, [])
        quality = classify_forward_release(
            issue,
            series,
            key_signals=signals,
            confidence_score=cand.confidence_score,
        )
        return should_include_in_top_recommendations(quality)

    series, issue = _parse_title_for_quality(cand.title)
    quality = classify_catalog_text(series_name=series, issue_number=issue, title=cand.title)
    quality = apply_price_discipline(quality, cover_price=None, issue_number=issue, title=cand.title)
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


def build_cross_system_candidates(session: Session, *, owner_user_id: int) -> list[_Candidate]:
    from app.services.daily_action_engine import generate_daily_actions
    from app.services.recommendation_forward_window import _key_signals_by_issue

    generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
    generate_daily_actions(session, owner_user_id=owner_user_id)
    raw = _unified_candidates(session, owner_user_id=owner_user_id) + _list_daily_collector_actions(
        session, owner_user_id=owner_user_id
    )
    _enrich_estimated_values(session, owner_user_id=owner_user_id, candidates=raw)
    resolved = _merge_raw_candidates(raw)
    release_index = build_forward_release_title_index(session, owner_user_id=owner_user_id)
    issue_ids = [int(issue.id or 0) for issue, _ in release_index.values() if issue.id is not None]
    signals_by_issue = _key_signals_by_issue(session, issue_ids=issue_ids)
    resolved = [
        c
        for c in resolved
        if _candidate_passes_quality_filter(c, release_index=release_index, signals_by_issue=signals_by_issue)
    ]
    _apply_budget_awareness(session, owner_user_id=owner_user_id, candidates=resolved)
    resolved.sort(key=_candidate_sort_key)
    return resolved


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


def _candidate_signature(candidates: list[_Candidate]) -> list[tuple]:
    return [
        (
            rank,
            c.recommendation_type,
            c.title,
            c.priority_score,
            c.confidence_score,
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
            int(row.recommendation_rank),
            row.recommendation_type,
            row.title,
            float(row.priority_score),
            float(row.confidence_score),
            row.rationale,
        )
        for row in rows
    ]


def generate_cross_system_recommendations(session: Session, *, owner_user_id: int) -> int:
    candidates = build_cross_system_candidates(session, owner_user_id=owner_user_id)
    new_sig = _candidate_signature(candidates)
    prior_sig = _prior_snapshot_signature(session, owner_user_id=owner_user_id)
    if prior_sig is not None and prior_sig == new_sig:
        return 0
    created = 0
    for rank, cand in enumerate(candidates, start=1):
        row = CrossSystemRecommendation(
            owner_user_id=owner_user_id,
            recommendation_type=cand.recommendation_type,
            priority_score=cand.priority_score,
            confidence_score=cand.confidence_score,
            title=cand.title,
            estimated_value=cand.estimated_value,
            recommendation_rank=rank,
            source_systems=sorted(cand.source_systems),
            rationale=cand.rationale,
        )
        session.add(row)
        created += 1
    if created:
        session.commit()
    return created


def _latest_snapshot_rows(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[int, CrossSystemRecommendation]:
    rows = session.exec(
        select(CrossSystemRecommendation)
        .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
        .order_by(CrossSystemRecommendation.id.desc())
    ).all()
    if not rows:
        return {}
    batch: list[CrossSystemRecommendation] = [rows[0]]
    for row in rows[1:]:
        if int(row.id or 0) != int(batch[-1].id or 0) - 1:
            break
        batch.append(row)
    snapshot: dict[int, CrossSystemRecommendation] = {}
    for row in batch:
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
