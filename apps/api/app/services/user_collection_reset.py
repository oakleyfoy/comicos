"""Scoped deletion of one user's collection, orders, and import data."""

from __future__ import annotations

import logging
import traceback
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
from app.models.p92_import_line_cover import P92ImportLineCoverResolution
from app.models.recommendation_v2 import (
    RecommendationDecisionV2,
    RecommendationRunV2,
    RecommendationScoreComponentV2,
    RecommendationScoreV2,
)
from app.models.storage_location import P79InventoryLocationAssignment

logger = logging.getLogger(__name__)

_INVENTORY_FK_FIELD_NAMES = ("inventory_copy_id", "inventory_item_id")


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


def _recommendation_score_v2_id_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    owned_score_ids = select(RecommendationScoreV2.id).where(RecommendationScoreV2.owner_user_id == scope.user_id)
    return column.in_(owned_score_ids)


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
# Release/catalog intelligence is user-scoped in the DB but is not collection data.
_PRESERVE_RELEASE_CATALOG_MODELS: frozenset[type[SQLModel]] = frozenset(
    {
        models.ReleaseSeries,
        models.ReleaseIssue,
        models.ReleaseVariant,
        models.ReleaseKeySignal,
        models.ReleaseAgentExecution,
        models.ReleaseImportRun,
        models.ReleaseImportFile,
        models.ReleaseImportError,
        models.ReleaseIntelligenceMatch,
        models.IndustryPublisher,
        models.IndustryReleaseScanRun,
        models.IndustryReleaseCandidate,
        models.IndustryReleaseSignal,
        models.FutureReleaseMatch,
        models.FutureReleaseAction,
        models.FutureReleaseCertificationRun,
    }
)

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
) | _PRESERVE_RELEASE_CATALOG_MODELS


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
        DeleteStep(
            "p92_import_line_cover_resolution",
            P92ImportLineCoverResolution,
            lambda s: _owner(s, P92ImportLineCoverResolution.owner_user_id),
        ),
        DeleteStep(
            "p79_inventory_location_assignment",
            P79InventoryLocationAssignment,
            lambda s: _owner(s, P79InventoryLocationAssignment.owner_user_id),
        ),
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
        DeleteStep(
            "recommendation_score_component_v2",
            RecommendationScoreComponentV2,
            lambda s: _recommendation_score_v2_id_in(s, RecommendationScoreComponentV2.recommendation_score_id),
        ),
        DeleteStep(
            "recommendation_decision_v2",
            RecommendationDecisionV2,
            lambda s: _recommendation_score_v2_id_in(s, RecommendationDecisionV2.recommendation_score_id),
        ),
        DeleteStep(
            "recommendation_score_v2",
            RecommendationScoreV2,
            lambda s: _owner(s, RecommendationScoreV2.owner_user_id),
        ),
        DeleteStep(
            "recommendation_run_v2",
            RecommendationRunV2,
            lambda s: _owner(s, RecommendationRunV2.owner_user_id),
        ),
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


def _split_explicit_at_inventory_copies(explicit: list[DeleteStep]) -> tuple[list[DeleteStep], list[DeleteStep]]:
    idx = next(i for i, step in enumerate(explicit) if step.label == "inventory_copies")
    return explicit[:idx], explicit[idx:]


def _sort_auxiliary_delete_steps(steps: list[DeleteStep]) -> list[DeleteStep]:
    if not steps:
        return []
    table_by_name = {step.model.__table__.name: step for step in steps}
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"Cannot correctly sort tables;.*")
        sorted_tables = sort_tables([step.model.__table__ for step in steps])
    ordered = [table_by_name[table.name] for table in reversed(sorted_tables) if table.name in table_by_name]
    seen: set[str] = set()
    deduped: list[DeleteStep] = []
    for step in ordered:
        if step.label in seen:
            continue
        seen.add(step.label)
        deduped.append(step)
    for step in steps:
        if step.label not in seen:
            deduped.append(step)
    return deduped


def _stabilize_collection_delete_order(steps: list[DeleteStep]) -> list[DeleteStep]:
    """Ensure inventory copies are removed before order items that they reference."""
    ordered = list(steps)
    edges: tuple[tuple[str, str], ...] = (
        ("portfolio_items", "inventory_copies"),
        ("inventory_copies", "order_items"),
        ("order_items", "customer_orders"),
    )
    labels = [step.label for step in ordered]
    for before_label, after_label in edges:
        if before_label not in labels or after_label not in labels:
            continue
        before_idx = labels.index(before_label)
        after_idx = labels.index(after_label)
        if before_idx < after_idx:
            continue
        step = ordered.pop(before_idx)
        after_idx = labels.index(after_label)
        ordered.insert(after_idx, step)
        labels = [item.label for item in ordered]
    return ordered


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


def _inventory_fk_delete_steps(*, skip_models: frozenset[type[SQLModel]]) -> list[DeleteStep]:
    """Delete rows in mapped tables that FK-reference inventory_copy for this user's copies."""
    steps: list[DeleteStep] = []
    seen_labels: set[str] = set()
    for value in vars(models).values():
        if not isinstance(value, type) or not issubclass(value, SQLModel):
            continue
        if value in _NEVER_DELETE_MODELS or value is InventoryCopy:
            continue
        if value in skip_models:
            continue
        if getattr(value, "__table__", None) is None:
            continue
        fk_column = None
        for field_name in _INVENTORY_FK_FIELD_NAMES:
            if field_name in value.model_fields:
                fk_column = getattr(value, field_name)
                break
        if fk_column is None:
            continue
        label = getattr(value, "__tablename__", value.__name__)
        if label in seen_labels:
            continue
        seen_labels.add(label)
        steps.append(
            DeleteStep(
                label,
                value,
                lambda scope, col=fk_column: _inventory_in(scope, col),
            )
        )
    return steps


def _ordered_delete_steps() -> list[DeleteStep]:
    explicit = _explicit_delete_steps()
    before_inventory, inventory_and_orders = _split_explicit_at_inventory_copies(explicit)
    explicit_models = frozenset(step.model for step in explicit)
    inventory_fk = _inventory_fk_delete_steps(skip_models=explicit_models)
    explicit_models = explicit_models | frozenset(step.model for step in inventory_fk)
    sweep_steps = [
        DeleteStep(getattr(model, "__tablename__", model.__name__), model, lambda s, m=model: _owner(s, m.owner_user_id))
        for model in _owner_user_id_sweep_models()
        if model not in explicit_models
    ]
    auxiliary = _sort_auxiliary_delete_steps(inventory_fk + sweep_steps)
    return _stabilize_collection_delete_order(before_inventory + auxiliary + inventory_and_orders)


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


class UserCollectionResetError(Exception):
    """Reset delete transaction failed partway through."""

    def __init__(
        self,
        *,
        failed_table: str,
        message: str,
        summaries: list[TableDeleteSummary],
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.failed_table = failed_table
        self.message = message
        self.summaries = summaries
        self.cause = cause
        self.traceback = "".join(traceback.format_exception(type(cause), cause, cause.__traceback__)) if cause else None


def _break_delete_cycles(connection: Connection, scope: UserCollectionScope) -> None:
    if scope.inventory_ids:
        connection.execute(
            update(InventoryCopy.__table__)
            .where(InventoryCopy.id.in_(scope.inventory_ids))
            .values(primary_cover_image_id=None)
        )
    if scope.draft_import_ids:
        connection.execute(
            update(DraftImport.__table__)
            .where(DraftImport.id.in_(scope.draft_import_ids))
            .values(primary_cover_image_id=None)
        )
    if scope.draft_import_ids:
        connection.execute(
            update(P92ImportLineCoverResolution.__table__)
            .where(P92ImportLineCoverResolution.draft_import_id.in_(scope.draft_import_ids))
            .values(inventory_copy_id=None)
        )
    elif scope.inventory_ids:
        connection.execute(
            update(P92ImportLineCoverResolution.__table__)
            .where(P92ImportLineCoverResolution.inventory_copy_id.in_(scope.inventory_ids))
            .values(inventory_copy_id=None)
        )


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
        logger.info(
            "collection_reset execute start user_id=%s email=%s inventory=%s orders=%s drafts=%s",
            user.id,
            user.email,
            len(scope.inventory_ids),
            len(scope.order_ids),
            len(scope.draft_import_ids),
        )
        try:
            with engine.begin() as connection:
                _break_delete_cycles(connection, scope)
                for step in steps:
                    targeted = _count_rows(connection, step, scope)
                    logger.info(
                        "collection_reset deleting table=%s targeted=%s",
                        step.label,
                        targeted,
                    )
                    if targeted == 0:
                        continue
                    try:
                        deleted = _delete_rows(connection, step, scope)
                    except Exception as exc:
                        logger.exception(
                            "collection_reset failed table=%s targeted=%s deleted_before=%s",
                            step.label,
                            targeted,
                            sum(row.row_count for row in summaries),
                        )
                        raise UserCollectionResetError(
                            failed_table=step.label,
                            message=str(exc),
                            summaries=list(summaries),
                            cause=exc,
                        ) from exc
                    logger.info(
                        "collection_reset deleted table=%s rows=%s",
                        step.label,
                        deleted,
                    )
                    if deleted:
                        summaries.append(TableDeleteSummary(label=step.label, row_count=deleted))
        except UserCollectionResetError:
            raise
        except Exception as exc:
            logger.exception("collection_reset transaction failed user_id=%s", user.id)
            raise UserCollectionResetError(
                failed_table="transaction",
                message=str(exc),
                summaries=list(summaries),
                cause=exc,
            ) from exc
        logger.info(
            "collection_reset execute complete user_id=%s tables=%s total_rows=%s",
            user.id,
            len(summaries),
            sum(row.row_count for row in summaries),
        )
    else:
        with engine.connect() as connection:
            for step in steps:
                count = _count_rows(connection, step, scope)
                if count:
                    summaries.append(TableDeleteSummary(label=step.label, row_count=count))
                    logger.debug("collection_reset preview table=%s count=%s", step.label, count)

    return UserCollectionResetResult(
        user_id=int(user.id),
        email=user.email,
        dry_run=not execute,
        table_summaries=summaries,
    )
