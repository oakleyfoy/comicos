from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Response, UploadFile, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import DraftImport, User
from app.schemas.retailer_accounts import (
    MidtownHtmlImportDebugResponse,
    MidtownHtmlImportResponse,
    RetailerAccountCreate,
    RetailerAccountRead,
    RetailerAccountsListResponse,
    RetailerLocalSyncCompleteRequest,
    RetailerLocalSyncStartRequest,
    RetailerLocalSyncStartResponse,
    RetailerAccountSyncRequest,
    RetailerAccountSyncResponse,
    RetailerAccountTestResponse,
    RetailerAccountUpdate,
    RetailerOrderItemSnapshotRead,
    RetailerOrderListResponse,
    RetailerOrderSnapshotRead,
    RetailerSyncRunListResponse,
    RetailerSyncRunRead,
)
from app.services.retailer_sync.midtown_html_import import (
    MAX_HTML_BYTES,
    MidtownHtmlImportError,
    debug_midtown_saved_html,
    import_midtown_order_from_html,
)
from app.schemas.imports import DraftImportRead
from app.services.retailer_accounts import (
    build_retailer_order_quality_summary,
    complete_retailer_account_local_sync,
    confirm_retailer_order,
    delete_retailer_account,
    get_retailer_order_review_draft_id,
    get_retailer_account_for_user_or_404,
    get_retailer_order_for_user_or_404,
    list_retailer_accounts,
    list_retailer_order_items,
    list_retailer_orders,
    list_retailer_sync_runs,
    masked_username_for_account,
    run_retailer_account_sync,
    run_retailer_account_test,
    save_retailer_account,
    start_retailer_account_local_sync,
    update_retailer_account,
)
from app.services.retailer_order_materialization import RetailerOrderMaterializationResult
from app.services.retailer_sync.retailer_import_enrichment import enrich_drafts_from_retailer_orders
from app.services.imports import serialize_import

retailer_accounts_v1_router = APIRouter(
    prefix="/api/v1", tags=["Retailer Accounts API v1 (P91-01)"]
)


def attach_retailer_accounts_layer(app: FastAPI) -> None:
    app.include_router(retailer_accounts_v1_router)


def _serialize_account(account) -> RetailerAccountRead:
    return RetailerAccountRead(
        id=int(account.id),
        retailer=account.retailer,
        display_name=account.display_name,
        masked_username=masked_username_for_account(account),
        credential_version=account.credential_version,
        status=account.status,
        sync_enabled=account.sync_enabled,
        last_sync_at=account.last_sync_at,
        last_success_at=account.last_success_at,
        last_error=account.last_error,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _serialize_run(run) -> RetailerSyncRunRead:
    return RetailerSyncRunRead.model_validate(run)


def _serialize_order_item(item) -> RetailerOrderItemSnapshotRead:
    return RetailerOrderItemSnapshotRead.model_validate(item)


def _serialize_order(
    order,
    *,
    session: Session,
    materialization: RetailerOrderMaterializationResult | None = None,
) -> RetailerOrderSnapshotRead:
    items = list_retailer_order_items(session, order_snapshot_id=int(order.id))
    draft_import_id = get_retailer_order_review_draft_id(
        session,
        owner_user_id=int(order.owner_user_id),
        retailer_order_number=order.retailer_order_number,
    )
    quality_summary = build_retailer_order_quality_summary(session, order=order, items=items)
    raw = order.raw_snapshot_json if isinstance(order.raw_snapshot_json, dict) else {}
    linked_order_id = materialization.order_id if materialization else raw.get("comicos_linked_order_id")
    linked_import_id = materialization.import_id if materialization else raw.get("comicos_linked_import_id")
    inventory_copies_created = (
        materialization.inventory_copies_created if materialization else raw.get("comicos_inventory_copies_created")
    )
    total_ordered_quantity = (
        materialization.total_ordered_quantity if materialization else raw.get("comicos_total_ordered_quantity")
    )
    portfolio_items_added = (
        materialization.portfolio_items_added if materialization else raw.get("comicos_portfolio_items_added")
    )
    return RetailerOrderSnapshotRead(
        id=int(order.id),
        retailer_account_id=order.retailer_account_id,
        retailer=order.retailer,
        retailer_order_number=order.retailer_order_number,
        order_date=order.order_date,
        order_status=order.order_status,
        order_total=order.order_total,
        source_url=order.source_url,
        draft_import_id=draft_import_id,
        review_status=quality_summary["review_status"],
        item_count=quality_summary["item_count"],
        cover_image_count=quality_summary["cover_image_count"],
        product_url_count=quality_summary["product_url_count"],
        price_count=quality_summary["price_count"],
        release_date_count=quality_summary["release_date_count"],
        linked_order_id=int(linked_order_id) if linked_order_id is not None else None,
        linked_import_id=int(linked_import_id) if linked_import_id is not None else None,
        inventory_copies_created=int(inventory_copies_created) if inventory_copies_created is not None else None,
        total_ordered_quantity=int(total_ordered_quantity) if total_ordered_quantity is not None else None,
        portfolio_items_added=int(portfolio_items_added) if portfolio_items_added is not None else None,
        capture_quality_summary_json=quality_summary["capture_quality_summary_json"],
        parser_quality_summary_json=quality_summary["parser_quality_summary_json"],
        raw_fields_summary_json=quality_summary["raw_fields_summary_json"],
        updated_at=order.updated_at,
        items=[_serialize_order_item(item) for item in items],
    )


@retailer_accounts_v1_router.get("/retailer-accounts", response_model=RetailerAccountsListResponse)
def get_retailer_accounts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerAccountsListResponse:
    assert current_user.id is not None
    items = list_retailer_accounts(session, owner_user_id=int(current_user.id))
    return RetailerAccountsListResponse(items=[_serialize_account(item) for item in items])


@retailer_accounts_v1_router.post(
    "/retailer-accounts",
    response_model=RetailerAccountRead,
    status_code=status.HTTP_201_CREATED,
)
def create_retailer_account(
    payload: RetailerAccountCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerAccountRead:
    assert current_user.id is not None
    account, created = save_retailer_account(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return _serialize_account(account)


@retailer_accounts_v1_router.patch(
    "/retailer-accounts/{account_id}", response_model=RetailerAccountRead
)
def patch_retailer_account(
    account_id: int,
    payload: RetailerAccountUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerAccountRead:
    assert current_user.id is not None
    account = update_retailer_account(
        session,
        owner_user_id=int(current_user.id),
        account_id=account_id,
        payload=payload,
    )
    return _serialize_account(account)


@retailer_accounts_v1_router.delete(
    "/retailer-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_retailer_account(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    delete_retailer_account(session, owner_user_id=int(current_user.id), account_id=account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@retailer_accounts_v1_router.post(
    "/retailer-accounts/{account_id}/test", response_model=RetailerAccountTestResponse
)
def test_retailer_account(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerAccountTestResponse:
    assert current_user.id is not None
    result = run_retailer_account_test(
        session,
        owner_user_id=int(current_user.id),
        account_id=account_id,
    )
    return RetailerAccountTestResponse(
        account=_serialize_account(result.account),
        run=_serialize_run(result.run),
    )


@retailer_accounts_v1_router.post(
    "/retailer-accounts/{account_id}/sync", response_model=RetailerAccountSyncResponse
)
def sync_retailer_account(
    account_id: int,
    payload: RetailerAccountSyncRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerAccountSyncResponse:
    assert current_user.id is not None
    result = run_retailer_account_sync(
        session,
        owner_user_id=int(current_user.id),
        account_id=account_id,
        limit_orders=payload.limit_orders,
    )
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=int(current_user.id), account_id=account_id
    )
    recent_orders = list_retailer_orders(session, owner_user_id=int(current_user.id))
    related_orders = [order for order in recent_orders if order.retailer_account_id == account_id][
        : payload.limit_orders
    ]
    return RetailerAccountSyncResponse(
        account=_serialize_account(account),
        run=_serialize_run(result.run),
        orders=[_serialize_order(order, session=session) for order in related_orders],
    )


@retailer_accounts_v1_router.post(
    "/retailer-accounts/{account_id}/local-sync/start",
    response_model=RetailerLocalSyncStartResponse,
)
def start_retailer_local_sync(
    account_id: int,
    payload: RetailerLocalSyncStartRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerLocalSyncStartResponse:
    assert current_user.id is not None
    result = start_retailer_account_local_sync(
        session,
        owner_user_id=int(current_user.id),
        account_id=account_id,
        payload=payload,
    )
    return RetailerLocalSyncStartResponse(
        account=_serialize_account(result.account),
        run=_serialize_run(result.run),
        helper_token=result.helper_token,
        helper_token_expires_at=result.helper_token_expires_at,
        capture_url=result.capture_url,
        capture_mode="extension",
    )


@retailer_accounts_v1_router.post(
    "/retailer-accounts/{account_id}/local-sync/{sync_run_id}/complete",
    response_model=RetailerAccountSyncResponse,
)
def complete_retailer_local_sync(
    account_id: int,
    sync_run_id: int,
    payload: RetailerLocalSyncCompleteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerAccountSyncResponse:
    assert current_user.id is not None
    result = complete_retailer_account_local_sync(
        session,
        owner_user_id=int(current_user.id),
        account_id=account_id,
        sync_run_id=sync_run_id,
        payload=payload,
    )
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=int(current_user.id), account_id=account_id
    )
    recent_orders = list_retailer_orders(session, owner_user_id=int(current_user.id))
    related_orders = [order for order in recent_orders if order.retailer_account_id == account_id][:25]
    return RetailerAccountSyncResponse(
        account=_serialize_account(account),
        run=_serialize_run(result.run),
        orders=[_serialize_order(order, session=session) for order in related_orders],
    )


@retailer_accounts_v1_router.get(
    "/retailer-accounts/{account_id}/sync-runs", response_model=RetailerSyncRunListResponse
)
def get_retailer_sync_runs(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerSyncRunListResponse:
    assert current_user.id is not None
    runs = list_retailer_sync_runs(
        session, owner_user_id=int(current_user.id), account_id=account_id
    )
    return RetailerSyncRunListResponse(items=[_serialize_run(run) for run in runs])


@retailer_accounts_v1_router.get("/retailer-orders", response_model=RetailerOrderListResponse)
def get_retailer_orders(
    retailer: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerOrderListResponse:
    assert current_user.id is not None
    orders = list_retailer_orders(
        session,
        owner_user_id=int(current_user.id),
        retailer=retailer,
        status=status,
    )
    return RetailerOrderListResponse(
        items=[_serialize_order(order, session=session) for order in orders]
    )


async def _read_midtown_html_upload(file: UploadFile) -> str:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file was empty.")
    if len(raw) > MAX_HTML_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large. Save just the Midtown order page as HTML and try again.",
        )
    return raw.decode("utf-8", errors="replace")


def _midtown_html_import_http_error(exc: MidtownHtmlImportError) -> HTTPException:
    payload: dict = {"message": str(exc)}
    if exc.diagnostics:
        payload["diagnostics"] = exc.diagnostics
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=payload)


@retailer_accounts_v1_router.post(
    "/retailer-orders/import/midtown-html/debug",
    response_model=MidtownHtmlImportDebugResponse,
)
async def debug_midtown_order_html_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> MidtownHtmlImportDebugResponse:
    assert current_user.id is not None
    html_text = await _read_midtown_html_upload(file)
    fields = debug_midtown_saved_html(html_text)
    return MidtownHtmlImportDebugResponse(**fields)


@retailer_accounts_v1_router.post(
    "/retailer-orders/import/midtown-html",
    response_model=MidtownHtmlImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_midtown_order_html(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MidtownHtmlImportResponse:
    assert current_user.id is not None
    html_text = await _read_midtown_html_upload(file)
    try:
        order_id, order_number, stats = import_midtown_order_from_html(
            session,
            owner_user_id=int(current_user.id),
            html_text=html_text,
            source_filename=file.filename,
        )
    except MidtownHtmlImportError as exc:
        raise _midtown_html_import_http_error(exc) from exc
    return MidtownHtmlImportResponse(
        order_id=order_id,
        retailer_order_number=order_number,
        item_count=int(stats.get("items_imported", 0)),
    )


@retailer_accounts_v1_router.get(
    "/retailer-orders/{order_id}", response_model=RetailerOrderSnapshotRead
)
def get_retailer_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerOrderSnapshotRead:
    assert current_user.id is not None
    order = get_retailer_order_for_user_or_404(
        session, owner_user_id=int(current_user.id), order_id=order_id
    )
    return _serialize_order(order, session=session)


@retailer_accounts_v1_router.post(
    "/retailer-orders/{order_id}/confirm",
    response_model=RetailerOrderSnapshotRead,
)
def confirm_retailer_order_route(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RetailerOrderSnapshotRead:
    assert current_user.id is not None
    order, materialization = confirm_retailer_order(
        session,
        owner_user_id=int(current_user.id),
        order_id=order_id,
    )
    return _serialize_order(order, session=session, materialization=materialization)


@retailer_accounts_v1_router.post(
    "/retailer-orders/{order_id}/review-draft",
    response_model=DraftImportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_retailer_order_review_draft(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    assert current_user.id is not None
    order = get_retailer_order_for_user_or_404(
        session, owner_user_id=int(current_user.id), order_id=order_id
    )
    account = get_retailer_account_for_user_or_404(
        session,
        owner_user_id=int(current_user.id),
        account_id=int(order.retailer_account_id),
    )
    touched_import_ids = enrich_drafts_from_retailer_orders(
        session,
        account=account,
        order_snapshots=[order],
    )
    if not touched_import_ids:
        raise HTTPException(status_code=404, detail="No review draft was created for this order.")
    draft_import = session.get(DraftImport, touched_import_ids[0])
    if draft_import is None:
        raise HTTPException(status_code=404, detail="Review draft not found.")
    return serialize_import(session, draft_import)
