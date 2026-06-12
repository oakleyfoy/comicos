"""Scoped deletion of one user's collection, orders, and import data."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, delete, false, func, or_, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.sql.ddl import sort_tables
from sqlmodel import Session, SQLModel

import app.models as models
from app.models import (
    CollectionRiskSnapshot,
    CollectionScenarioRun,
    CollectionValuationSnapshot,
    CoverImage,
    DraftImport,
    GmailAccount,
    GmailImportRecord,
    InventoryCopy,
    InventoryFmvSnapshot,
    OpsEvent,
    Order,
    OrderItem,
    P90FmvSnapshot,
    Portfolio,
    PortfolioItem,
    ReceivingSession,
    ReceivingSessionItem,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    RetailerSyncRun,
    User,
)


@dataclass(frozen=True)
class UserCollectionScope:
    user_id: int
    inventory_ids: tuple[int, ...] = ()
    order_ids: tuple[int, ...] = ()
    order_item_ids: tuple[int, ...] = ()
    draft_import_ids: tuple[int, ...] = ()
    portfolio_ids: tuple[int, ...] = ()
    receiving_session_ids: tuple[int, ...] = ()
    gmail_account_id: int | None = None
    cover_image_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class DeleteStep:
    label: str
    model: type[SQLModel]
    predicate: Callable[[UserCollectionScope], ColumnElement[bool]]


def _scalar_ids(session: Session, statement) -> tuple[int, ...]:
    return tuple(int(value) for value in session.scalars(statement).all())


def build_user_collection_scope(session: Session, *, user_id: int) -> UserCollectionScope:
    inventory_ids = _scalar_ids(session, select(InventoryCopy.id).where(InventoryCopy.user_id == user_id))
    order_ids = _scalar_ids(session, select(Order.id).where(Order.user_id == user_id))
    order_item_ids: tuple[int, ...] = ()
    if order_ids:
        order_item_ids = _scalar_ids(
            session, select(OrderItem.id).where(OrderItem.order_id.in_(order_ids))
        )
    draft_import_ids = _scalar_ids(session, select(DraftImport.id).where(DraftImport.user_id == user_id))
    portfolio_ids = _scalar_ids(session, select(Portfolio.id).where(Portfolio.owner_user_id == user_id))
    receiving_session_ids = _scalar_ids(
        session, select(ReceivingSession.id).where(ReceivingSession.owner_user_id == user_id)
    )
    gmail_account_id = session.scalar(select(GmailAccount.id).where(GmailAccount.user_id == user_id))
    cover_clauses = []
    if draft_import_ids:
        cover_clauses.append(CoverImage.draft_import_id.in_(draft_import_ids))
    if inventory_ids:
        cover_clauses.append(CoverImage.inventory_copy_id.in_(inventory_ids))
    cover_image_ids: tuple[int, ...] = ()
    if cover_clauses:
        cover_image_ids = _scalar_ids(session, select(CoverImage.id).where(or_(*cover_clauses)))
    return UserCollectionScope(
        user_id=user_id,
        inventory_ids=inventory_ids,
        order_ids=order_ids,
        order_item_ids=order_item_ids,
        draft_import_ids=draft_import_ids,
        portfolio_ids=portfolio_ids,
        receiving_session_ids=receiving_session_ids,
        gmail_account_id=int(gmail_account_id) if gmail_account_id is not None else None,
        cover_image_ids=cover_image_ids,
    )


def _owner(scope: UserCollectionScope, column):
    return column == scope.user_id


def _inventory_in(scope: UserCollectionScope, column):
    if not scope.inventory_ids:
        return column.in_(())
    return column.in_(scope.inventory_ids)


def _order_in(scope: UserCollectionScope, column):
    if not scope.order_ids:
        return column.in_(())
    return column.in_(scope.order_ids)


def _order_item_in(scope: UserCollectionScope, column):
    if not scope.order_item_ids:
        return column.in_(())
    return column.in_(scope.order_item_ids)


def _draft_in(scope: UserCollectionScope, column):
    if not scope.draft_import_ids:
        return column.in_(())
    return column.in_(scope.draft_import_ids)


def _portfolio_in(scope: UserCollectionScope, column):
    if not scope.portfolio_ids:
        return column.in_(())
    return column.in_(scope.portfolio_ids)


def _receiving_in(scope: UserCollectionScope, column):
    if not scope.receiving_session_ids:
        return column.in_(())
    return column.in_(scope.receiving_session_ids)


def _cover_image_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return CoverImage.id.in_(scope.cover_image_ids)


def _cover_image_id_predicate(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return column.in_(scope.cover_image_ids)


def _cover_image_match_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return or_(
        models.CoverImageMatchCandidate.source_cover_image_id.in_(scope.cover_image_ids),
        models.CoverImageMatchCandidate.candidate_cover_image_id.in_(scope.cover_image_ids),
    )


def _cover_image_link_decision_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return or_(
        models.CoverImageLinkDecision.source_cover_image_id.in_(scope.cover_image_ids),
        models.CoverImageLinkDecision.candidate_cover_image_id.in_(scope.cover_image_ids),
    )


def _gmail_import_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if scope.gmail_account_id is None:
        return false()
    return GmailImportRecord.gmail_account_id == scope.gmail_account_id


# Models we never touch during a per-user collection reset.
_NEVER_DELETE_MODELS: frozenset[type[SQLModel]] = frozenset(
    {
        User,
        models.RetailerAccount,
        GmailAccount,
        models.ReleaseWatchlist,
        models.ReleaseWatchlistItem,
        models.WatchlistAgentExecution,
        models.AutoWatchlist,
        models.AutoWatchlistItem,
        models.P81DiscoveryWatchlist,
        models.MarketSource,
        models.MarketSourceSnapshot,
    }
)


def _portfolio_related_steps() -> list[DeleteStep]:
    portfolio_models: list[type[SQLModel]] = [
        models.PortfolioStrategyDashboardFeedEvent,
        models.PortfolioStrategyDashboardAlert,
        models.PortfolioStrategyDashboardMetric,
        models.PortfolioStrategyDashboardSnapshot,
        models.PortfolioLifecycleEvent,
        models.PortfolioItem,
        models.PortfolioExposureEvidence,
        models.PortfolioExposureSnapshot,
        models.PortfolioAllocationSnapshot,
        models.PortfolioLiquidityEvidence,
        models.PortfolioLiquidityHistory,
        models.PortfolioLiquidityBucket,
        models.PortfolioLiquiditySnapshot,
        models.PortfolioRecommendationEvidence,
        models.PortfolioRecommendationHistory,
        models.PortfolioRecommendationScenario,
        models.PortfolioRecommendation,
        models.PortfolioMarketCouplingEvidence,
        models.PortfolioMarketCouplingHistory,
        models.PortfolioMarketCouplingEdge,
        models.PortfolioMarketCouplingSnapshot,
        models.ConcentrationRiskEvidence,
        models.ConcentrationRiskHistory,
        models.ConcentrationRiskFactor,
        models.ConcentrationRiskSnapshot,
        models.AcquisitionPriorityEvidence,
        models.AcquisitionPriorityHistory,
        models.AcquisitionPriorityScenario,
        models.AcquisitionPrioritySnapshot,
        models.DuplicateClusterItem,
        models.DuplicateConsolidationRecommendation,
        models.DuplicateHistorySnapshot,
        models.DuplicateCluster,
        Portfolio,
    ]
    steps: list[DeleteStep] = []
    for model in portfolio_models:
        if not hasattr(model, "owner_user_id"):
            if model is PortfolioItem:
                steps.append(
                    DeleteStep(
                        "portfolio_items",
                        model,
                        lambda scope, col=PortfolioItem.portfolio_id: _portfolio_in(scope, col),
                    )
                )
            continue
        label = getattr(model, "__tablename__", model.__name__)
        steps.append(
            DeleteStep(
                label,
                model,
                lambda scope, col=model.owner_user_id: _owner(scope, col),
            )
        )
    return steps


def _explicit_delete_steps() -> list[DeleteStep]:
    steps: list[DeleteStep] = [
        DeleteStep("receiving_session_items", ReceivingSessionItem, lambda s: _receiving_in(s, ReceivingSessionItem.receiving_session_id)),
        DeleteStep("receiving_sessions", ReceivingSession, lambda s: _owner(s, ReceivingSession.owner_user_id)),
        DeleteStep("retailer_order_item_snapshots", RetailerOrderItemSnapshot, lambda s: _owner(s, RetailerOrderItemSnapshot.owner_user_id)),
        DeleteStep("retailer_order_snapshots", RetailerOrderSnapshot, lambda s: _owner(s, RetailerOrderSnapshot.owner_user_id)),
        DeleteStep("retailer_sync_runs", RetailerSyncRun, lambda s: _owner(s, RetailerSyncRun.owner_user_id)),
        DeleteStep("gmail_import_records", GmailImportRecord, _gmail_import_predicate),
        DeleteStep("p83_collection_valuation_snapshot", CollectionValuationSnapshot, lambda s: _owner(s, CollectionValuationSnapshot.owner_user_id)),
        DeleteStep("p83_collection_risk_snapshot", CollectionRiskSnapshot, lambda s: _owner(s, CollectionRiskSnapshot.owner_user_id)),
        DeleteStep("p83_collection_scenario_run", CollectionScenarioRun, lambda s: _owner(s, CollectionScenarioRun.owner_user_id)),
        DeleteStep("p90_fmv_snapshot", P90FmvSnapshot, lambda s: _owner(s, P90FmvSnapshot.owner_user_id)),
        DeleteStep("inventory_fmv_snapshots", InventoryFmvSnapshot, lambda s: _inventory_in(s, InventoryFmvSnapshot.inventory_copy_id)),
        DeleteStep("ops_events", OpsEvent, lambda s: OpsEvent.user_id == s.user_id),
    ]
    steps.extend(_portfolio_related_steps())
    steps.extend(
        [
            DeleteStep("listing_inventory_links", models.ListingInventoryLink, lambda s: _inventory_in(s, models.ListingInventoryLink.inventory_copy_id)),
            DeleteStep("grading_candidates", models.GradingCandidate, lambda s: _inventory_in(s, models.GradingCandidate.inventory_item_id)),
            DeleteStep("canonical_issue_link_suggestions", models.CanonicalIssueLinkSuggestion, lambda s: _inventory_in(s, models.CanonicalIssueLinkSuggestion.inventory_copy_id)),
            DeleteStep("cover_image_link_decisions", models.CoverImageLinkDecision, _cover_image_link_decision_predicate),
            DeleteStep("cover_image_match_candidates", models.CoverImageMatchCandidate, _cover_image_match_predicate),
            DeleteStep(
                "cover_image_ocr_candidates",
                models.CoverImageOcrCandidate,
                lambda s: _cover_image_id_predicate(s, models.CoverImageOcrCandidate.cover_image_id),
            ),
            DeleteStep(
                "cover_image_ocr_quality_analysis",
                models.CoverImageOcrQualityAnalysis,
                lambda s: _cover_image_id_predicate(s, models.CoverImageOcrQualityAnalysis.cover_image_id),
            ),
            DeleteStep(
                "cover_image_ocr_reconciliation_warnings",
                models.CoverImageOcrReconciliationWarning,
                lambda s: _cover_image_id_predicate(s, models.CoverImageOcrReconciliationWarning.cover_image_id),
            ),
            DeleteStep(
                "cover_image_ocr_regions",
                models.CoverImageOcrRegion,
                lambda s: _cover_image_id_predicate(s, models.CoverImageOcrRegion.cover_image_id),
            ),
            DeleteStep(
                "cover_image_ocr_results",
                models.CoverImageOcrResult,
                lambda s: _cover_image_id_predicate(s, models.CoverImageOcrResult.cover_image_id),
            ),
            DeleteStep(
                "cover_image_barcode_candidates",
                models.CoverImageBarcodeCandidate,
                lambda s: _cover_image_id_predicate(s, models.CoverImageBarcodeCandidate.cover_image_id),
            ),
            DeleteStep(
                "cover_image_fingerprints",
                models.CoverImageFingerprint,
                lambda s: _cover_image_id_predicate(s, models.CoverImageFingerprint.cover_image_id),
            ),
            DeleteStep(
                "cover_image_derivatives",
                models.CoverImageDerivative,
                lambda s: _cover_image_id_predicate(s, models.CoverImageDerivative.cover_image_id),
            ),
            DeleteStep("cover_images", CoverImage, _cover_image_predicate),
            DeleteStep("draft_imports", DraftImport, lambda s: DraftImport.user_id == s.user_id),
            DeleteStep("inventory_copies", InventoryCopy, lambda s: InventoryCopy.user_id == s.user_id),
            DeleteStep("order_items", OrderItem, lambda s: _order_in(s, OrderItem.order_id)),
            DeleteStep("customer_orders", Order, lambda s: Order.user_id == s.user_id),
        ]
    )
    return steps


def _owner_user_id_sweep_models() -> list[type[SQLModel]]:
    discovered: list[type[SQLModel]] = []
    for value in vars(models).values():
        if not isinstance(value, type) or not issubclass(value, SQLModel):
            continue
        if value in _NEVER_DELETE_MODELS:
            continue
        table = getattr(value, "__table__", None)
        if table is None:
            continue
        if "owner_user_id" not in value.model_fields:
            continue
        if value in {InventoryCopy, Order, DraftImport}:
            continue
        discovered.append(value)
    return discovered


def _ordered_delete_steps() -> list[DeleteStep]:
    explicit = _explicit_delete_steps()
    explicit_models = {step.model for step in explicit}
    sweep_steps = [
        DeleteStep(getattr(model, "__tablename__", model.__name__), model, lambda s, m=model: _owner(s, m.owner_user_id))
        for model in _owner_user_id_sweep_models()
        if model not in explicit_models
    ]
    combined = explicit + sweep_steps
    table_by_name = {step.model.__table__.name: step for step in combined}
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"Cannot correctly sort tables;.*")
        sorted_tables = sort_tables([step.model.__table__ for step in combined])
    ordered = [table_by_name[table.name] for table in reversed(sorted_tables) if table.name in table_by_name]
    seen: set[str] = set()
    deduped: list[DeleteStep] = []
    for step in ordered:
        if step.label in seen:
            continue
        seen.add(step.label)
        deduped.append(step)
    for step in combined:
        if step.label not in seen:
            deduped.append(step)
    return deduped


@dataclass
class TableDeleteSummary:
    label: str
    row_count: int


@dataclass
class UserCollectionResetResult:
    user_id: int
    email: str
    dry_run: bool
    table_summaries: list[TableDeleteSummary] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return sum(row.row_count for row in self.table_summaries)


def _break_delete_cycles(connection: Connection) -> None:
    connection.execute(update(InventoryCopy.__table__).values(primary_cover_image_id=None))
    connection.execute(update(DraftImport.__table__).values(primary_cover_image_id=None))


def _count_rows(connection: Connection, step: DeleteStep, scope: UserCollectionScope) -> int:
    predicate = step.predicate(scope)
    return int(connection.execute(select(func.count()).select_from(step.model.__table__).where(predicate)).scalar_one())


def _delete_rows(connection: Connection, step: DeleteStep, scope: UserCollectionScope) -> int:
    result = connection.execute(delete(step.model).where(step.predicate(scope)))
    return int(result.rowcount or 0)


COLLECTION_RESET_CONFIRMATION_PHRASE = "DELETE MY COLLECTION"


def remaining_collection_row_counts(session: Session, *, user_id: int) -> dict[str, int]:
    """Counts of user-owned collection rows after a reset (or preview baseline)."""
    gmail_account_id = session.scalar(select(GmailAccount.id).where(GmailAccount.user_id == user_id))
    gmail_imports = 0
    if gmail_account_id is not None:
        gmail_imports = int(
            session.scalar(
                select(func.count())
                .select_from(GmailImportRecord)
                .where(GmailImportRecord.gmail_account_id == gmail_account_id)
            )
            or 0
        )
    portfolio_ids = _scalar_ids(session, select(Portfolio.id).where(Portfolio.owner_user_id == user_id))
    portfolio_items = 0
    if portfolio_ids:
        portfolio_items = int(
            session.scalar(
                select(func.count())
                .select_from(PortfolioItem)
                .where(PortfolioItem.portfolio_id.in_(portfolio_ids))
            )
            or 0
        )
    return {
        "inventory_copies": int(
            session.scalar(select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == user_id)) or 0
        ),
        "orders": int(session.scalar(select(func.count()).select_from(Order).where(Order.user_id == user_id)) or 0),
        "draft_imports": int(
            session.scalar(select(func.count()).select_from(DraftImport).where(DraftImport.user_id == user_id)) or 0
        ),
        "retailer_order_snapshots": int(
            session.scalar(
                select(func.count()).select_from(RetailerOrderSnapshot).where(RetailerOrderSnapshot.owner_user_id == user_id)
            )
            or 0
        ),
        "gmail_import_records": gmail_imports,
        "portfolio_items": portfolio_items,
        "portfolios": len(portfolio_ids),
    }


def friendly_delete_summary(table_summaries: list[TableDeleteSummary]) -> dict[str, int]:
    """Map internal table labels to user-facing aggregate counts."""
    by_label = {row.label: row.row_count for row in table_summaries}
    order_items = by_label.get("order_items", 0)
    return {
        "inventory_copies": by_label.get("inventory_copies", 0),
        "orders": by_label.get("customer_orders", 0),
        "order_items": order_items,
        "draft_imports": by_label.get("draft_imports", 0),
        "retailer_order_snapshots": by_label.get("retailer_order_snapshots", 0),
        "retailer_order_item_snapshots": by_label.get("retailer_order_item_snapshots", 0),
        "gmail_import_records": by_label.get("gmail_import_records", 0),
        "portfolio_items": by_label.get("portfolio_items", 0),
        "portfolios": by_label.get("portfolio", 0),
        "cover_images": by_label.get("cover_images", 0),
        "receiving_sessions": by_label.get("receiving_sessions", 0),
        "collection_valuation_snapshots": by_label.get("p83_collection_valuation_snapshot", 0),
        "inventory_fmv_snapshots": by_label.get("inventory_fmv_snapshots", 0),
        "total_rows": sum(row.row_count for row in table_summaries),
    }


def reset_user_collection_data(
    session: Session,
    *,
    user: User,
    execute: bool,
) -> UserCollectionResetResult:
    if user.id is None:
        raise ValueError("user must be persisted")
    scope = build_user_collection_scope(session, user_id=int(user.id))
    steps = _ordered_delete_steps()
    summaries: list[TableDeleteSummary] = []

    engine = session.get_bind()
    if execute:
        with engine.begin() as connection:
            _break_delete_cycles(connection)
            for step in steps:
                deleted = _delete_rows(connection, step, scope)
                if deleted:
                    summaries.append(TableDeleteSummary(label=step.label, row_count=deleted))
                    print(f"deleted {step.label}: {deleted}")
    else:
        with engine.connect() as connection:
            for step in steps:
                count = _count_rows(connection, step, scope)
                if count:
                    summaries.append(TableDeleteSummary(label=step.label, row_count=count))
                    print(f"  - {step.label}: {count}")

    return UserCollectionResetResult(
        user_id=int(user.id),
        email=user.email,
        dry_run=not execute,
        table_summaries=summaries,
    )
