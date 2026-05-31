from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.unified_collector_intelligence import UnifiedCollectorRecommendation
from app.schemas.unified_collector_intelligence import (
    UnifiedCollectorRecommendationRead,
    UnifiedCollectorSummaryRead,
)
from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows
from app.services.collection_gaps import latest_collection_gap_rows
from app.services.foc_dates import days_until_foc, utc_today
from app.services.grade_before_sell import _latest_rows as _latest_grade_before_sell_rows
from app.services.hold_sell_intelligence import _latest_hold_sell_rows, _to_read as hold_sell_to_read
from app.services.portfolio_rebalancing import _latest_rows as _latest_rebalance_rows
from app.services.pull_list_decisions import _latest_decision_rows as _latest_pull_decisions
from app.services.purchase_quantities import _latest_quantity_rows, _to_read as purchase_qty_to_read
from app.services.sell_candidates import _latest_sell_candidate_rows, _to_read as sell_candidate_to_read

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

_GAP_PRIORITY = {"CRITICAL": 95.0, "HIGH": 88.0, "MEDIUM": 72.0, "LOW": 55.0}


@dataclass
class _Draft:
    recommendation_type: str
    title: str
    rationale: str
    source_systems: set[str] = field(default_factory=set)
    priority_score: float = 0.0
    confidence_score: float = 0.0

    @property
    def merge_key(self) -> str:
        return f"{self.recommendation_type}|{self.title.strip().lower()}"


def _clamp_priority(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


def _clamp_confidence(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _combined_confidence(base: float, source_count: int) -> float:
    boost = min(0.25, 0.08 * max(0, source_count - 1))
    return _clamp_confidence(base + boost)


def _combined_priority(base: float, source_count: int) -> float:
    bonus = min(8.0, max(0, source_count - 1) * 3.0)
    return _clamp_priority(base + bonus)


def _display_title(*, series_name: str, issue_number: str) -> str:
    series = (series_name or "Unknown").strip()
    issue = (issue_number or "").strip()
    if issue:
        return f"{series} #{issue}"
    return series


def _acquire_key(*, publisher: str, series_name: str, issue_number: str) -> str:
    return "|".join(
        [
            publisher.strip().lower(),
            series_name.strip().lower(),
            issue_number.strip().lower(),
        ]
    )


def _merge_draft(store: dict[str, _Draft], draft: _Draft) -> None:
    existing = store.get(draft.merge_key)
    if existing is None:
        store[draft.merge_key] = draft
        return
    existing.source_systems.update(draft.source_systems)
    n = len(existing.source_systems)
    existing.priority_score = _combined_priority(max(existing.priority_score, draft.priority_score), n)
    existing.confidence_score = _combined_confidence(max(existing.confidence_score, draft.confidence_score), n)
    if draft.rationale and draft.rationale not in existing.rationale:
        existing.rationale = f"{existing.rationale} {draft.rationale}".strip()


def _foc_priority(foc_date) -> float:
    days = days_until_foc(foc_date, today=utc_today())
    if days is None:
        return 78.0
    if days < 0:
        return 82.0
    if days <= 7:
        return 92.0
    if days <= 14:
        return 87.0
    if days <= 30:
        return 80.0
    return 70.0


def _collect_pull_list_drafts(session: Session, *, owner_user_id: int) -> list[_Draft]:
    drafts: list[_Draft] = []
    decisions = _latest_pull_decisions(session, owner_user_id=owner_user_id)
    for row in decisions.values():
        issue = session.get(ReleaseIssue, row.release_id)
        series = session.get(ReleaseSeries, issue.series_id) if issue else None
        if issue is None:
            continue
        title = _display_title(series_name=series.series_name if series else "", issue_number=issue.issue_number)
        if row.decision_type in {"START_RUN", "CONTINUE_RUN"}:
            days = days_until_foc(issue.foc_date, today=utc_today())
            if days is not None and days <= 30:
                rationale = "FOC deadline approaching."
                if days is not None and days >= 0:
                    rationale = f"FOC deadline approaching ({days} days)."
                drafts.append(
                    _Draft(
                        recommendation_type=TYPE_PREORDER,
                        title=title,
                        rationale=rationale,
                        source_systems={SRC_PULL},
                        priority_score=_foc_priority(issue.foc_date),
                        confidence_score=_clamp_confidence(float(row.confidence_score)),
                    )
                )
        elif row.decision_type == "WATCH":
            drafts.append(
                _Draft(
                    recommendation_type=TYPE_WATCH,
                    title=title,
                    rationale="Pull list watch signal; monitor before committing.",
                    source_systems={SRC_PULL},
                    priority_score=45.0,
                    confidence_score=_clamp_confidence(float(row.confidence_score) * 0.85),
                )
            )
    return drafts


def _collect_purchase_drafts(session: Session, *, owner_user_id: int) -> list[_Draft]:
    drafts: list[_Draft] = []
    for release_id, row in _latest_quantity_rows(session, owner_user_id=owner_user_id).items():
        if row.quantity_recommended <= 0:
            continue
        read = purchase_qty_to_read(session, row=row, pull_decision=None)
        title = _display_title(series_name=read.series_name, issue_number=read.issue_number)
        issue = session.get(ReleaseIssue, release_id)
        priority = 82.0
        if issue and issue.foc_date is not None:
            priority = max(priority, _foc_priority(issue.foc_date))
        drafts.append(
            _Draft(
                recommendation_type=TYPE_PREORDER,
                title=title,
                rationale=read.rationale or "Purchase quantity recommendation for upcoming release.",
                source_systems={SRC_PURCHASE},
                priority_score=priority,
                confidence_score=_clamp_confidence(float(row.confidence_score)),
            )
        )
    return drafts


def _collect_portfolio_acquire_drafts(session: Session, *, owner_user_id: int) -> list[_Draft]:
    drafts: list[_Draft] = []
    for row in latest_collection_gap_rows(session, owner_user_id=owner_user_id).values():
        title = _display_title(series_name=row.series_name, issue_number=row.issue_number)
        drafts.append(
            _Draft(
                recommendation_type=TYPE_ACQUIRE,
                title=title,
                rationale=row.rationale or "Missing issue in an otherwise complete run.",
                source_systems={SRC_PORTFOLIO},
                priority_score=_GAP_PRIORITY.get(row.priority, 70.0),
                confidence_score=0.58,
            )
        )
    return drafts


def _collect_acquisition_drafts(session: Session, *, owner_user_id: int) -> list[_Draft]:
    drafts: list[_Draft] = []
    for row in latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id).values():
        title = _display_title(series_name=row.series_name, issue_number=row.issue_number)
        drafts.append(
            _Draft(
                recommendation_type=TYPE_ACQUIRE,
                title=title,
                rationale=row.rationale or "Acquisition opportunity identified.",
                source_systems={SRC_ACQUISITION},
                priority_score=_clamp_priority(float(row.priority_score)),
                confidence_score=_clamp_confidence(float(row.confidence_score)),
            )
        )
    return drafts


def _collect_portfolio_sell_drafts(session: Session, *, owner_user_id: int) -> list[_Draft]:
    drafts: list[_Draft] = []
    for row in _latest_sell_candidate_rows(session, owner_user_id=owner_user_id).values():
        if row.recommendation not in {"SELL", "STRONG_SELL"}:
            continue
        read = sell_candidate_to_read(session, row=row)
        title = _display_title(series_name=read.title, issue_number=read.issue_number)
        base = 76.0 if row.recommendation == "SELL" else 82.0
        drafts.append(
            _Draft(
                recommendation_type=TYPE_SELL,
                title=title,
                rationale=read.rationale or "Portfolio sell candidate identified.",
                source_systems={SRC_PORTFOLIO},
                priority_score=base,
                confidence_score=_clamp_confidence(float(row.confidence_score)),
            )
        )
    return drafts


def _collect_exit_drafts(session: Session, *, owner_user_id: int) -> list[_Draft]:
    drafts: list[_Draft] = []
    for row in _latest_hold_sell_rows(session, owner_user_id=owner_user_id).values():
        read = hold_sell_to_read(session, row=row)
        title = _display_title(series_name=read.title, issue_number=read.issue_number)
        if row.recommendation == "SELL":
            drafts.append(
                _Draft(
                    recommendation_type=TYPE_SELL,
                    title=title,
                    rationale=read.rationale or "Duplicate profitable inventory supports exit.",
                    source_systems={SRC_EXIT},
                    priority_score=_clamp_priority(float(row.conviction_score)),
                    confidence_score=_clamp_confidence(float(row.confidence_score)),
                )
            )
        elif row.recommendation == "WATCH":
            drafts.append(
                _Draft(
                    recommendation_type=TYPE_WATCH,
                    title=title,
                    rationale=read.rationale or "Moderate exit opportunity; monitor timing.",
                    source_systems={SRC_EXIT},
                    priority_score=_clamp_priority(min(60.0, float(row.conviction_score))),
                    confidence_score=_clamp_confidence(float(row.confidence_score) * 0.9),
                )
            )

    for row in _latest_grade_before_sell_rows(session, owner_user_id=owner_user_id).values():
        if row.recommendation != "GRADE_BEFORE_SELL":
            continue
        from app.services.grade_before_sell import _to_read as gbs_to_read

        read = gbs_to_read(session, row=row)
        title = _display_title(series_name=read.title, issue_number=read.issue_number)
        priority = 80.0 + min(15.0, float(row.expected_roi) * 5.0)
        drafts.append(
            _Draft(
                recommendation_type=TYPE_GRADE,
                title=title,
                rationale=read.rationale or "Strong grading upside identified.",
                source_systems={SRC_EXIT},
                priority_score=_clamp_priority(priority),
                confidence_score=_clamp_confidence(float(row.confidence_score)),
            )
        )

    for key, row in _latest_rebalance_rows(session, owner_user_id=owner_user_id).items():
        if row.recommended_action not in {"REDUCE_EXPOSURE", "REVIEW_POSITION"}:
            continue
        title = row.target_label.strip() or key[1]
        drafts.append(
            _Draft(
                recommendation_type=TYPE_REBALANCE,
                title=title,
                rationale=row.rationale or "Portfolio exposure exceeds target.",
                source_systems={SRC_EXIT},
                priority_score=_clamp_priority(float(row.priority_score)),
                confidence_score=_clamp_confidence(float(row.confidence_score)),
            )
        )
    return drafts


def _build_drafts(session: Session, *, owner_user_id: int) -> list[_Draft]:
    store: dict[str, _Draft] = {}
    for draft in (
        _collect_pull_list_drafts(session, owner_user_id=owner_user_id)
        + _collect_purchase_drafts(session, owner_user_id=owner_user_id)
        + _collect_portfolio_acquire_drafts(session, owner_user_id=owner_user_id)
        + _collect_acquisition_drafts(session, owner_user_id=owner_user_id)
        + _collect_portfolio_sell_drafts(session, owner_user_id=owner_user_id)
        + _collect_exit_drafts(session, owner_user_id=owner_user_id)
    ):
        _merge_draft(store, draft)

    merged: list[_Draft] = list(store.values())
    merged.sort(
        key=lambda d: (
            -d.priority_score,
            -d.confidence_score,
            d.recommendation_type,
            d.title.lower(),
        )
    )
    return merged


def _latest_recommendation_rows(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[tuple[str, str], UnifiedCollectorRecommendation]:
    rows = session.exec(
        select(UnifiedCollectorRecommendation)
        .where(UnifiedCollectorRecommendation.owner_user_id == owner_user_id)
        .order_by(UnifiedCollectorRecommendation.created_at.desc(), UnifiedCollectorRecommendation.id.desc())
    ).all()
    latest: dict[tuple[str, str], UnifiedCollectorRecommendation] = {}
    for row in rows:
        key = (row.recommendation_type, row.title.strip().lower())
        if key not in latest:
            latest[key] = row
    return latest


def _sources_equal(a: list[str], b: list[str]) -> bool:
    return sorted(a) == sorted(b)


def _matches_idempotency(prior: UnifiedCollectorRecommendation, draft: _Draft) -> bool:
    return (
        prior.recommendation_type == draft.recommendation_type
        and prior.title == draft.title
        and abs(float(prior.priority_score) - float(draft.priority_score)) < 1e-9
        and abs(float(prior.confidence_score) - float(draft.confidence_score)) < 1e-9
        and prior.rationale == draft.rationale
    )


def generate_unified_collector_recommendations(session: Session, *, owner_user_id: int) -> int:
    drafts = _build_drafts(session, owner_user_id=owner_user_id)
    latest = _latest_recommendation_rows(session, owner_user_id=owner_user_id)
    created = 0
    for draft in drafts:
        key = (draft.recommendation_type, draft.title.strip().lower())
        prior = latest.get(key)
        sources = sorted(draft.source_systems)
        if prior is not None and _matches_idempotency(prior, draft):
            continue
        row = UnifiedCollectorRecommendation(
            owner_user_id=owner_user_id,
            recommendation_type=draft.recommendation_type,
            priority_score=draft.priority_score,
            confidence_score=draft.confidence_score,
            title=draft.title,
            rationale=draft.rationale,
            source_systems=sources,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def _to_read(row: UnifiedCollectorRecommendation) -> UnifiedCollectorRecommendationRead:
    return UnifiedCollectorRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        recommendation_type=row.recommendation_type,
        priority_score=float(row.priority_score),
        confidence_score=float(row.confidence_score),
        title=row.title,
        rationale=row.rationale,
        source_systems=list(row.source_systems or []),
        created_at=row.created_at,
    )


def list_latest_unified_collector_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    priority_min: float | None = None,
    source_system: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[UnifiedCollectorRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_recommendation_rows(session, owner_user_id=owner_user_id)
    items: list[UnifiedCollectorRecommendationRead] = []
    for row in latest.values():
        if recommendation_type and row.recommendation_type != recommendation_type.strip().upper():
            continue
        if priority_min is not None and float(row.priority_score) < float(priority_min):
            continue
        if source_system:
            needle = source_system.strip().upper()
            if needle not in {str(s).upper() for s in (row.source_systems or [])}:
                continue
        items.append(_to_read(row))
    items.sort(
        key=lambda r: (
            -r.priority_score,
            -r.confidence_score,
            r.recommendation_type,
            r.title.lower(),
            -r.id,
        )
    )
    total = len(items)
    return items[offset : offset + limit], total


def get_unified_collector_summary(session: Session, *, owner_user_id: int) -> UnifiedCollectorSummaryRead:
    items, total = list_latest_unified_collector_recommendations(session, owner_user_id=owner_user_id, limit=500, offset=0)
    counts = {t: 0 for t in (TYPE_PREORDER, TYPE_ACQUIRE, TYPE_GRADE, TYPE_SELL, TYPE_REBALANCE, TYPE_WATCH)}
    multi = 0
    priority_sum = 0.0
    confidence_sum = 0.0
    for item in items:
        counts[item.recommendation_type] = counts.get(item.recommendation_type, 0) + 1
        if len(item.source_systems) > 1:
            multi += 1
        priority_sum += item.priority_score
        confidence_sum += item.confidence_score
    avg_p = round(priority_sum / total, 1) if total else 0.0
    avg_c = round(confidence_sum / total, 4) if total else 0.0
    return UnifiedCollectorSummaryRead(
        total_recommendations=total,
        preorder_count=counts[TYPE_PREORDER],
        acquire_count=counts[TYPE_ACQUIRE],
        grade_count=counts[TYPE_GRADE],
        sell_count=counts[TYPE_SELL],
        rebalance_count=counts[TYPE_REBALANCE],
        watch_count=counts[TYPE_WATCH],
        multi_source_count=multi,
        average_priority=avg_p,
        average_confidence=avg_c,
    )


def refresh_and_list_latest_unified_collector_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    priority_min: float | None = None,
    source_system: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[UnifiedCollectorRecommendationRead], int]:
    generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
    return list_latest_unified_collector_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation_type=recommendation_type,
        priority_min=priority_min,
        source_system=source_system,
        limit=limit,
        offset=offset,
    )
