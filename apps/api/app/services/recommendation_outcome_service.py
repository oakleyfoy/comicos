"""P73-01 recommendation outcome tracking service (no scoring/ranking changes)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.recommendation_action_event import (
    P73_ATTRIBUTION_MAP,
    P73_EVENT_RECOMMENDED,
    P73_EVENT_STAGE_ORDER,
    P73_ALL_EVENT_TYPES,
    P73RecommendationActionEvent,
)
from app.models.recommendation_outcome import P73RecommendationOutcome
from app.schemas.recommendation_event import (
    P73RecommendationEventCreatePayload,
    P73RecommendationEventRead,
    P73RecommendationTimelineEntryRead,
)
from app.schemas.recommendation_feedback import (
    P73RecommendationFeedbackDashboardRead,
    P73RecommendationFeedbackSummaryRead,
)
from app.schemas.recommendation_outcome import (
    P73RecommendationOutcomeCreatePayload,
    P73RecommendationOutcomeDetailRead,
    P73RecommendationOutcomeListResponse,
    P73RecommendationOutcomeRead,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_type(value: str) -> str:
    return value.strip().upper().replace(" ", "_")


def _expected_attribution(recommendation_type: str) -> str | None:
    key = _normalize_type(recommendation_type)
    return P73_ATTRIBUTION_MAP.get(key)


def _derive_status(events: list[P73RecommendationActionEvent]) -> str:
    if not events:
        return P73_EVENT_RECOMMENDED
    best = max(events, key=lambda e: P73_EVENT_STAGE_ORDER.get(e.event_type, 0))
    return best.event_type


def _apply_profit_metadata(outcome: P73RecommendationOutcome, metadata: dict) -> None:
    if not metadata:
        return
    if "actual_profit" in metadata and metadata["actual_profit"] is not None:
        outcome.actual_profit = Decimal(str(metadata["actual_profit"]))
    if "actual_roi_pct" in metadata and metadata["actual_roi_pct"] is not None:
        outcome.actual_roi_pct = Decimal(str(metadata["actual_roi_pct"]))
    if "expected_profit" in metadata and metadata["expected_profit"] is not None:
        outcome.expected_profit = Decimal(str(metadata["expected_profit"]))
    if "expected_roi_pct" in metadata and metadata["expected_roi_pct"] is not None:
        outcome.expected_roi_pct = Decimal(str(metadata["expected_roi_pct"]))


def _update_attribution(outcome: P73RecommendationOutcome, status: str) -> None:
    expected = _expected_attribution(outcome.recommendation_type)
    if expected is None:
        outcome.attribution_outcome = status
        outcome.attribution_accurate = None
        return
    outcome.attribution_outcome = status
    outcome.attribution_accurate = status == expected


def create_outcome(
    session: Session,
    *,
    owner_user_id: int,
    payload: P73RecommendationOutcomeCreatePayload,
) -> P73RecommendationOutcomeRead:
    today = payload.created_date or date.today()
    row = P73RecommendationOutcome(
        owner_user_id=owner_user_id,
        recommendation_id=payload.recommendation_id.strip(),
        inventory_copy_id=payload.inventory_copy_id,
        series=payload.series.strip(),
        issue=payload.issue.strip(),
        variant=payload.variant.strip(),
        publisher=(payload.publisher or "").strip(),
        character=(payload.character or "").strip(),
        creator=(payload.creator or "").strip(),
        expected_profit=payload.expected_profit,
        actual_profit=payload.actual_profit,
        expected_roi_pct=payload.expected_roi_pct,
        actual_roi_pct=payload.actual_roi_pct,
        recommendation_type=_normalize_type(payload.recommendation_type),
        recommendation_category=_normalize_type(payload.recommendation_category),
        created_date=today,
        current_status=P73_EVENT_RECOMMENDED,
        source_table=payload.source_table,
        source_row_id=payload.source_row_id,
        notes=payload.notes,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    append_event(
        session,
        owner_user_id=owner_user_id,
        outcome_id=int(row.id or 0),
        payload=P73RecommendationEventCreatePayload(
            event_type=P73_EVENT_RECOMMENDED,
            event_source="system",
            metadata_json={"recommendation_id": row.recommendation_id},
        ),
        skip_attribution_refresh=False,
    )
    session.commit()
    session.refresh(row)
    return P73RecommendationOutcomeRead.model_validate(row)


def append_event(
    session: Session,
    *,
    owner_user_id: int,
    outcome_id: int,
    payload: P73RecommendationEventCreatePayload,
    skip_attribution_refresh: bool = False,
) -> P73RecommendationEventRead:
    outcome = session.get(P73RecommendationOutcome, outcome_id)
    if outcome is None or outcome.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Recommendation outcome not found.")
    event_type = _normalize_type(payload.event_type)
    if event_type not in P73_ALL_EVENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
    event = P73RecommendationActionEvent(
        owner_user_id=owner_user_id,
        outcome_id=outcome_id,
        event_type=event_type,
        event_source=payload.event_source or "manual",
        metadata_json=dict(payload.metadata_json or {}),
        notes=payload.notes,
        created_at=utc_now(),
    )
    session.add(event)
    session.flush()
    if not skip_attribution_refresh:
        events = list(
            session.exec(
                select(P73RecommendationActionEvent).where(P73RecommendationActionEvent.outcome_id == outcome_id)
            ).all()
        )
        status = _derive_status(events)
        outcome.current_status = status
        outcome.updated_at = utc_now()
        _update_attribution(outcome, status)
        _apply_profit_metadata(outcome, payload.metadata_json or {})
        session.add(outcome)
    session.commit()
    session.refresh(event)
    return P73RecommendationEventRead.model_validate(event)


def build_timeline(
    session: Session,
    *,
    owner_user_id: int,
    outcome_id: int,
) -> list[P73RecommendationTimelineEntryRead]:
    outcome = session.get(P73RecommendationOutcome, outcome_id)
    if outcome is None or outcome.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Recommendation outcome not found.")
    events = session.exec(
        select(P73RecommendationActionEvent)
        .where(P73RecommendationActionEvent.outcome_id == outcome_id)
        .order_by(P73RecommendationActionEvent.created_at.asc(), P73RecommendationActionEvent.id.asc())
    ).all()
    return [
        P73RecommendationTimelineEntryRead(
            event_type=e.event_type,
            event_source=e.event_source,
            created_at=e.created_at,
            metadata_json=dict(e.metadata_json or {}),
        )
        for e in events
    ]


def get_outcome_detail(
    session: Session,
    *,
    owner_user_id: int,
    outcome_id: int,
) -> P73RecommendationOutcomeDetailRead:
    outcome = session.get(P73RecommendationOutcome, outcome_id)
    if outcome is None or outcome.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Recommendation outcome not found.")
    return P73RecommendationOutcomeDetailRead(
        outcome=P73RecommendationOutcomeRead.model_validate(outcome),
        timeline=build_timeline(session, owner_user_id=owner_user_id, outcome_id=outcome_id),
    )


def list_outcomes(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> P73RecommendationOutcomeListResponse:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = list(
        session.exec(
            select(P73RecommendationOutcome)
            .where(P73RecommendationOutcome.owner_user_id == owner_user_id)
            .order_by(P73RecommendationOutcome.created_at.desc(), P73RecommendationOutcome.id.desc())
        ).all()
    )
    page = rows[offset : offset + limit]
    return P73RecommendationOutcomeListResponse(
        items=[P73RecommendationOutcomeRead.model_validate(r) for r in page],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def build_feedback_summary(session: Session, *, owner_user_id: int) -> P73RecommendationFeedbackSummaryRead:
    outcomes = list(
        session.exec(
            select(P73RecommendationOutcome).where(P73RecommendationOutcome.owner_user_id == owner_user_id)
        ).all()
    )
    event_rows = list(
        session.exec(
            select(P73RecommendationActionEvent).where(P73RecommendationActionEvent.owner_user_id == owner_user_id)
        ).all()
    )
    counts = {k: 0 for k in ("VIEWED", "PURCHASED", "SKIPPED", "WATCHLISTED", "HELD", "GRADED", "LISTED", "SOLD")}
    for e in event_rows:
        if e.event_type in counts:
            counts[e.event_type] += 1
    matches = sum(1 for o in outcomes if o.attribution_accurate is True)
    samples = sum(1 for o in outcomes if o.attribution_accurate is not None)
    acc_pct = round(matches / samples * 100.0, 1) if samples else 0.0
    return P73RecommendationFeedbackSummaryRead(
        recommendations_created=len(outcomes),
        viewed=counts["VIEWED"],
        purchased=counts["PURCHASED"],
        skipped=counts["SKIPPED"],
        watchlisted=counts["WATCHLISTED"],
        held=counts["HELD"],
        graded=counts["GRADED"],
        listed=counts["LISTED"],
        sold=counts["SOLD"],
        attribution_matches=matches,
        attribution_samples=samples,
        attribution_accuracy_pct=acc_pct,
    )


def build_feedback_dashboard(session: Session, *, owner_user_id: int) -> P73RecommendationFeedbackDashboardRead:
    summary = build_feedback_summary(session, owner_user_id=owner_user_id)
    listed = list_outcomes(session, owner_user_id=owner_user_id, limit=15, offset=0)
    return P73RecommendationFeedbackDashboardRead(summary=summary, recent_outcomes=listed.items)


def record_automatic_event_for_inventory(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    event_type: str,
    event_source: str,
    metadata_json: dict | None = None,
) -> None:
    """Append workflow event to open outcomes for this copy (no inference if none linked)."""
    rows = session.exec(
        select(P73RecommendationOutcome)
        .where(P73RecommendationOutcome.owner_user_id == owner_user_id)
        .where(P73RecommendationOutcome.inventory_copy_id == inventory_copy_id)
        .order_by(P73RecommendationOutcome.id.desc())
    ).all()
    if not rows:
        return
    payload = P73RecommendationEventCreatePayload(
        event_type=event_type,
        event_source=event_source,
        metadata_json=metadata_json or {},
    )
    for outcome in rows[:3]:
        append_event(
            session,
            owner_user_id=owner_user_id,
            outcome_id=int(outcome.id or 0),
            payload=payload,
        )
