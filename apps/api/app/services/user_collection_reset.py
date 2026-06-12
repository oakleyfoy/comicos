"""Scoped deletion of one user's collection, orders, and import data."""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models import (
    DraftImport,
    GmailImportRecord,
    InventoryCopy,
    Order,
    OrderItem,
    Portfolio,
    PortfolioItem,
    User,
)
from app.models.p92_import_line_cover import P92ImportLineCoverResolution
from app.services.user_collection_reset_plan import (
    DeletePlanStep,
    build_collection_reset_plan,
    enrich_integrity_error,
    parse_fk_failure,
)
from app.services.user_collection_reset_scope import (
    UserCollectionScope,
    build_user_collection_scope,
)

logger = logging.getLogger(__name__)


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
    plan: list[DeletePlanStep] = field(default_factory=list)

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
        fk_constraint: str | None = None,
        referencing_table: str | None = None,
        suggested_missing_child: str | None = None,
    ) -> None:
        super().__init__(message)
        self.failed_table = failed_table
        self.message = message
        self.summaries = summaries
        self.cause = cause
        self.fk_constraint = fk_constraint
        self.referencing_table = referencing_table
        self.suggested_missing_child = suggested_missing_child
        self.traceback = "".join(traceback.format_exception(type(cause), cause, cause.__traceback__)) if cause else None


def build_reset_delete_plan(*, validate: bool = True) -> list[DeletePlanStep]:
    return build_collection_reset_plan(validate=validate)


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


def _count_rows(connection: Connection, step: DeletePlanStep, scope: UserCollectionScope) -> int:
    predicate = step.predicate(scope)
    return int(connection.execute(select(func.count()).select_from(step.model.__table__).where(predicate)).scalar_one())


def _delete_rows(connection: Connection, step: DeletePlanStep, scope: UserCollectionScope) -> int:
    result = connection.execute(delete(step.model).where(step.predicate(scope)))
    return int(result.rowcount or 0)


COLLECTION_RESET_CONFIRMATION_PHRASE = "DELETE MY COLLECTION"


def remaining_collection_row_counts(session: Session, *, user_id: int) -> dict[str, int]:
    """Counts of user-owned collection rows after a reset (or preview baseline)."""
    from app.models import GmailAccount, RetailerOrderSnapshot

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
    portfolio_ids = tuple(
        int(value)
        for value in session.scalars(select(Portfolio.id).where(Portfolio.owner_user_id == user_id)).all()
    )
    portfolio_items = 0
    if portfolio_ids:
        portfolio_items = int(
            session.scalar(
                select(func.count()).select_from(PortfolioItem).where(PortfolioItem.portfolio_id.in_(portfolio_ids))
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
    plan = build_reset_delete_plan(validate=True)
    summaries: list[TableDeleteSummary] = []

    engine = session.get_bind()
    if execute:
        logger.info(
            "collection_reset execute start user_id=%s email=%s inventory=%s orders=%s drafts=%s plan_steps=%s",
            user.id,
            user.email,
            len(scope.inventory_ids),
            len(scope.order_ids),
            len(scope.draft_import_ids),
            len(plan),
        )
        try:
            with engine.begin() as connection:
                _break_delete_cycles(connection, scope)
                for step in plan:
                    targeted = _count_rows(connection, step, scope)
                    step.row_count = targeted
                    logger.info(
                        "collection_reset deleting table=%s order=%s scope=%s targeted=%s depends_on=%s",
                        step.table_name,
                        step.order,
                        step.scope_reason,
                        targeted,
                        step.depends_on,
                    )
                    if targeted == 0:
                        continue
                    try:
                        deleted = _delete_rows(connection, step, scope)
                    except Exception as exc:
                        fk_constraint, referencing_table, suggested_child = parse_fk_failure(exc)
                        message = enrich_integrity_error(exc) if isinstance(exc, IntegrityError) else str(exc)
                        logger.exception(
                            "collection_reset failed table=%s targeted=%s deleted_before=%s",
                            step.table_name,
                            targeted,
                            sum(row.row_count for row in summaries),
                        )
                        raise UserCollectionResetError(
                            failed_table=step.table_name,
                            message=message,
                            summaries=list(summaries),
                            cause=exc,
                            fk_constraint=fk_constraint,
                            referencing_table=referencing_table,
                            suggested_missing_child=suggested_child,
                        ) from exc
                    logger.info(
                        "collection_reset deleted table=%s rows=%s",
                        step.table_name,
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
            for step in plan:
                count = _count_rows(connection, step, scope)
                step.row_count = count
                if count:
                    summaries.append(TableDeleteSummary(label=step.label, row_count=count))
                    logger.debug(
                        "collection_reset preview table=%s order=%s scope=%s count=%s",
                        step.table_name,
                        step.order,
                        step.scope_reason,
                        count,
                    )

    return UserCollectionResetResult(
        user_id=int(user.id),
        email=user.email,
        dry_run=not execute,
        table_summaries=summaries,
        plan=plan,
    )
