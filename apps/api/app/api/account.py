from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.account import (
    CollectionResetExecuteRequest,
    CollectionResetExecuteResponse,
    CollectionResetPreviewResponse,
    CollectionResetRemaining,
    CollectionResetSummary,
    CollectionResetTableCount,
)
from app.services.user_collection_reset import (
    COLLECTION_RESET_CONFIRMATION_PHRASE,
    UserCollectionResetError,
    friendly_delete_summary,
    remaining_collection_row_counts,
    reset_user_collection_data,
)

logger = logging.getLogger(__name__)

account_v1_router = APIRouter(prefix="/api/v1/account", tags=["Account API v1"])


def attach_account_layer(app: FastAPI) -> None:
    app.include_router(account_v1_router)


def _table_counts(result) -> list[CollectionResetTableCount]:
    return [
        CollectionResetTableCount(label=row.label, row_count=row.row_count) for row in result.table_summaries
    ]


def _table_counts_from_summaries(summaries) -> list[CollectionResetTableCount]:
    return [CollectionResetTableCount(label=row.label, row_count=row.row_count) for row in summaries]


def _summary_from_result(result) -> CollectionResetSummary:
    return CollectionResetSummary(**friendly_delete_summary(result.table_summaries))


def _summary_from_summaries(summaries) -> CollectionResetSummary:
    return CollectionResetSummary(**friendly_delete_summary(summaries))


def _remaining_model(counts: dict[str, int]) -> CollectionResetRemaining:
    return CollectionResetRemaining(
        inventory_copies=counts.get("inventory_copies", 0),
        orders=counts.get("orders", 0),
        draft_imports=counts.get("draft_imports", 0),
        retailer_order_snapshots=counts.get("retailer_order_snapshots", 0),
        gmail_import_records=counts.get("gmail_import_records", 0),
        portfolio_items=counts.get("portfolio_items", 0),
        portfolios=counts.get("portfolios", 0),
    )


@account_v1_router.post(
    "/reset-collection-data/preview",
    response_model=CollectionResetPreviewResponse,
)
def preview_reset_collection_data(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionResetPreviewResponse:
    """Dry-run: report what would be deleted without mutating data."""
    try:
        result = reset_user_collection_data(session, user=current_user, execute=False)
    except Exception:
        logger.exception("collection_reset preview failed user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load collection reset preview. Try again or use Settings → Collections to manage test workspaces.",
        ) from None
    session.expire_all()
    remaining = remaining_collection_row_counts(session, user_id=int(current_user.id or 0))
    return CollectionResetPreviewResponse(
        status="preview",
        dry_run=True,
        summary=_summary_from_result(result),
        table_counts=_table_counts(result),
        remaining=_remaining_model(remaining),
    )


@account_v1_router.post(
    "/reset-collection-data",
    response_model=CollectionResetExecuteResponse,
)
def execute_reset_collection_data(
    payload: CollectionResetExecuteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete the authenticated user's collection and import data."""
    if not payload.acknowledge_permanent_delete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="acknowledge_permanent_delete must be true.",
        )
    if payload.confirmation_phrase.strip() != COLLECTION_RESET_CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'confirmation_phrase must exactly match "{COLLECTION_RESET_CONFIRMATION_PHRASE}".',
        )

    try:
        result = reset_user_collection_data(session, user=current_user, execute=True)
    except UserCollectionResetError as exc:
        session.expire_all()
        remaining = remaining_collection_row_counts(session, user_id=int(current_user.id or 0))
        if exc.traceback:
            logger.error(
                "collection_reset failed user_id=%s table=%s error=%s\n%s",
                current_user.id,
                exc.failed_table,
                exc.message,
                exc.traceback,
            )
        response = CollectionResetExecuteResponse(
            status="partial_failure",
            dry_run=False,
            deleted=_summary_from_summaries(exc.summaries),
            deleted_by_table=_table_counts_from_summaries(exc.summaries),
            remaining=_remaining_model(remaining),
            failed_table=exc.failed_table,
            error=exc.message,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(mode="json"),
        )
    except Exception as exc:
        session.expire_all()
        remaining = remaining_collection_row_counts(session, user_id=int(current_user.id or 0))
        logger.exception("collection_reset unexpected failure user_id=%s", current_user.id)
        response = CollectionResetExecuteResponse(
            status="partial_failure",
            dry_run=False,
            deleted=CollectionResetSummary(),
            deleted_by_table=[],
            remaining=_remaining_model(remaining),
            failed_table="unknown",
            error=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(mode="json"),
        )

    session.expire_all()
    remaining = remaining_collection_row_counts(session, user_id=int(current_user.id or 0))
    remaining_model = _remaining_model(remaining)
    success = (
        remaining_model.inventory_copies == 0
        and remaining_model.orders == 0
        and remaining_model.draft_imports == 0
        and remaining_model.retailer_order_snapshots == 0
    )
    return CollectionResetExecuteResponse(
        status="success" if success else "partial_failure",
        dry_run=False,
        deleted=_summary_from_result(result),
        deleted_by_table=_table_counts(result),
        remaining=remaining_model,
        failed_table=None if success else "remaining_rows",
        error=None if success else "Some collection rows remain after reset.",
    )
