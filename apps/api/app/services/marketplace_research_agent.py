from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    AgentDefinition,
    CatalogIssue,
    ComicIssue,
    DraftImport,
    InventoryCopy,
    InventoryFmvSnapshot,
    MarketFmvSnapshot,
    MarketTrendSnapshot,
    User,
)
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.schemas.research_agent import ResearchSnapshotDetail
from app.services.agent_execution import complete_execution, fail_execution, start_execution
from app.services.order_arrival_intelligence import compute_order_arrival_intelligence
from app.services.research_agent_base import (
    add_evidence,
    add_finding,
    complete_snapshot,
    create_snapshot,
    fail_snapshot,
    get_snapshot_detail,
)

AGENT_CODE = "marketplace_research_agent"
RESEARCH_TYPE = "marketplace"


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
        raise RuntimeError("Marketplace research agent is not registered.")
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


def _draft_import_scope(session: Session, *, owner_user_id: int) -> tuple[int, list[DraftImport]]:
    rows = session.exec(
        select(DraftImport)
        .where(DraftImport.user_id == owner_user_id)
        .order_by(DraftImport.created_at.asc(), DraftImport.id.asc())
    ).all()
    return len(rows), rows[:5]


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


def _persist_finding(
    session: Session,
    *,
    snapshot_id: int,
    finding_code: str,
    finding_type: str,
    title: str,
    description: str,
    confidence_score: float,
    priority_score: float,
    recommendation_json: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
) -> str:
    finding = add_finding(
        session,
        snapshot_id=snapshot_id,
        finding_code=finding_code,
        finding_type=finding_type,
        title=title,
        description=description,
        confidence_score=confidence_score,
        priority_score=priority_score,
        recommendation_json=recommendation_json,
    )
    for evidence in evidence_rows:
        add_evidence(
            session,
            finding_id=finding.id,
            evidence_type=str(evidence["evidence_type"]),
            source_name=str(evidence["source_name"]),
            source_url=evidence.get("source_url"),
            source_payload_json=dict(evidence.get("source_payload_json") or {}),
            evidence_score=float(evidence.get("evidence_score") or 0.0),
        )
    return finding.finding_type


def run_marketplace_research_agent(session: Session, *, current_user: User) -> ResearchSnapshotDetail:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    agent_execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="research_agent:marketplace",
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
        arrival_response, _ = compute_order_arrival_intelligence(session, current_user=current_user)
        arrival_by_inventory: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for item in arrival_response.items:
            arrival_by_inventory[item.inventory_copy_id].append(
                {
                    "classification": item.classification,
                    "evidence_json": item.evidence_json,
                }
            )
        draft_import_total, draft_import_rows = _draft_import_scope(session, owner_user_id=owner_user_id)
        snapshot = create_snapshot(
            session,
            agent_execution_id=agent_execution.execution.id,
            agent_code=AGENT_CODE,
            research_type=RESEARCH_TYPE,
            input_scope_json={
                "owner_user_id": owner_user_id,
                "inventory_copy_count": len(inventory_rows),
                "draft_import_count": draft_import_total,
                "arrival_intel_item_count": arrival_response.total_count,
            },
        )
        snapshot_id = snapshot.id
        finding_types: list[str] = []
        now = utc_now()

        for row in inventory_rows:
            effective_fmv = row.current_fmv
            inventory_fmv_row = latest_inventory_fmv.get(row.inventory_copy_id)
            if effective_fmv is None and inventory_fmv_row is not None:
                effective_fmv = inventory_fmv_row.new_fmv
            market_fmv_row = _find_market_fmv(row, by_key=market_fmv_by_key, by_issue=market_fmv_by_issue)
            trend_row = _find_market_trend(row, by_key=market_trend_by_key, by_issue=market_trend_by_issue)
            arrival_bits = arrival_by_inventory.get(row.inventory_copy_id, [])
            received_at = _as_utc(row.received_at)
            age_days = (now - received_at).days if received_at is not None else None

            base_evidence = [
                {
                    "evidence_type": "inventory_projection",
                    "source_name": "inventory_copy",
                    "source_payload_json": {
                        "inventory_copy_id": row.inventory_copy_id,
                        "title": row.title,
                        "publisher": row.publisher,
                        "issue_number": row.issue_number,
                        "acquisition_cost": _money(row.acquisition_cost),
                        "current_fmv": _money(row.current_fmv),
                        "grade_status": row.grade_status,
                        "hold_status": row.hold_status,
                        "order_status": row.order_status,
                        "received_at": None if received_at is None else received_at.isoformat(),
                    },
                    "evidence_score": 1.0,
                }
            ]
            if inventory_fmv_row is not None:
                base_evidence.append(
                    {
                        "evidence_type": "inventory_fmv_snapshot",
                        "source_name": "inventory_fmv_snapshot",
                        "source_payload_json": {
                            "inventory_copy_id": inventory_fmv_row.inventory_copy_id,
                            "previous_fmv": _money(inventory_fmv_row.previous_fmv),
                            "new_fmv": _money(inventory_fmv_row.new_fmv),
                            "source": inventory_fmv_row.source,
                            "changed_at": inventory_fmv_row.changed_at.isoformat(),
                        },
                        "evidence_score": 0.92,
                    }
                )
            if market_fmv_row is not None:
                base_evidence.append(
                    {
                        "evidence_type": "market_fmv_snapshot",
                        "source_name": "market_fmv_snapshot",
                        "source_payload_json": {
                            "snapshot_id": market_fmv_row.id,
                            "snapshot_scope": market_fmv_row.snapshot_scope,
                            "snapshot_date": market_fmv_row.snapshot_date.isoformat(),
                            "estimated_fmv": _money(market_fmv_row.estimated_fmv),
                            "comp_count": market_fmv_row.comp_count,
                            "valuation_method": market_fmv_row.valuation_method,
                            "stale_data": market_fmv_row.stale_data,
                            "evidence_json": market_fmv_row.evidence_json,
                        },
                        "evidence_score": 0.9,
                    }
                )
            if trend_row is not None:
                base_evidence.append(
                    {
                        "evidence_type": "market_trend_snapshot",
                        "source_name": "market_trend_snapshot",
                        "source_payload_json": {
                            "trend_snapshot_id": trend_row.id,
                            "trend_window": trend_row.trend_window,
                            "trend_direction": trend_row.trend_direction,
                            "trend_strength": trend_row.trend_strength,
                            "comp_count": trend_row.comp_count,
                            "percent_change": _money(trend_row.percent_change),
                            "stale_data": trend_row.stale_data,
                            "evidence_json": trend_row.evidence_json,
                        },
                        "evidence_score": 0.86,
                    }
                )
            for arrival in arrival_bits:
                base_evidence.append(
                    {
                        "evidence_type": "order_arrival_intelligence",
                        "source_name": "order_arrival_intelligence",
                        "source_payload_json": {
                            "inventory_copy_id": row.inventory_copy_id,
                            "classification": arrival["classification"],
                            "evidence_json": arrival["evidence_json"],
                        },
                        "evidence_score": 0.8,
                    }
                )

            if effective_fmv is None and market_fmv_row is None and trend_row is None:
                finding_types.append(
                    _persist_finding(
                        session,
                        snapshot_id=snapshot_id,
                        finding_code=f"marketplace_research_needed|inventory_copy|{row.inventory_copy_id}",
                        finding_type="marketplace_research_needed",
                        title=f"{row.title} #{row.issue_number} needs market research coverage",
                        description=(
                            "This inventory copy has no current FMV, no matching market FMV snapshot, and no trend snapshot."
                        ),
                        confidence_score=0.98,
                        priority_score=0.95,
                        recommendation_json={
                            "candidate_action": "collect_internal_market_context",
                            "inventory_copy_id": row.inventory_copy_id,
                        },
                        evidence_rows=base_evidence,
                    )
                )

            if effective_fmv is not None and received_at is not None and effective_fmv >= (row.acquisition_cost * Decimal("1.50")):
                finding_types.append(
                    _persist_finding(
                        session,
                        snapshot_id=snapshot_id,
                        finding_code=f"possible_underpriced_item|inventory_copy|{row.inventory_copy_id}",
                        finding_type="possible_underpriced_item",
                        title=f"{row.title} #{row.issue_number} has upside versus cost basis",
                        description=(
                            "The stored FMV is materially above acquisition cost, making this copy a strong review candidate."
                        ),
                        confidence_score=0.88,
                        priority_score=0.84,
                        recommendation_json={
                            "candidate_action": "review_listing_or_hold_strategy",
                            "inventory_copy_id": row.inventory_copy_id,
                            "acquisition_cost": _money(row.acquisition_cost),
                            "effective_fmv": _money(effective_fmv),
                        },
                        evidence_rows=base_evidence,
                    )
                )

            if effective_fmv is not None and effective_fmv <= (row.acquisition_cost * Decimal("0.80")):
                finding_types.append(
                    _persist_finding(
                        session,
                        snapshot_id=snapshot_id,
                        finding_code=f"possible_overpriced_item|inventory_copy|{row.inventory_copy_id}",
                        finding_type="possible_overpriced_item",
                        title=f"{row.title} #{row.issue_number} is below cost basis",
                        description=(
                            "The stored FMV is materially below acquisition cost, so the copy should be reviewed before any pricing decision."
                        ),
                        confidence_score=0.84,
                        priority_score=0.79,
                        recommendation_json={
                            "candidate_action": "review_market_position",
                            "inventory_copy_id": row.inventory_copy_id,
                            "acquisition_cost": _money(row.acquisition_cost),
                            "effective_fmv": _money(effective_fmv),
                        },
                        evidence_rows=base_evidence,
                    )
                )

            if age_days is not None and age_days >= 90 and row.order_status == "received" and row.hold_status == "hold":
                finding_types.append(
                    _persist_finding(
                        session,
                        snapshot_id=snapshot_id,
                        finding_code=f"stale_inventory_candidate|inventory_copy|{row.inventory_copy_id}",
                        finding_type="stale_inventory_candidate",
                        title=f"{row.title} #{row.issue_number} has been sitting in inventory",
                        description="This received copy has remained on hold long enough to merit a fresh review.",
                        confidence_score=0.83,
                        priority_score=0.76,
                        recommendation_json={
                            "candidate_action": "review_stale_inventory",
                            "inventory_copy_id": row.inventory_copy_id,
                            "age_days": age_days,
                        },
                        evidence_rows=base_evidence,
                    )
                )

            if (
                effective_fmv is not None
                and row.grade_status == "raw"
                and effective_fmv >= Decimal("25.00")
                and (
                    (trend_row is not None and trend_row.trend_direction == "up")
                    or (market_fmv_row is not None and market_fmv_row.comp_count >= 3)
                )
            ):
                finding_types.append(
                    _persist_finding(
                        session,
                        snapshot_id=snapshot_id,
                        finding_code=f"grading_candidate|inventory_copy|{row.inventory_copy_id}",
                        finding_type="grading_candidate",
                        title=f"{row.title} #{row.issue_number} may justify grading review",
                        description=(
                            "The copy is raw, has meaningful stored value, and is backed by internal market strength signals."
                        ),
                        confidence_score=0.82,
                        priority_score=0.8,
                        recommendation_json={
                            "candidate_action": "review_for_grading",
                            "inventory_copy_id": row.inventory_copy_id,
                            "effective_fmv": _money(effective_fmv),
                        },
                        evidence_rows=base_evidence,
                    )
                )

            if trend_row is not None and trend_row.trend_direction == "up" and trend_row.trend_strength in {"high", "very_high"}:
                finding_types.append(
                    _persist_finding(
                        session,
                        snapshot_id=snapshot_id,
                        finding_code=f"high_interest_series|inventory_copy|{row.inventory_copy_id}",
                        finding_type="high_interest_series",
                        title=f"{row.title} #{row.issue_number} shows strong internal market momentum",
                        description=(
                            "The latest internal trend snapshot shows upward direction with strong trend strength."
                        ),
                        confidence_score=0.86,
                        priority_score=0.78,
                        recommendation_json={
                            "candidate_action": "add_to_watchlist",
                            "inventory_copy_id": row.inventory_copy_id,
                            "trend_window": trend_row.trend_window,
                            "percent_change": _money(trend_row.percent_change),
                        },
                        evidence_rows=base_evidence,
                    )
                )

        for draft_import in draft_import_rows:
            finding_types.append(
                _persist_finding(
                    session,
                    snapshot_id=snapshot_id,
                    finding_code=f"marketplace_research_needed|draft_import|{draft_import.id}",
                    finding_type="marketplace_research_needed",
                    title="Draft import still needs market-ready review",
                    description=(
                        "A draft import remains unconfirmed, so its intake data should be reviewed before it feeds future research or listing flows."
                    ),
                    confidence_score=0.74,
                    priority_score=0.58,
                    recommendation_json={
                        "candidate_action": "review_draft_import",
                        "draft_import_id": draft_import.id,
                        "status": draft_import.status,
                    },
                    evidence_rows=[
                        {
                            "evidence_type": "draft_import",
                            "source_name": "draft_import",
                            "source_payload_json": {
                                "draft_import_id": draft_import.id,
                                "status": draft_import.status,
                                "confidence_score": _money(draft_import.confidence_score),
                                "linked_order_id": draft_import.linked_order_id,
                                "created_at": draft_import.created_at.isoformat(),
                            },
                            "evidence_score": 0.72,
                        }
                    ],
                )
            )

        summary = {
            "owner_user_id": owner_user_id,
            "inventory_copy_count": len(inventory_rows),
            "draft_import_count": draft_import_total,
            "finding_count": len(finding_types),
            "findings_by_type": dict(sorted(Counter(finding_types).items())),
        }
        complete_snapshot(session, snapshot_id=snapshot_id, summary_json=summary)
        complete_execution(
            session,
            execution_id=agent_execution.execution.id,
            event_payload_json={
                "snapshot_id": snapshot_id,
                "research_type": RESEARCH_TYPE,
                "finding_count": len(finding_types),
            },
        )
        return get_snapshot_detail(session, snapshot_id=snapshot_id)
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
