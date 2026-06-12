from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
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
    friendly_delete_summary,
    remaining_collection_row_counts,
    reset_user_collection_data,
)

account_v1_router = APIRouter(prefix="/api/v1/account", tags=["Account API v1"])


def attach_account_layer(app: FastAPI) -> None:
    app.include_router(account_v1_router)


def _table_counts(result) -> list[CollectionResetTableCount]:
    return [
        CollectionResetTableCount(label=row.label, row_count=row.row_count) for row in result.table_summaries
    ]


def _summary_from_result(result) -> CollectionResetSummary:
    return CollectionResetSummary(**friendly_delete_summary(result.table_summaries))


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
    result = reset_user_collection_data(session, user=current_user, execute=False)
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
) -> CollectionResetExecuteResponse:
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
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Collection reset failed.",
        ) from exc

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
    )
