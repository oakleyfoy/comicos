from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    AgentDefinition,
    CatalogIssue,
    ComicIssue,
    InventoryCopy,
    InventoryFmvSnapshot,
    MarketFmvSnapshot,
    MarketTrendSnapshot,
    OrderItem,
    User,
)
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    order_item_quantity_expr,
    publisher_expr,
    title_expr,
)
from app.schemas.intelligence import IntelligenceRunResponse
from app.services.agent_execution import complete_execution, fail_execution, start_execution
from app.services.intelligence_engine import (
    create_recommendation,
    attach_evidence,
    calculate_confidence_score,
    calculate_opportunity_score,
    calculate_priority_score,
)
from app.services.order_arrival_intelligence import compute_order_arrival_intelligence
from app.services.research_agent_base import create_snapshot, complete_snapshot, fail_snapshot

AGENT_CODE = "pricing_intelligence_agent"
RESEARCH_TYPE = "pricing_intelligence"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class _InventoryRow:
    inventory_copy_id: int
    metadata_identity_key: str | None
    canonical_issue_id: int | None
    title: str
    publisher: str
    issue_number: str
    acquisition_cost: Decimal
    current_fmv: Decimal | None
    grade_status: str
    hold_status: str
    order_status: str
    received_at: datetime | None


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("Pricing intelligence agent is not registered.")
    return int(row.id)


def _inventory_rows(session: Session, *, owner_user_id: int) -> list[_InventoryRow]:
    rows = session.exec(
        apply_inventory_spine_joins(
            select(
                InventoryCopy.id.label("inventory_copy_id"),
                InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
                func.coalesce(ComicIssue.id, CatalogIssue.id).label("canonical_issue_id"),
                title_expr().label("title"),
                publisher_expr().label("publisher"),
                issue_number_expr().label("issue_number"),
                InventoryCopy.acquisition_cost.label("acquisition_cost"),
                InventoryCopy.current_fmv.label("current_fmv"),
                InventoryCopy.grade_status.label("grade_status"),
                InventoryCopy.hold_status.label("hold_status"),
                InventoryCopy.order_status.label("order_status"),
                InventoryCopy.received_at.label("received_at"),
            ).select_from(InventoryCopy)
        )
        .where(InventoryCopy.user_id == owner_user_id)
        .order_by(InventoryCopy.id.asc())
    ).all()
    return [
        _InventoryRow(
            inventory_copy_id=int(row.inventory_copy_id),
            metadata_identity_key=str(row.metadata_identity_key) if row.metadata_identity_key is not None else None,
            canonical_issue_id=int(row.canonical_issue_id) if row.canonical_issue_id is not None else None,
            title=str(row.title),
            publisher=str(row.publisher),
            issue_number=str(row.issue_number),
            acquisition_cost=Decimal(str(row.acquisition_cost)),
            current_fmv=Decimal(str(row.current_fmv)) if row.current_fmv is not None else None,
            grade_status=str(row.grade_status),
            hold_status=str(row.hold_status),
            order_status=str(row.order_status),
            received_at=row.received_at,
        )
        for row in rows
    ]


def _latest_inventory_fmv_map(session: Session, *, inventory_copy_ids: list[int]) -> dict[int, InventoryFmvSnapshot]:
    if not inventory_copy_ids:
        return {}
    rows = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id.in_(inventory_copy_ids))
        .order_by(
            InventoryFmvSnapshot.inventory_copy_id.asc(),
            InventoryFmvSnapshot.changed_at.desc(),
            InventoryFmvSnapshot.id.desc(),
        )
    ).all()
    out: dict[int, InventoryFmvSnapshot] = {}
    for row in rows:
        out.setdefault(row.inventory_copy_id, row)
    return out


def _latest_market_fmv_maps(
    session: Session,
    *,
    metadata_identity_keys: list[str],
    canonical_issue_ids: list[int],
) -> tuple[dict[str, MarketFmvSnapshot], dict[int, MarketFmvSnapshot]]:
    by_key: dict[str, MarketFmvSnapshot] = {}
    by_issue: dict[int, MarketFmvSnapshot] = {}
    if metadata_identity_keys:
        rows = session.exec(
            select(MarketFmvSnapshot)
            .where(MarketFmvSnapshot.metadata_identity_key.in_(metadata_identity_keys))
            .order_by(
                MarketFmvSnapshot.metadata_identity_key.asc(),
                MarketFmvSnapshot.stale_data.asc(),
                MarketFmvSnapshot.snapshot_date.desc(),
                MarketFmvSnapshot.valuation_method.asc(),
                MarketFmvSnapshot.id.desc(),
            )
        ).all()
        for row in rows:
            if row.metadata_identity_key is not None:
                by_key.setdefault(str(row.metadata_identity_key), row)
    if canonical_issue_ids:
        rows = session.exec(
            select(MarketFmvSnapshot)
            .where(MarketFmvSnapshot.canonical_issue_id.in_(canonical_issue_ids))
            .order_by(
                MarketFmvSnapshot.canonical_issue_id.asc(),
                MarketFmvSnapshot.stale_data.asc(),
                MarketFmvSnapshot.snapshot_date.desc(),
                MarketFmvSnapshot.valuation_method.asc(),
                MarketFmvSnapshot.id.desc(),
            )
        ).all()
        for row in rows:
            if row.canonical_issue_id is not None:
                by_issue.setdefault(int(row.canonical_issue_id), row)
    return by_key, by_issue


def _latest_market_trend_maps(
    session: Session,
    *,
    metadata_identity_keys: list[str],
    canonical_issue_ids: list[int],
) -> tuple[dict[str, MarketTrendSnapshot], dict[int, MarketTrendSnapshot]]:
    by_key: dict[str, MarketTrendSnapshot] = {}
    by_issue: dict[int, MarketTrendSnapshot] = {}
    if metadata_identity_keys:
        rows = session.exec(
            select(MarketTrendSnapshot)
            .where(MarketTrendSnapshot.metadata_identity_key.in_(metadata_identity_keys))
            .order_by(
                MarketTrendSnapshot.metadata_identity_key.asc(),
                MarketTrendSnapshot.stale_data.asc(),
                MarketTrendSnapshot.created_at.desc(),
                MarketTrendSnapshot.id.desc(),
            )
        ).all()
        for row in rows:
            if row.metadata_identity_key is not None:
                by_key.setdefault(str(row.metadata_identity_key), row)
    if canonical_issue_ids:
        rows = session.exec(
            select(MarketTrendSnapshot)
            .where(MarketTrendSnapshot.canonical_issue_id.in_(canonical_issue_ids))
            .order_by(
                MarketTrendSnapshot.canonical_issue_id.asc(),
                MarketTrendSnapshot.stale_data.asc(),
                MarketTrendSnapshot.created_at.desc(),
                MarketTrendSnapshot.id.desc(),
            )
        ).all()
        for row in rows:
            if row.canonical_issue_id is not None:
                by_issue.setdefault(int(row.canonical_issue_id), row)
    return by_key, by_issue


def _find_market_fmv(
    row: _InventoryRow,
    *,
    by_key: dict[str, MarketFmvSnapshot],
    by_issue: dict[int, MarketFmvSnapshot],
) -> MarketFmvSnapshot | None:
    if row.metadata_identity_key and row.metadata_identity_key in by_key:
        return by_key[row.metadata_identity_key]
    if row.canonical_issue_id is not None and row.canonical_issue_id in by_issue:
        return by_issue[row.canonical_issue_id]
    return None


def _find_market_trend(
    row: _InventoryRow,
    *,
    by_key: dict[str, MarketTrendSnapshot],
    by_issue: dict[int, MarketTrendSnapshot],
) -> MarketTrendSnapshot | None:
    if row.metadata_identity_key and row.metadata_identity_key in by_key:
        return by_key[row.metadata_identity_key]
    if row.canonical_issue_id is not None and row.canonical_issue_id in by_issue:
        return by_issue[row.canonical_issue_id]
    return None


def _order_history_quantities(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], int]:
    # Reuse single expression objects so SELECT/GROUP BY/ORDER BY share the same
    # bound parameters; otherwise Postgres rejects the GROUP BY.
    title_e = title_expr()
    issue_e = issue_number_expr()
    rows = session.exec(
        apply_inventory_spine_joins(
            select(
                title_e.label("title"),
                issue_e.label("issue_number"),
                func.sum(order_item_quantity_expr()).label("total_quantity"),
            ).select_from(InventoryCopy)
        )
        .where(InventoryCopy.user_id == owner_user_id)
        .group_by(title_e, issue_e)
        .order_by(title_e.asc(), issue_e.asc())
    ).all()
    return {(str(row.title), str(row.issue_number)): int(row.total_quantity or 0) for row in rows}


def _trend_strength_score(row: MarketTrendSnapshot | None) -> float:
    if row is None:
        return 0.0
    strength = {
        "very_high": 1.0,
        "high": 0.85,
        "medium": 0.6,
        "low": 0.35,
        "very_low": 0.2,
    }.get(row.trend_strength, 0.0)
    percent = min(1.0, abs(float(row.percent_change)) / 25.0)
    return _clamp01((strength * 0.6) + (percent * 0.4))


def _persist_recommendation(
    session: Session,
    *,
    agent_execution_id: int,
    snapshot_id: int,
    recommendation_key: str,
    recommendation_type: str,
    title: str,
    description: str,
    inventory_copy_id: int | None,
    inventory_title: str,
    recommendation_payload_json: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    spread_score: float = 0.0,
    trend_score: float = 0.0,
    urgency_score: float = 0.0,
    scarcity_score: float = 0.0,
    data_gap_score: float = 0.0,
) -> tuple[str, Any]:
    evidence_scores = [float(row["evidence_score"]) for row in evidence_rows]
    confidence_score = calculate_confidence_score(
        evidence_scores=evidence_scores,
        supporting_signal_count=len(evidence_scores),
        data_freshness_score=1.0 if evidence_scores else 0.0,
    )
    opportunity_score = calculate_opportunity_score(
        spread_score=spread_score,
        trend_score=trend_score,
        urgency_score=urgency_score,
        scarcity_score=scarcity_score,
        data_gap_score=data_gap_score,
    )
    priority_score = calculate_priority_score(
        opportunity_score=opportunity_score,
        confidence_score=confidence_score,
        urgency_score=urgency_score,
    )
    recommendation = create_recommendation(
        session,
        agent_execution_id=agent_execution_id,
        recommendation_key=recommendation_key,
        recommendation_type=recommendation_type,
        title=title,
        description=description,
        inventory_copy_id=inventory_copy_id,
        inventory_title=inventory_title,
        confidence_score=confidence_score,
        opportunity_score=opportunity_score,
        priority_score=priority_score,
        recommendation_payload_json={"research_snapshot_id": snapshot_id, **recommendation_payload_json},
    )
    for evidence in evidence_rows:
        attach_evidence(
            session,
            recommendation_id=recommendation.id,
            evidence_type=str(evidence["evidence_type"]),
            evidence_source=str(evidence["evidence_source"]),
            evidence_payload_json=dict(evidence.get("evidence_payload_json") or {}),
            evidence_score=float(evidence["evidence_score"]),
        )
    return recommendation.recommendation_type, recommendation


def run_pricing_intelligence_agent(session: Session, *, current_user: User) -> IntelligenceRunResponse:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    agent_execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="intelligence_agent:pricing",
    )
    snapshot_id: int | None = None
    try:
        inventory_rows = _inventory_rows(session, owner_user_id=owner_user_id)
        inventory_ids = [row.inventory_copy_id for row in inventory_rows]
        metadata_keys = sorted({row.metadata_identity_key for row in inventory_rows if row.metadata_identity_key})
        canonical_issue_ids = sorted({row.canonical_issue_id for row in inventory_rows if row.canonical_issue_id is not None})
        latest_inventory_fmv = _latest_inventory_fmv_map(session, inventory_copy_ids=inventory_ids)
        market_fmv_by_key, market_fmv_by_issue = _latest_market_fmv_maps(
            session,
            metadata_identity_keys=metadata_keys,
            canonical_issue_ids=canonical_issue_ids,
        )
        market_trend_by_key, market_trend_by_issue = _latest_market_trend_maps(
            session,
            metadata_identity_keys=metadata_keys,
            canonical_issue_ids=canonical_issue_ids,
        )
        order_history = _order_history_quantities(session, owner_user_id=owner_user_id)
        arrival_response, _ = compute_order_arrival_intelligence(session, current_user=current_user)
        arrival_by_inventory: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for item in arrival_response.items:
            arrival_by_inventory[item.inventory_copy_id].append(
                {
                    "classification": item.classification,
                    "evidence_json": item.evidence_json,
                }
            )
        snapshot = create_snapshot(
            session,
            agent_execution_id=agent_execution.execution.id,
            agent_code=AGENT_CODE,
            research_type=RESEARCH_TYPE,
            input_scope_json={
                "owner_user_id": owner_user_id,
                "inventory_copy_count": len(inventory_rows),
                "arrival_intel_item_count": arrival_response.total_count,
            },
        )
        snapshot_id = snapshot.id
        recommendations = []
        recommendation_types: list[str] = []
        now = utc_now()

        for row in inventory_rows:
            effective_fmv = row.current_fmv
            inventory_fmv_row = latest_inventory_fmv.get(row.inventory_copy_id)
            if effective_fmv is None and inventory_fmv_row is not None:
                effective_fmv = inventory_fmv_row.new_fmv
            market_fmv_row = _find_market_fmv(row, by_key=market_fmv_by_key, by_issue=market_fmv_by_issue)
            trend_row = _find_market_trend(row, by_key=market_trend_by_key, by_issue=market_trend_by_issue)
            history_quantity = order_history.get((row.title, row.issue_number), 0)
            received_at = _as_utc(row.received_at)
            age_days = (now - received_at).days if received_at is not None else None
            arrival_bits = arrival_by_inventory.get(row.inventory_copy_id, [])

            base_evidence = [
                {
                    "evidence_type": "inventory_projection",
                    "evidence_source": "inventory_copy",
                    "evidence_payload_json": {
                        "inventory_copy_id": row.inventory_copy_id,
                        "title": row.title,
                        "issue_number": row.issue_number,
                        "acquisition_cost": _money(row.acquisition_cost),
                        "current_fmv": _money(row.current_fmv),
                        "grade_status": row.grade_status,
                        "hold_status": row.hold_status,
                        "order_status": row.order_status,
                        "received_at": None if received_at is None else received_at.isoformat(),
                    },
                    "evidence_score": 1.0,
                },
                {
                    "evidence_type": "order_history",
                    "evidence_source": "order_history",
                    "evidence_payload_json": {
                        "title": row.title,
                        "issue_number": row.issue_number,
                        "historical_quantity": history_quantity,
                    },
                    "evidence_score": 0.72,
                },
            ]
            if inventory_fmv_row is not None:
                base_evidence.append(
                    {
                        "evidence_type": "inventory_fmv_snapshot",
                        "evidence_source": "inventory_fmv_snapshot",
                        "evidence_payload_json": {
                            "new_fmv": _money(inventory_fmv_row.new_fmv),
                            "previous_fmv": _money(inventory_fmv_row.previous_fmv),
                            "changed_at": inventory_fmv_row.changed_at.isoformat(),
                            "source": inventory_fmv_row.source,
                        },
                        "evidence_score": 0.9,
                    }
                )
            if market_fmv_row is not None:
                base_evidence.append(
                    {
                        "evidence_type": "market_fmv_snapshot",
                        "evidence_source": "market_fmv_snapshot",
                        "evidence_payload_json": {
                            "snapshot_id": market_fmv_row.id,
                            "estimated_fmv": _money(market_fmv_row.estimated_fmv),
                            "comp_count": market_fmv_row.comp_count,
                            "valuation_method": market_fmv_row.valuation_method,
                            "snapshot_date": market_fmv_row.snapshot_date.isoformat(),
                            "stale_data": market_fmv_row.stale_data,
                        },
                        "evidence_score": 0.88,
                    }
                )
            if trend_row is not None:
                base_evidence.append(
                    {
                        "evidence_type": "market_trend_snapshot",
                        "evidence_source": "market_trend_snapshot",
                        "evidence_payload_json": {
                            "trend_window": trend_row.trend_window,
                            "trend_direction": trend_row.trend_direction,
                            "trend_strength": trend_row.trend_strength,
                            "percent_change": _money(trend_row.percent_change),
                            "comp_count": trend_row.comp_count,
                            "stale_data": trend_row.stale_data,
                        },
                        "evidence_score": 0.86,
                    }
                )
            for arrival in arrival_bits:
                base_evidence.append(
                    {
                        "evidence_type": "arrival_intelligence",
                        "evidence_source": "order_arrival_intelligence",
                        "evidence_payload_json": {
                            "classification": arrival["classification"],
                            "evidence_json": arrival["evidence_json"],
                        },
                        "evidence_score": 0.74,
                    }
                )

            cost_basis = float(row.acquisition_cost) if row.acquisition_cost else 0.0
            effective_fmv_float = float(effective_fmv) if effective_fmv is not None else 0.0
            upside_ratio = 0.0 if cost_basis <= 0 else max(0.0, (effective_fmv_float - cost_basis) / cost_basis)
            downside_ratio = 0.0 if cost_basis <= 0 else max(0.0, (cost_basis - effective_fmv_float) / cost_basis)
            trend_score = _trend_strength_score(trend_row)
            urgency_score = _clamp01(((age_days or 0) / 180.0)) if age_days is not None else 0.0
            scarcity_score = _clamp01(history_quantity / 4.0)
            spread_score = _clamp01(upside_ratio / 1.25)
            decline_spread_score = _clamp01(downside_ratio / 1.0)
            arrival_classifications = {item["classification"] for item in arrival_bits}

            if effective_fmv is not None and upside_ratio >= 0.35:
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"underpriced_inventory|{row.inventory_copy_id}",
                    recommendation_type="underpriced_inventory",
                    title=f"{row.title} #{row.issue_number} appears underpriced versus cost basis",
                    description="The internal value signals are materially above acquisition cost, making this copy a candidate for pricing review.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "review_price_position",
                        "effective_fmv": _money(effective_fmv),
                        "acquisition_cost": _money(row.acquisition_cost),
                    },
                    evidence_rows=base_evidence,
                    spread_score=spread_score,
                    trend_score=trend_score,
                    urgency_score=max(urgency_score, 0.45 if row.order_status == "received" else 0.2),
                    scarcity_score=scarcity_score,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if effective_fmv is not None and downside_ratio >= 0.2:
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"overpriced_inventory|{row.inventory_copy_id}",
                    recommendation_type="overpriced_inventory",
                    title=f"{row.title} #{row.issue_number} appears overpriced versus current signals",
                    description="The internal value signals are below acquisition cost, so this copy should be reviewed before future pricing action.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "review_for_price_reduction",
                        "effective_fmv": _money(effective_fmv),
                        "acquisition_cost": _money(row.acquisition_cost),
                    },
                    evidence_rows=base_evidence,
                    spread_score=decline_spread_score,
                    trend_score=trend_score if trend_row is not None and trend_row.trend_direction == "down" else 0.0,
                    urgency_score=max(0.4, urgency_score),
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if trend_row is not None and trend_row.trend_direction == "up" and abs(float(trend_row.percent_change)) >= 10.0:
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"rapid_appreciation_candidate|{row.inventory_copy_id}",
                    recommendation_type="rapid_appreciation_candidate",
                    title=f"{row.title} #{row.issue_number} is appreciating rapidly",
                    description="The latest internal market trend snapshot shows strong upward movement worth active monitoring.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "monitor_appreciation",
                        "percent_change": _money(trend_row.percent_change),
                        "trend_strength": trend_row.trend_strength,
                    },
                    evidence_rows=base_evidence,
                    spread_score=spread_score,
                    trend_score=trend_score,
                    urgency_score=max(0.55, urgency_score),
                    scarcity_score=scarcity_score,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if trend_row is not None and trend_row.trend_direction == "down" and abs(float(trend_row.percent_change)) >= 10.0:
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"rapid_decline_candidate|{row.inventory_copy_id}",
                    recommendation_type="rapid_decline_candidate",
                    title=f"{row.title} #{row.issue_number} is declining rapidly",
                    description="The latest internal market trend snapshot shows meaningful downward movement that warrants review.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "monitor_decline",
                        "percent_change": _money(trend_row.percent_change),
                        "trend_strength": trend_row.trend_strength,
                    },
                    evidence_rows=base_evidence,
                    spread_score=decline_spread_score,
                    trend_score=trend_score,
                    urgency_score=max(0.65, urgency_score),
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if (
                row.grade_status == "raw"
                and effective_fmv is not None
                and effective_fmv >= Decimal("25.00")
                and ((market_fmv_row is not None and market_fmv_row.comp_count >= 3) or trend_score >= 0.55)
            ):
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"grade_candidate|{row.inventory_copy_id}",
                    recommendation_type="grade_candidate",
                    title=f"{row.title} #{row.issue_number} may be a grading candidate",
                    description="The copy is raw and backed by enough internal value evidence to justify manual grading review.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "review_for_grading",
                        "effective_fmv": _money(effective_fmv),
                        "grade_status": row.grade_status,
                    },
                    evidence_rows=base_evidence,
                    spread_score=max(spread_score, 0.35),
                    trend_score=trend_score,
                    urgency_score=0.45,
                    scarcity_score=scarcity_score,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if trend_row is not None and trend_row.trend_direction == "up" and spread_score >= 0.1 and row.hold_status == "hold":
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"hold_candidate|{row.inventory_copy_id}",
                    recommendation_type="hold_candidate",
                    title=f"{row.title} #{row.issue_number} looks like a hold candidate",
                    description="Positive internal trend momentum suggests this copy may benefit from continued hold rather than immediate action.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "hold_and_monitor",
                        "trend_direction": trend_row.trend_direction,
                        "trend_strength": trend_row.trend_strength,
                    },
                    evidence_rows=base_evidence,
                    spread_score=spread_score,
                    trend_score=trend_score,
                    urgency_score=0.35,
                    scarcity_score=scarcity_score,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if age_days is not None and age_days >= 90 and (
                (trend_row is not None and trend_row.trend_direction == "down")
                or upside_ratio >= 0.5
            ):
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"sell_candidate|{row.inventory_copy_id}",
                    recommendation_type="sell_candidate",
                    title=f"{row.title} #{row.issue_number} looks like a sell candidate",
                    description="The copy has aged in inventory long enough that internal valuation and timing signals now justify a manual sell review.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "review_for_sale",
                        "age_days": age_days,
                        "effective_fmv": _money(effective_fmv),
                    },
                    evidence_rows=base_evidence,
                    spread_score=max(spread_score, decline_spread_score),
                    trend_score=trend_score,
                    urgency_score=max(urgency_score, 0.75),
                    scarcity_score=scarcity_score,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if (
                "upcoming_preorder" in arrival_classifications
                or "releases_this_week" in arrival_classifications
                or (trend_row is not None and trend_row.trend_direction == "up" and trend_score >= 0.45)
            ):
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"watch_candidate|{row.inventory_copy_id}",
                    recommendation_type="watch_candidate",
                    title=f"{row.title} #{row.issue_number} should stay on the watch list",
                    description="Internal timing or trend signals suggest this copy should remain on an active watch list for a human follow-up.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=f"{row.title} #{row.issue_number}",
                    recommendation_payload_json={
                        "candidate_action": "watch_item",
                        "arrival_classifications": sorted(arrival_classifications),
                    },
                    evidence_rows=base_evidence,
                    spread_score=max(spread_score, 0.1 if arrival_classifications else 0.0),
                    trend_score=trend_score,
                    urgency_score=max(0.4, urgency_score if arrival_classifications else 0.2),
                    scarcity_score=scarcity_score,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

        summary = {
            "owner_user_id": owner_user_id,
            "inventory_copy_count": len(inventory_rows),
            "recommendation_count": len(recommendations),
            "recommendations_by_type": dict(sorted(Counter(recommendation_types).items())),
        }
        completed_snapshot = complete_snapshot(session, snapshot_id=snapshot_id, summary_json=summary)
        complete_execution(
            session,
            execution_id=agent_execution.execution.id,
            event_payload_json={
                "snapshot_id": snapshot_id,
                "recommendation_count": len(recommendations),
                "research_type": RESEARCH_TYPE,
            },
        )
        return IntelligenceRunResponse(snapshot=completed_snapshot, recommendations=recommendations)
    except Exception as exc:
        if snapshot_id is not None:
            fail_snapshot(
                session,
                snapshot_id=snapshot_id,
                summary_json={"error": str(exc), "research_type": RESEARCH_TYPE},
            )
        fail_execution(
            session,
            execution_id=agent_execution.execution.id,
            event_payload_json={
                "snapshot_id": snapshot_id,
                "research_type": RESEARCH_TYPE,
                "error": str(exc),
            },
        )
        raise
