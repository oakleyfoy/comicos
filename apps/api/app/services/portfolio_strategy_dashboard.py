"""P38-07 deterministic portfolio strategy dashboard aggregation."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    AcquisitionPrioritySnapshot,
    ConcentrationRiskSnapshot,
    DuplicateCluster,
    DuplicateConsolidationRecommendation,
    GradingCandidate,
    InventoryCopy,
    Portfolio,
    PortfolioAllocationSnapshot,
    PortfolioLiquiditySnapshot,
    PortfolioLifecycleEvent,
    PortfolioRecommendation,
    PortfolioStrategyDashboardAlert,
    PortfolioStrategyDashboardFeedEvent,
    PortfolioStrategyDashboardMetric,
    PortfolioStrategyDashboardSnapshot,
    SaleRecord,
)
from app.schemas.portfolio_strategy_dashboard import (
    PortfolioStrategyDashboardAlertListResponse,
    PortfolioStrategyDashboardAlertRead,
    PortfolioStrategyDashboardFeedEventRead,
    PortfolioStrategyDashboardFeedListResponse,
    PortfolioStrategyDashboardGeneratePayload,
    PortfolioStrategyDashboardGenerateResponse,
    PortfolioStrategyDashboardGetResponse,
    PortfolioStrategyDashboardMetricListResponse,
    PortfolioStrategyDashboardMetricRead,
    PortfolioStrategyDashboardSnapshotRead,
)

AGGREGATION_VERSION = "p38-07:v1"
MONEY_QUANT = Decimal("0.01")
SCORE_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
ALL_INVENTORY_SCOPE = "ALL_INVENTORY"
ACTIVE_GRADING_STATUSES = {"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION", "SUBMITTED"}
SOURCE_ENGINE_VERSIONS = {
    "portfolio_registry": "p38-01:v1",
    "duplicate_intelligence": "p38-02:v1",
    "portfolio_liquidity": "p38-03:v1",
    "portfolio_recommendations": "p38-04:v1",
    "concentration_risk": "p38-05:v1",
    "acquisition_priority": "p38-06:v1",
    "portfolio_strategy_dashboard": AGGREGATION_VERSION,
}
logger = logging.getLogger(__name__)


def clamp_portfolio_strategy_dashboard_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _score(value: Any | None) -> Decimal:
    return _decimal(value).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _percent(numerator: int, denominator: int) -> Decimal | None:
    if denominator <= 0:
        return None
    return (Decimal(numerator) * Decimal("100") / Decimal(denominator)).quantize(
        SCORE_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _avg_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return (sum(values, ZERO) / Decimal(len(values))).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT if value.as_tuple().exponent <= -2 else SCORE_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sort_timestamp_desc_key(value: datetime) -> int:
    normalized = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return -int(normalized.strftime("%Y%m%d%H%M%S%f"))


def _sort_alert_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _sort_timestamp_desc_key(row["created_at"]),
            str(row["alert_type"]),
            str(row["severity"]),
            int(row["source_portfolio_id"] or 0),
            int(row["source_inventory_item_id"] or 0),
            int(row["source_snapshot_id"] or 0),
            str(row["message"]),
        ),
    )


def _sort_feed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _sort_timestamp_desc_key(row["created_at"]),
            str(row["event_type"]),
            int(row["source_id"] or 0),
            str(row["deterministic_key"]),
            str(row["summary"]),
        ),
    )


def _snapshot_read(row: PortfolioStrategyDashboardSnapshot) -> PortfolioStrategyDashboardSnapshotRead:
    return PortfolioStrategyDashboardSnapshotRead.model_validate(row, from_attributes=True)


def latest_snapshot_for_owner(session: Session, *, owner_user_id: int) -> PortfolioStrategyDashboardSnapshot | None:
    return session.exec(
        select(PortfolioStrategyDashboardSnapshot)
        .where(PortfolioStrategyDashboardSnapshot.owner_user_id == owner_user_id)
        .order_by(col(PortfolioStrategyDashboardSnapshot.snapshot_date).desc())
        .order_by(col(PortfolioStrategyDashboardSnapshot.created_at).desc())
        .order_by(col(PortfolioStrategyDashboardSnapshot.id).desc())
    ).first()


def latest_snapshot_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
) -> PortfolioStrategyDashboardSnapshot | None:
    stmt = select(PortfolioStrategyDashboardSnapshot).order_by(
        col(PortfolioStrategyDashboardSnapshot.snapshot_date).desc(),
        col(PortfolioStrategyDashboardSnapshot.created_at).desc(),
        col(PortfolioStrategyDashboardSnapshot.id).desc(),
    )
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioStrategyDashboardSnapshot.owner_user_id == owner_user_id)
    return session.exec(stmt).first()


def get_dashboard_owner(session: Session, *, owner_user_id: int) -> PortfolioStrategyDashboardGetResponse:
    row = latest_snapshot_for_owner(session, owner_user_id=owner_user_id)
    return PortfolioStrategyDashboardGetResponse(snapshot=_snapshot_read(row) if row else None)


def get_dashboard_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
) -> PortfolioStrategyDashboardGetResponse:
    row = latest_snapshot_ops(session, owner_user_id=owner_user_id)
    return PortfolioStrategyDashboardGetResponse(snapshot=_snapshot_read(row) if row else None)


def _latest_all_inventory_allocation(session: Session, *, owner_user_id: int) -> PortfolioAllocationSnapshot | None:
    return session.exec(
        select(PortfolioAllocationSnapshot)
        .where(
            PortfolioAllocationSnapshot.owner_user_id == owner_user_id,
            PortfolioAllocationSnapshot.generation_scope_key == ALL_INVENTORY_SCOPE,
        )
        .order_by(col(PortfolioAllocationSnapshot.snapshot_date).desc(), col(PortfolioAllocationSnapshot.id).desc())
    ).first()


def _latest_all_inventory_liquidity(session: Session, *, owner_user_id: int) -> PortfolioLiquiditySnapshot | None:
    return session.exec(
        select(PortfolioLiquiditySnapshot)
        .where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.generation_scope_key == ALL_INVENTORY_SCOPE,
        )
        .order_by(col(PortfolioLiquiditySnapshot.snapshot_date).desc(), col(PortfolioLiquiditySnapshot.id).desc())
    ).first()


def _latest_duplicate_batch(session: Session, *, owner_user_id: int) -> list[DuplicateCluster]:
    row = session.exec(
        select(DuplicateCluster)
        .where(DuplicateCluster.owner_user_id == owner_user_id)
        .order_by(col(DuplicateCluster.snapshot_date).desc(), col(DuplicateCluster.id).desc())
    ).first()
    if row is None:
        return []
    return list(
        session.exec(
            select(DuplicateCluster)
            .where(
                DuplicateCluster.owner_user_id == owner_user_id,
                DuplicateCluster.generation_batch_checksum == row.generation_batch_checksum,
            )
            .order_by(col(DuplicateCluster.duplication_status).asc(), col(DuplicateCluster.cluster_key).asc(), col(DuplicateCluster.id).asc())
        ).all(),
    )


def _latest_current_recommendations(session: Session, *, owner_user_id: int) -> list[PortfolioRecommendation]:
    return list(
        session.exec(
            select(PortfolioRecommendation)
            .where(
                PortfolioRecommendation.owner_user_id == owner_user_id,
                PortfolioRecommendation.recommendation_status == "ACTIVE",
            )
            .order_by(
                col(PortfolioRecommendation.snapshot_date).desc(),
                col(PortfolioRecommendation.recommendation_action).asc(),
                col(PortfolioRecommendation.inventory_item_id).asc(),
                col(PortfolioRecommendation.id).asc(),
            )
        ).all(),
    )


def _latest_signature_rows(
    rows: list[Any],
    *,
    snapshot_attr: str = "snapshot_date",
    replay_attr: str = "replay_key",
) -> list[Any]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: (getattr(row, snapshot_attr), getattr(row, "created_at"), int(row.id or 0)), reverse=True)
    latest = ordered[0]
    snapshot_date = getattr(latest, snapshot_attr)
    replay_key = getattr(latest, replay_attr, "")
    return sorted(
        [
            row
            for row in rows
            if getattr(row, snapshot_attr) == snapshot_date and getattr(row, replay_attr, "") == replay_key
        ],
        key=lambda row: (
            getattr(row, "created_at"),
            str(getattr(row, "acquisition_category", getattr(row, "concentration_type", ""))),
            str(getattr(row, "acquisition_priority", getattr(row, "concentration_key", ""))),
            int(row.id or 0),
        ),
    )


def _latest_concentration_rows(session: Session, *, owner_user_id: int) -> list[ConcentrationRiskSnapshot]:
    rows = list(
        session.exec(
            select(ConcentrationRiskSnapshot)
            .where(
                ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
                col(ConcentrationRiskSnapshot.portfolio_id).is_(None),
            )
            .order_by(
                col(ConcentrationRiskSnapshot.snapshot_date).desc(),
                col(ConcentrationRiskSnapshot.id).desc(),
            )
        ).all(),
    )
    return [row for row in _latest_signature_rows(rows) if row.portfolio_id is None]


def _latest_acquisition_rows(session: Session, *, owner_user_id: int) -> list[AcquisitionPrioritySnapshot]:
    rows = list(
        session.exec(
            select(AcquisitionPrioritySnapshot)
            .where(AcquisitionPrioritySnapshot.owner_user_id == owner_user_id)
            .order_by(
                col(AcquisitionPrioritySnapshot.snapshot_date).desc(),
                col(AcquisitionPrioritySnapshot.id).desc(),
            )
        ).all(),
    )
    return _latest_signature_rows(rows)


def _fallback_inventory_rollup(session: Session, *, owner_user_id: int) -> tuple[int, Decimal | None, Decimal | None]:
    inventory_rows = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .order_by(col(InventoryCopy.id).asc())
        ).all(),
    )
    if not inventory_rows:
        return 0, None, None
    total_value = _money(sum((_decimal(row.current_fmv) for row in inventory_rows), ZERO))
    total_cost = _money(sum((_decimal(row.acquisition_cost) for row in inventory_rows), ZERO))
    return len(inventory_rows), total_value if total_value > ZERO else None, total_cost if total_cost > ZERO else None


def _compute_payload(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date,
) -> dict[str, Any]:
    portfolios = list(
        session.exec(
            select(Portfolio)
            .where(Portfolio.owner_user_id == owner_user_id, Portfolio.archived_at.is_(None))
            .order_by(col(Portfolio.created_at).asc(), col(Portfolio.id).asc())
        ).all(),
    )
    portfolio_count = len(portfolios)

    alloc = _latest_all_inventory_allocation(session, owner_user_id=owner_user_id)
    if alloc is None:
        fallback_count, fallback_value, fallback_cost = _fallback_inventory_rollup(session, owner_user_id=owner_user_id)
        total_portfolio_value = fallback_value
        total_cost_basis = fallback_cost
        total_realized_sales = _money(
            session.exec(
                select(func.coalesce(func.sum(col(SaleRecord.net_proceeds_amount)), ZERO)).where(
                    SaleRecord.owner_user_id == owner_user_id,
                    SaleRecord.status == "RECORDED",
                )
            ).one(),
        )
        grading_candidate_count = int(
            session.exec(
                select(func.count(col(GradingCandidate.id))).where(
                    GradingCandidate.owner_user_id == owner_user_id,
                    GradingCandidate.archived_at.is_(None),
                    col(GradingCandidate.status).in_(tuple(ACTIVE_GRADING_STATUSES)),
                )
            ).one()
            or 0,
        )
        inventory_count = fallback_count
    else:
        total_portfolio_value = _money(alloc.total_fmv_amount) if alloc.total_fmv_amount is not None else None
        total_cost_basis = _money(alloc.total_cost_basis_amount) if alloc.total_cost_basis_amount is not None else None
        total_realized_sales = _money(alloc.total_realized_sales_amount) if alloc.total_realized_sales_amount is not None else None
        grading_candidate_count = int(alloc.grading_candidate_count or 0)
        inventory_count = int(alloc.total_item_count or 0)

    liquidity = _latest_all_inventory_liquidity(session, owner_user_id=owner_user_id)
    liquidity_efficiency_score = _score(liquidity.liquidity_efficiency_score) if liquidity and liquidity.liquidity_efficiency_score is not None else None
    dead_capital_estimate = _money(liquidity.dead_capital_estimate) if liquidity and liquidity.dead_capital_estimate is not None else None
    liquid_inventory_percentage = None
    illiquid_inventory_percentage = None
    if liquidity is not None:
        liquid_inventory_percentage = _percent(
            int(liquidity.high_liquidity_count or 0) + int(liquidity.medium_liquidity_count or 0),
            int(liquidity.high_liquidity_count or 0)
            + int(liquidity.medium_liquidity_count or 0)
            + int(liquidity.low_liquidity_count or 0)
            + int(liquidity.illiquid_count or 0),
        )
        illiquid_inventory_percentage = _percent(
            int(liquidity.low_liquidity_count or 0) + int(liquidity.illiquid_count or 0),
            int(liquidity.high_liquidity_count or 0)
            + int(liquidity.medium_liquidity_count or 0)
            + int(liquidity.low_liquidity_count or 0)
            + int(liquidity.illiquid_count or 0),
        )

    duplicate_clusters = _latest_duplicate_batch(session, owner_user_id=owner_user_id)
    duplicate_cluster_count = len(duplicate_clusters)
    duplicate_warning_clusters = [
        row for row in duplicate_clusters if str(row.duplication_status) in {"REDUNDANT", "OVEREXPOSED"}
    ]

    recommendations = _latest_current_recommendations(session, owner_user_id=owner_user_id)
    recommendation_rows = _latest_signature_rows(recommendations, replay_attr="replay_key")
    hold_count = sum(1 for row in recommendation_rows if str(row.recommendation_action) == "HOLD")
    sell_count = sum(
        1 for row in recommendation_rows if str(row.recommendation_action) in {"SELL", "GRADE_THEN_SELL"}
    )
    reduce_exposure_count = sum(
        1 for row in recommendation_rows if str(row.recommendation_action) in {"REDUCE_EXPOSURE", "CONSOLIDATE"}
    )
    high_risk_holds = [
        row
        for row in recommendation_rows
        if str(row.recommendation_action) == "HOLD" and str(row.risk_level) == "HIGH"
    ]

    concentration_rows = _latest_concentration_rows(session, owner_user_id=owner_user_id)
    diversification_score = _avg_decimal(
        [_score(row.diversification_score) for row in concentration_rows if row.diversification_score is not None],
    )
    concentration_risk_score = _avg_decimal(
        [_score(row.concentration_score) for row in concentration_rows if row.concentration_score is not None],
    )
    overexposed_rows = [
        row for row in concentration_rows if str(row.exposure_status) in {"OVEREXPOSED", "CRITICAL"}
    ]

    acquisition_rows = _latest_acquisition_rows(session, owner_user_id=owner_user_id)
    acquisition_opportunity_count = len(acquisition_rows)
    elite_acquisition_count = sum(1 for row in acquisition_rows if str(row.acquisition_priority) == "ELITE")
    acquisition_gap_rows = [
        row
        for row in acquisition_rows
        if str(row.acquisition_category) in {"PORTFOLIO_GAP", "LOW_EXPOSURE_CATEGORY", "DIVERSIFICATION"}
        and str(row.acquisition_priority) in {"HIGH", "ELITE"}
    ]

    metrics: list[dict[str, Any]] = [
        {"metric_key": "aggregation_version", "metric_value_text": AGGREGATION_VERSION},
        {"metric_key": "portfolio_count", "metric_value_decimal": Decimal(portfolio_count)},
        {"metric_key": "inventory_count", "metric_value_decimal": Decimal(inventory_count)},
        {"metric_key": "portfolio_names", "metric_value_text": ", ".join(str(row.name) for row in portfolios[:10]) or None},
        {"metric_key": "overexposed_categories", "metric_value_decimal": Decimal(len(overexposed_rows))},
        {
            "metric_key": "critical_concentration_count",
            "metric_value_decimal": Decimal(sum(1 for row in concentration_rows if str(row.exposure_status) == "CRITICAL")),
        },
        {"metric_key": "duplicate_cluster_count", "metric_value_decimal": Decimal(duplicate_cluster_count)},
        {"metric_key": "duplicate_warning_clusters", "metric_value_decimal": Decimal(len(duplicate_warning_clusters))},
        {"metric_key": "hold_recommendation_count", "metric_value_decimal": Decimal(hold_count)},
        {"metric_key": "sell_recommendation_count", "metric_value_decimal": Decimal(sell_count)},
        {"metric_key": "reduce_exposure_count", "metric_value_decimal": Decimal(reduce_exposure_count)},
        {
            "metric_key": "capital_release_estimate",
            "metric_value_decimal": _money(
                sum(
                    (
                        _decimal(row.estimated_capital_release)
                        for row in recommendation_rows
                        if row.estimated_capital_release is not None
                    ),
                    ZERO,
                ),
            )
            if any(row.estimated_capital_release is not None for row in recommendation_rows)
            else None,
        },
        {
            "metric_key": "recommendation_efficiency_gain",
            "metric_value_decimal": _score(
                sum(
                    (
                        _decimal(row.estimated_portfolio_efficiency_gain)
                        for row in recommendation_rows
                        if row.estimated_portfolio_efficiency_gain is not None
                    ),
                    ZERO,
                ),
            )
            if any(row.estimated_portfolio_efficiency_gain is not None for row in recommendation_rows)
            else None,
        },
        {"metric_key": "acquisition_opportunity_count", "metric_value_decimal": Decimal(acquisition_opportunity_count)},
        {"metric_key": "elite_acquisition_count", "metric_value_decimal": Decimal(elite_acquisition_count)},
        {
            "metric_key": "diversification_acquisitions",
            "metric_value_decimal": Decimal(sum(1 for row in acquisition_rows if str(row.acquisition_category) == "DIVERSIFICATION")),
        },
        {
            "metric_key": "liquidity_improvement_acquisitions",
            "metric_value_decimal": Decimal(sum(1 for row in acquisition_rows if str(row.acquisition_category) == "LIQUIDITY_IMPROVEMENT")),
        },
        {
            "metric_key": "grading_opportunity_acquisitions",
            "metric_value_decimal": Decimal(sum(1 for row in acquisition_rows if str(row.acquisition_category) == "GRADING_OPPORTUNITY")),
        },
        {
            "metric_key": "liquidity_balance_status",
            "metric_value_text": str(liquidity.liquidity_balance_status) if liquidity is not None else None,
        },
        {
            "metric_key": "duplicate_top_clusters",
            "metric_value_text": "Latest duplicate posture",
            "metric_metadata_json": {
                "clusters": [
                    {
                        "cluster_id": int(row.id or 0),
                        "cluster_key": str(row.cluster_key),
                        "duplication_status": str(row.duplication_status),
                        "total_item_count": int(row.total_item_count or 0),
                        "total_fmv_amount": row.total_fmv_amount,
                    }
                    for row in duplicate_warning_clusters[:5]
                ],
            },
        },
        {
            "metric_key": "acquisition_focus_rows",
            "metric_value_text": "Highest priority acquisition gaps",
            "metric_metadata_json": {
                "rows": [
                    {
                        "snapshot_id": int(row.id or 0),
                        "issue_id": row.canonical_comic_issue_id,
                        "acquisition_category": str(row.acquisition_category),
                        "acquisition_priority": str(row.acquisition_priority),
                        "diversification_impact": row.diversification_impact,
                        "liquidity_impact": row.liquidity_impact,
                    }
                    for row in acquisition_gap_rows[:5]
                ],
            },
        },
        {
            "metric_key": "source_engine_versions",
            "metric_value_text": "Deterministic upstream ledger versions",
            "metric_metadata_json": SOURCE_ENGINE_VERSIONS,
        },
        {
            "metric_key": "source_dependency_graph",
            "metric_value_text": "Latest upstream snapshot lineage",
            "metric_metadata_json": {
                "portfolio_ids": [int(row.id or 0) for row in portfolios],
                "allocation_snapshot_id": int(alloc.id or 0) if alloc is not None else None,
                "allocation_checksum": alloc.checksum if alloc is not None else None,
                "liquidity_snapshot_id": int(liquidity.id or 0) if liquidity is not None else None,
                "liquidity_checksum": liquidity.checksum if liquidity is not None else None,
                "duplicate_cluster_ids": [int(row.id or 0) for row in duplicate_clusters[:10]],
                "duplicate_batch_checksum": duplicate_clusters[0].generation_batch_checksum if duplicate_clusters else None,
                "recommendation_snapshot_ids": [int(row.id or 0) for row in recommendation_rows[:10]],
                "concentration_snapshot_ids": [int(row.id or 0) for row in concentration_rows[:10]],
                "acquisition_snapshot_ids": [int(row.id or 0) for row in acquisition_rows[:10]],
            },
        },
    ]

    alerts: list[dict[str, Any]] = []
    for row in overexposed_rows[:6]:
        alerts.append(
            {
                "alert_type": "OVEREXPOSURE",
                "severity": "critical" if str(row.exposure_status) == "CRITICAL" else "warning",
                "source_portfolio_id": row.portfolio_id,
                "source_inventory_item_id": None,
                "source_snapshot_id": int(row.id or 0),
                "message": f"{row.concentration_type}::{row.concentration_key} is {row.exposure_status.lower()} in the latest concentration batch.",
                "created_at": row.created_at,
            },
        )
    if liquidity is not None and dead_capital_estimate is not None and dead_capital_estimate > ZERO:
        alerts.append(
            {
                "alert_type": "DEAD_CAPITAL",
                "severity": "critical"
                if str(liquidity.liquidity_balance_status) == "CRITICAL"
                else "warning",
                "source_portfolio_id": liquidity.portfolio_id,
                "source_inventory_item_id": None,
                "source_snapshot_id": int(liquidity.id or 0),
                "message": f"Dead capital estimate is {dead_capital_estimate} with balance status {liquidity.liquidity_balance_status}.",
                "created_at": liquidity.created_at,
            },
        )
    if liquidity is not None and str(liquidity.liquidity_balance_status) in {"IMBALANCED", "CRITICAL"}:
        alerts.append(
            {
                "alert_type": "LIQUIDITY_IMBALANCE",
                "severity": "critical" if str(liquidity.liquidity_balance_status) == "CRITICAL" else "warning",
                "source_portfolio_id": liquidity.portfolio_id,
                "source_inventory_item_id": None,
                "source_snapshot_id": int(liquidity.id or 0),
                "message": f"Liquidity posture is {liquidity.liquidity_balance_status.lower()} across the owner-wide portfolio scope.",
                "created_at": liquidity.created_at,
            },
        )
    for row in duplicate_warning_clusters[:5]:
        alerts.append(
            {
                "alert_type": "DUPLICATE_RISK",
                "severity": "critical" if str(row.duplication_status) == "OVEREXPOSED" else "warning",
                "source_portfolio_id": None,
                "source_inventory_item_id": None,
                "source_snapshot_id": int(row.id or 0),
                "message": f"Duplicate cluster {row.cluster_key} is {row.duplication_status.lower()} with {row.total_item_count} copies.",
                "created_at": row.created_at,
            },
        )
    if diversification_score is not None and diversification_score < Decimal("45"):
        alerts.append(
            {
                "alert_type": "CONCENTRATION_CRITICAL",
                "severity": "critical",
                "source_portfolio_id": None,
                "source_inventory_item_id": None,
                "source_snapshot_id": int(concentration_rows[0].id or 0) if concentration_rows else None,
                "message": f"Average diversification score has fallen to {diversification_score}.",
                "created_at": concentration_rows[0].created_at if concentration_rows else datetime.now(timezone.utc),
            },
        )
    elif diversification_score is not None and diversification_score < Decimal("60"):
        alerts.append(
            {
                "alert_type": "WEAK_DIVERSIFICATION",
                "severity": "warning",
                "source_portfolio_id": None,
                "source_inventory_item_id": None,
                "source_snapshot_id": int(concentration_rows[0].id or 0) if concentration_rows else None,
                "message": f"Average diversification score is only {diversification_score}; breadth remains weak.",
                "created_at": concentration_rows[0].created_at if concentration_rows else datetime.now(timezone.utc),
            },
        )
    for row in high_risk_holds[:5]:
        alerts.append(
            {
                "alert_type": "HIGH_RISK_HOLDING",
                "severity": "warning",
                "source_portfolio_id": row.portfolio_id,
                "source_inventory_item_id": row.inventory_item_id,
                "source_snapshot_id": int(row.id or 0),
                "message": f"HOLD recommendation for inventory #{row.inventory_item_id} still carries HIGH risk.",
                "created_at": row.created_at,
            },
        )
    for row in acquisition_gap_rows[:5]:
        alerts.append(
            {
                "alert_type": "ACQUISITION_GAP",
                "severity": "info" if str(row.acquisition_priority) == "HIGH" else "warning",
                "source_portfolio_id": None,
                "source_inventory_item_id": None,
                "source_snapshot_id": int(row.id or 0),
                "message": f"{row.acquisition_category.replace('_', ' ').title()} remains open at {row.acquisition_priority} priority.",
                "created_at": row.created_at,
            },
        )

    feed_events: list[dict[str, Any]] = []
    portfolio_create_events = list(
        session.exec(
            select(PortfolioLifecycleEvent)
            .join(Portfolio, PortfolioLifecycleEvent.portfolio_id == Portfolio.id)
            .where(
                Portfolio.owner_user_id == owner_user_id,
                PortfolioLifecycleEvent.event_type == "CREATED",
            )
            .order_by(col(PortfolioLifecycleEvent.created_at).desc(), col(PortfolioLifecycleEvent.id).desc())
        ).all(),
    )
    for row in portfolio_create_events[:6]:
        metadata = row.metadata_json or {}
        feed_events.append(
            {
                "event_type": "PORTFOLIO_CREATED",
                "source_id": int(row.portfolio_id),
                "summary": f"Portfolio {metadata.get('name', row.portfolio_id)} created.",
                "metadata_json": metadata,
                "created_at": row.created_at,
                "deterministic_key": f"portfolio_created:{row.id}",
            },
        )
    if alloc is not None:
        feed_events.append(
            {
                "event_type": "EXPOSURE_GENERATED",
                "source_id": int(alloc.id or 0),
                "summary": f"Owner-wide allocation snapshot refreshed across {alloc.total_item_count} items.",
                "metadata_json": {
                    "allocation_checksum": alloc.checksum,
                    "generation_scope_key": alloc.generation_scope_key,
                },
                "created_at": alloc.created_at,
                "deterministic_key": f"exposure_generated:{alloc.id}",
            },
        )
    if duplicate_clusters:
        batch_checksum = str(duplicate_clusters[0].generation_batch_checksum)
        feed_events.append(
            {
                "event_type": "DUPLICATE_CLUSTER_CREATED",
                "source_id": int(duplicate_clusters[0].id or 0),
                "summary": f"Duplicate intelligence refreshed with {len(duplicate_clusters)} active clusters.",
                "metadata_json": {"generation_batch_checksum": batch_checksum},
                "created_at": max(row.created_at for row in duplicate_clusters),
                "deterministic_key": f"duplicate_cluster_created:{batch_checksum}",
            },
        )
    latest_reco_signature = recommendation_rows
    if latest_reco_signature:
        hold_signature = [row for row in latest_reco_signature if str(row.recommendation_action) == "HOLD"]
        if hold_signature:
            feed_events.append(
                {
                    "event_type": "HOLD_RECOMMENDATION_CREATED",
                    "source_id": int(hold_signature[0].id or 0),
                    "summary": f"Generated {len(hold_signature)} HOLD recommendations in the latest strategy pass.",
                    "metadata_json": {"snapshot_date": hold_signature[0].snapshot_date.isoformat()},
                    "created_at": max(row.created_at for row in hold_signature),
                    "deterministic_key": f"hold_recommendation_created:{hold_signature[0].snapshot_date}:{hold_signature[0].replay_key}:{len(hold_signature)}",
                },
            )
        sell_signature = [
            row
            for row in latest_reco_signature
            if str(row.recommendation_action) in {"SELL", "GRADE_THEN_SELL", "REDUCE_EXPOSURE", "CONSOLIDATE"}
        ]
        if sell_signature:
            feed_events.append(
                {
                    "event_type": "SELL_RECOMMENDATION_CREATED",
                    "source_id": int(sell_signature[0].id or 0),
                    "summary": f"Generated {len(sell_signature)} sell-side strategy recommendations in the latest pass.",
                    "metadata_json": {"snapshot_date": sell_signature[0].snapshot_date.isoformat()},
                    "created_at": max(row.created_at for row in sell_signature),
                    "deterministic_key": f"sell_recommendation_created:{sell_signature[0].snapshot_date}:{sell_signature[0].replay_key}:{len(sell_signature)}",
                },
            )
    if overexposed_rows:
        feed_events.append(
            {
                "event_type": "CONCENTRATION_ALERT",
                "source_id": int(overexposed_rows[0].id or 0),
                "summary": f"Concentration engine surfaced {len(overexposed_rows)} overexposed or critical rows.",
                "metadata_json": {
                    "snapshot_date": overexposed_rows[0].snapshot_date.isoformat(),
                    "critical_count": sum(1 for row in overexposed_rows if str(row.exposure_status) == "CRITICAL"),
                },
                "created_at": max(row.created_at for row in overexposed_rows),
                "deterministic_key": f"concentration_alert:{overexposed_rows[0].snapshot_date}:{overexposed_rows[0].replay_key}:{len(overexposed_rows)}",
            },
        )
    if liquidity is not None and str(liquidity.liquidity_balance_status) in {"IMBALANCED", "CRITICAL"}:
        feed_events.append(
            {
                "event_type": "LIQUIDITY_WARNING",
                "source_id": int(liquidity.id or 0),
                "summary": f"Portfolio liquidity balance is {liquidity.liquidity_balance_status.lower()} in the latest scope snapshot.",
                "metadata_json": {"dead_capital_estimate": liquidity.dead_capital_estimate},
                "created_at": liquidity.created_at,
                "deterministic_key": f"liquidity_warning:{liquidity.id}:{liquidity.checksum}",
            },
        )
    if acquisition_rows:
        high_value_rows = [row for row in acquisition_rows if str(row.acquisition_priority) in {"HIGH", "ELITE"}]
        if high_value_rows:
            feed_events.append(
                {
                    "event_type": "ACQUISITION_OPPORTUNITY",
                    "source_id": int(high_value_rows[0].id or 0),
                    "summary": f"Acquisition engine surfaced {len(high_value_rows)} high-priority or elite opportunities.",
                    "metadata_json": {
                        "snapshot_date": high_value_rows[0].snapshot_date.isoformat(),
                        "elite_count": sum(1 for row in high_value_rows if str(row.acquisition_priority) == "ELITE"),
                    },
                    "created_at": max(row.created_at for row in high_value_rows),
                    "deterministic_key": f"acquisition_opportunity:{high_value_rows[0].snapshot_date}:{high_value_rows[0].replay_key}:{len(high_value_rows)}",
                },
            )

    alerts = _sort_alert_rows(alerts)
    feed_events = _sort_feed_rows(feed_events)

    checklist: dict[str, Any] = {
        "aggregation_version": AGGREGATION_VERSION,
        "owner_user_id": owner_user_id,
        "snapshot_date": snapshot_date,
        "portfolio_count": portfolio_count,
        "total_portfolio_value": total_portfolio_value,
        "total_cost_basis": total_cost_basis,
        "total_realized_sales": total_realized_sales,
        "diversification_score": diversification_score,
        "liquidity_efficiency_score": liquidity_efficiency_score,
        "concentration_risk_score": concentration_risk_score,
        "dead_capital_estimate": dead_capital_estimate,
        "duplicate_cluster_count": duplicate_cluster_count,
        "overexposed_category_count": len(overexposed_rows),
        "hold_recommendation_count": hold_count,
        "sell_recommendation_count": sell_count,
        "reduce_exposure_count": reduce_exposure_count,
        "acquisition_opportunity_count": acquisition_opportunity_count,
        "elite_acquisition_count": elite_acquisition_count,
        "grading_candidate_count": grading_candidate_count,
        "liquid_inventory_percentage": liquid_inventory_percentage,
        "illiquid_inventory_percentage": illiquid_inventory_percentage,
        "portfolio_ids": [int(row.id or 0) for row in portfolios],
        "metrics": metrics,
        "alerts": [
            {
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "source_snapshot_id": row["source_snapshot_id"],
                "message": row["message"],
            }
            for row in alerts
        ],
        "feed_events": [
            {
                "event_type": row["event_type"],
                "deterministic_key": row["deterministic_key"],
                "summary": row["summary"],
            }
            for row in feed_events
        ],
        "source_checksums": {
            "allocation": alloc.checksum if alloc is not None else None,
            "liquidity": liquidity.checksum if liquidity is not None else None,
            "duplicate_batch": duplicate_clusters[0].generation_batch_checksum if duplicate_clusters else None,
            "recommendations": [row.checksum for row in recommendation_rows[:20]],
            "concentration": [row.checksum for row in concentration_rows[:20]],
            "acquisition": [row.checksum for row in acquisition_rows[:20]],
        },
    }
    checklist["metrics_rows"] = metrics
    checklist["alert_rows"] = alerts
    checklist["feed_rows"] = feed_events
    return checklist


def _persist_metrics(session: Session, *, snapshot_id: int, metric_rows: list[dict[str, Any]]) -> None:
    for metric in metric_rows:
        session.add(
            PortfolioStrategyDashboardMetric(
                dashboard_snapshot_id=snapshot_id,
                metric_key=str(metric["metric_key"]),
                metric_value_decimal=metric.get("metric_value_decimal"),
                metric_value_text=metric.get("metric_value_text"),
                metric_metadata_json=_json_safe(metric.get("metric_metadata_json")),
            ),
        )


def _persist_alerts(
    session: Session,
    *,
    owner_user_id: int,
    alert_rows: list[dict[str, Any]],
) -> int:
    alert_payloads = [
        (
            row,
            _hash_payload(
                {
                    "owner_user_id": owner_user_id,
                    "alert_type": row["alert_type"],
                    "severity": row["severity"],
                    "source_portfolio_id": row["source_portfolio_id"],
                    "source_inventory_item_id": row["source_inventory_item_id"],
                    "source_snapshot_id": row["source_snapshot_id"],
                    "message": row["message"],
                },
            ),
        )
        for row in alert_rows
    ]
    replay_keys = tuple(replay_key for _, replay_key in alert_payloads)
    existing_keys = set[str]()
    if replay_keys:
        existing_keys = set(
            session.exec(
                select(PortfolioStrategyDashboardAlert.alert_replay_key).where(
                    PortfolioStrategyDashboardAlert.owner_user_id == owner_user_id,
                    col(PortfolioStrategyDashboardAlert.alert_replay_key).in_(replay_keys),
                )
            ).all(),
        )
    inserted_count = 0
    for row, replay_key in alert_payloads:
        if replay_key in existing_keys:
            continue
        session.add(
            PortfolioStrategyDashboardAlert(
                owner_user_id=owner_user_id,
                alert_type=str(row["alert_type"]),
                severity=str(row["severity"]),
                alert_replay_key=replay_key,
                source_portfolio_id=row["source_portfolio_id"],
                source_inventory_item_id=row["source_inventory_item_id"],
                source_snapshot_id=row["source_snapshot_id"],
                message=str(row["message"]),
                created_at=row["created_at"],
            ),
        )
        inserted_count += 1
        existing_keys.add(replay_key)
        logger.info(
            "Portfolio strategy alert persisted owner_user_id=%s alert_type=%s severity=%s source_snapshot_id=%s",
            owner_user_id,
            row["alert_type"],
            row["severity"],
            row["source_snapshot_id"],
        )
    return inserted_count


def _persist_feed(
    session: Session,
    *,
    owner_user_id: int,
    dashboard_snapshot_id: int,
    feed_rows: list[dict[str, Any]],
) -> int:
    deterministic_keys = tuple(str(row["deterministic_key"]) for row in feed_rows)
    existing_keys = set[str]()
    if deterministic_keys:
        existing_keys = set(
            session.exec(
                select(PortfolioStrategyDashboardFeedEvent.deterministic_key).where(
                    PortfolioStrategyDashboardFeedEvent.owner_user_id == owner_user_id,
                    col(PortfolioStrategyDashboardFeedEvent.deterministic_key).in_(deterministic_keys),
                )
            ).all(),
        )
    inserted_count = 0
    for row in feed_rows:
        deterministic_key = str(row["deterministic_key"])
        if deterministic_key in existing_keys:
            continue
        session.add(
            PortfolioStrategyDashboardFeedEvent(
                owner_user_id=owner_user_id,
                deterministic_key=deterministic_key,
                dashboard_snapshot_id=dashboard_snapshot_id,
                event_type=str(row["event_type"]),
                source_id=row["source_id"],
                summary=str(row["summary"]),
                metadata_json=_json_safe(row.get("metadata_json")),
                created_at=row["created_at"],
            ),
        )
        inserted_count += 1
        existing_keys.add(deterministic_key)
    logger.info(
        "Portfolio strategy feed batch owner_user_id=%s dashboard_snapshot_id=%s total_event_count=%s inserted_event_count=%s",
        owner_user_id,
        dashboard_snapshot_id,
        len(feed_rows),
        inserted_count,
    )
    return inserted_count


def generate_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    payload: PortfolioStrategyDashboardGeneratePayload,
) -> PortfolioStrategyDashboardGenerateResponse:
    replay_key = payload.replay_key.strip() if payload.replay_key else None
    snapshot_date = payload.snapshot_date or _utc_today()
    if replay_key:
        existing = session.exec(
            select(PortfolioStrategyDashboardSnapshot).where(
                PortfolioStrategyDashboardSnapshot.owner_user_id == owner_user_id,
                PortfolioStrategyDashboardSnapshot.replay_key == replay_key,
            )
        ).first()
        if existing is not None:
            logger.info(
                "Portfolio strategy dashboard replay reused snapshot_id=%s owner_user_id=%s checksum=%s replay_key=%s",
                existing.id,
                owner_user_id,
                existing.checksum,
                replay_key,
            )
            return PortfolioStrategyDashboardGenerateResponse(snapshot=_snapshot_read(existing))

    body = _compute_payload(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)
    checksum = _hash_payload(body)

    latest = latest_snapshot_for_owner(session, owner_user_id=owner_user_id)
    if latest is not None and latest.snapshot_date == snapshot_date and latest.checksum == checksum:
        logger.info(
            "Portfolio strategy dashboard checksum match reused snapshot_id=%s owner_user_id=%s checksum=%s",
            latest.id,
            owner_user_id,
            checksum,
        )
        return PortfolioStrategyDashboardGenerateResponse(snapshot=_snapshot_read(latest))

    snapshot = PortfolioStrategyDashboardSnapshot(
        owner_user_id=owner_user_id,
        replay_key=replay_key,
        portfolio_count=int(body["portfolio_count"]),
        total_portfolio_value=body["total_portfolio_value"],
        total_cost_basis=body["total_cost_basis"],
        total_realized_sales=body["total_realized_sales"],
        diversification_score=body["diversification_score"],
        liquidity_efficiency_score=body["liquidity_efficiency_score"],
        concentration_risk_score=body["concentration_risk_score"],
        dead_capital_estimate=body["dead_capital_estimate"],
        duplicate_cluster_count=int(body["duplicate_cluster_count"]),
        overexposed_category_count=int(body["overexposed_category_count"]),
        hold_recommendation_count=int(body["hold_recommendation_count"]),
        sell_recommendation_count=int(body["sell_recommendation_count"]),
        reduce_exposure_count=int(body["reduce_exposure_count"]),
        acquisition_opportunity_count=int(body["acquisition_opportunity_count"]),
        elite_acquisition_count=int(body["elite_acquisition_count"]),
        grading_candidate_count=int(body["grading_candidate_count"]),
        liquid_inventory_percentage=body["liquid_inventory_percentage"],
        illiquid_inventory_percentage=body["illiquid_inventory_percentage"],
        checksum=checksum,
        snapshot_date=snapshot_date,
    )
    session.add(snapshot)
    session.flush()

    _persist_metrics(session, snapshot_id=int(snapshot.id or 0), metric_rows=body["metrics_rows"])
    inserted_alert_count = _persist_alerts(session, owner_user_id=owner_user_id, alert_rows=body["alert_rows"])
    inserted_feed_count = _persist_feed(
        session,
        owner_user_id=owner_user_id,
        dashboard_snapshot_id=int(snapshot.id or 0),
        feed_rows=body["feed_rows"],
    )
    session.commit()
    session.refresh(snapshot)
    logger.info(
        "Generated portfolio strategy dashboard snapshot_id=%s owner_user_id=%s checksum=%s engine_versions=%s alert_count=%s feed_count=%s",
        snapshot.id,
        owner_user_id,
        checksum,
        json.dumps(SOURCE_ENGINE_VERSIONS, sort_keys=True),
        inserted_alert_count,
        inserted_feed_count,
    )
    return PortfolioStrategyDashboardGenerateResponse(snapshot=_snapshot_read(snapshot))


def list_metrics_owner(
    session: Session,
    *,
    owner_user_id: int,
    dashboard_snapshot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioStrategyDashboardMetricListResponse:
    limit, offset = clamp_portfolio_strategy_dashboard_pagination(limit=limit, offset=offset)
    if dashboard_snapshot_id is None:
        latest = latest_snapshot_for_owner(session, owner_user_id=owner_user_id)
        dashboard_snapshot_id = int(latest.id) if latest is not None and latest.id is not None else None
    if dashboard_snapshot_id is None:
        return PortfolioStrategyDashboardMetricListResponse(items=[], total_items=0, limit=limit, offset=offset)
    stmt = select(PortfolioStrategyDashboardMetric).join(
        PortfolioStrategyDashboardSnapshot,
        PortfolioStrategyDashboardMetric.dashboard_snapshot_id == PortfolioStrategyDashboardSnapshot.id,
    ).where(PortfolioStrategyDashboardSnapshot.owner_user_id == owner_user_id)
    if dashboard_snapshot_id is not None:
        stmt = stmt.where(PortfolioStrategyDashboardMetric.dashboard_snapshot_id == dashboard_snapshot_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(PortfolioStrategyDashboardMetric.metric_key).asc(), col(PortfolioStrategyDashboardMetric.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioStrategyDashboardMetricListResponse(
        items=[PortfolioStrategyDashboardMetricRead.model_validate(row, from_attributes=True) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_metrics_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    dashboard_snapshot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioStrategyDashboardMetricListResponse:
    limit, offset = clamp_portfolio_strategy_dashboard_pagination(limit=limit, offset=offset)
    if dashboard_snapshot_id is None:
        latest = latest_snapshot_ops(session, owner_user_id=owner_user_id)
        dashboard_snapshot_id = int(latest.id) if latest is not None and latest.id is not None else None
    if dashboard_snapshot_id is None:
        return PortfolioStrategyDashboardMetricListResponse(items=[], total_items=0, limit=limit, offset=offset)
    stmt = select(PortfolioStrategyDashboardMetric).join(
        PortfolioStrategyDashboardSnapshot,
        PortfolioStrategyDashboardMetric.dashboard_snapshot_id == PortfolioStrategyDashboardSnapshot.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioStrategyDashboardSnapshot.owner_user_id == owner_user_id)
    if dashboard_snapshot_id is not None:
        stmt = stmt.where(PortfolioStrategyDashboardMetric.dashboard_snapshot_id == dashboard_snapshot_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioStrategyDashboardMetric.metric_key).asc(),
            col(PortfolioStrategyDashboardMetric.id).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioStrategyDashboardMetricListResponse(
        items=[PortfolioStrategyDashboardMetricRead.model_validate(row, from_attributes=True) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_alerts_owner(
    session: Session,
    *,
    owner_user_id: int,
    severity: str | None = None,
    alert_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioStrategyDashboardAlertListResponse:
    limit, offset = clamp_portfolio_strategy_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioStrategyDashboardAlert).where(PortfolioStrategyDashboardAlert.owner_user_id == owner_user_id)
    if severity is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.severity == severity)
    if alert_type is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.alert_type == alert_type)
    if created_from is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.created_at <= created_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioStrategyDashboardAlert.created_at).desc(),
            col(PortfolioStrategyDashboardAlert.alert_type).asc(),
            col(PortfolioStrategyDashboardAlert.alert_replay_key).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioStrategyDashboardAlertListResponse(
        items=[PortfolioStrategyDashboardAlertRead.model_validate(row, from_attributes=True) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_alerts_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioStrategyDashboardAlertListResponse:
    limit, offset = clamp_portfolio_strategy_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioStrategyDashboardAlert)
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.owner_user_id == owner_user_id)
    if severity is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.severity == severity)
    if alert_type is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.alert_type == alert_type)
    if created_from is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(PortfolioStrategyDashboardAlert.created_at <= created_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioStrategyDashboardAlert.owner_user_id).asc(),
            col(PortfolioStrategyDashboardAlert.created_at).desc(),
            col(PortfolioStrategyDashboardAlert.alert_type).asc(),
            col(PortfolioStrategyDashboardAlert.alert_replay_key).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioStrategyDashboardAlertListResponse(
        items=[PortfolioStrategyDashboardAlertRead.model_validate(row, from_attributes=True) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_feed_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioStrategyDashboardFeedListResponse:
    limit, offset = clamp_portfolio_strategy_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioStrategyDashboardFeedEvent).where(PortfolioStrategyDashboardFeedEvent.owner_user_id == owner_user_id)
    if event_type is not None:
        stmt = stmt.where(PortfolioStrategyDashboardFeedEvent.event_type == event_type)
    if created_from is not None:
        stmt = stmt.where(PortfolioStrategyDashboardFeedEvent.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(PortfolioStrategyDashboardFeedEvent.created_at <= created_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioStrategyDashboardFeedEvent.created_at).desc(),
            col(PortfolioStrategyDashboardFeedEvent.event_type).asc(),
            col(PortfolioStrategyDashboardFeedEvent.deterministic_key).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioStrategyDashboardFeedListResponse(
        items=[PortfolioStrategyDashboardFeedEventRead.model_validate(row, from_attributes=True) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_feed_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PortfolioStrategyDashboardFeedListResponse:
    limit, offset = clamp_portfolio_strategy_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioStrategyDashboardFeedEvent)
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioStrategyDashboardFeedEvent.owner_user_id == owner_user_id)
    if event_type is not None:
        stmt = stmt.where(PortfolioStrategyDashboardFeedEvent.event_type == event_type)
    if created_from is not None:
        stmt = stmt.where(PortfolioStrategyDashboardFeedEvent.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(PortfolioStrategyDashboardFeedEvent.created_at <= created_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(
            col(PortfolioStrategyDashboardFeedEvent.owner_user_id).asc(),
            col(PortfolioStrategyDashboardFeedEvent.created_at).desc(),
            col(PortfolioStrategyDashboardFeedEvent.event_type).asc(),
            col(PortfolioStrategyDashboardFeedEvent.deterministic_key).asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return PortfolioStrategyDashboardFeedListResponse(
        items=[PortfolioStrategyDashboardFeedEventRead.model_validate(row, from_attributes=True) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )
