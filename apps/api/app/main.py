from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings, validate_production_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_session
from app.models import User
from app.schemas.ai import ParseOrderRequest, ParseOrderResponse
from app.schemas.auth import TokenResponse, UserLogin, UserRead, UserRegister
from app.schemas.debug import RuntimeDebugResponse
from app.schemas.gmail import (
    GmailConnectStartResponse,
    GmailDisconnectResponse,
    GmailImportedDraftRead,
    GmailStatusResponse,
    GmailSyncEnqueueResponse,
    GmailSyncSettingsUpdate,
    GmailSyncStatusResponse,
)
from app.schemas.imports import (
    DraftImportConfirmResponse,
    DraftImportCreate,
    DraftImportListResponse,
    DraftImportRead,
    DraftImportStatus,
    DraftImportUpdate,
    ManualDraftImportCreate,
)
from app.schemas.inventory import (
    BulkInventoryUpdateRequest,
    BulkInventoryUpdateResponse,
    InventoryDetailResponse,
    InventoryFmvSnapshotResponse,
    InventoryListResponse,
    InventoryRow,
    InventorySummaryResponse,
    InventoryUpdate,
    PortfolioPerformanceResponse,
)
from app.schemas.jobs import ImportParseJobEnqueueResponse, ImportParseJobStatusResponse
from app.schemas.ops import OpsDashboardResponse
from app.schemas.orders import (
    OrderCreate,
    OrderCreateResponse,
    OrderDetailResponse,
    OrderListResponse,
)
from app.services.ai_order_parser import (
    AiOrderParserError,
    AiOrderParserNotConfiguredError,
    parse_order_draft_from_text,
)
from app.services.background_jobs import (
    enqueue_gmail_sync_job_for_user,
    enqueue_import_parse_job_for_user,
    get_gmail_sync_job_status_for_user,
    get_import_parse_job_status_for_user,
)
from app.services.gmail_ingestion import (
    GmailIntegrationError,
    GmailIntegrationNotConfiguredError,
    GmailNotConnectedError,
    build_gmail_connect_authorization_url,
    connect_gmail_account_for_user,
    decode_gmail_connect_state,
    disconnect_gmail_for_user,
    get_gmail_status_for_user,
    get_gmail_sync_status_for_user,
    serialize_gmail_import_drafts,
    update_gmail_sync_settings_for_user,
)
from app.services.imports import (
    confirm_import_for_user,
    create_import_for_user,
    create_manual_import_for_user,
    discard_import_for_user,
    get_import_for_user,
    list_imports_for_user,
    update_import_for_user,
)
from app.services.inventory import (
    bulk_update_inventory,
    get_inventory_copy_detail,
    get_inventory_fmv_history,
    inventory_summary,
    list_inventory,
    portfolio_performance,
    update_inventory_copy,
)
from app.services.ops_admin import build_ops_dashboard, ensure_ops_admin_access
from app.services.orders import (
    create_order_for_user,
    get_order_detail_for_user,
    list_orders_for_user,
)
from app.services.runtime_debug import build_runtime_debug_response

settings = get_settings()
validate_production_settings(settings)

app = FastAPI(title="ComicOS API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/health/db")
def health_db(session: Session = Depends(get_session)) -> dict[str, bool | str]:
    try:
        session.exec(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database connection failed") from exc

    return {"ok": True, "database": "connected"}


@app.get("/health/redis")
def health_redis() -> dict[str, bool | str]:
    from redis.exceptions import RedisError

    from app.tasks.queue import get_redis_connection

    try:
        get_redis_connection().ping()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis connection failed") from exc

    return {"ok": True, "redis": "connected"}


@app.get("/health/worker")
def health_worker() -> dict[str, object]:
    from redis.exceptions import RedisError
    from rq import Worker

    from app.tasks.queue import get_redis_connection, get_worker_queue_names

    try:
        connection = get_redis_connection()
        workers = Worker.all(connection=connection)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Worker visibility unavailable") from exc

    return {
        "ok": True,
        "worker_count": len(workers),
        "workers": [worker.name for worker in workers],
        "queues": get_worker_queue_names(),
    }


@app.get("/debug/runtime", response_model=RuntimeDebugResponse, include_in_schema=False)
def debug_runtime(settings: Settings = Depends(get_settings)) -> RuntimeDebugResponse:
    if not settings.debug_runtime:
        raise HTTPException(status_code=404, detail="Not Found")

    return build_runtime_debug_response(settings)


@app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, session: Session = Depends(get_session)) -> User:
    existing_user = session.exec(select(User).where(User.email == payload.email)).first()
    if existing_user is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return user


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=access_token)


@app.get("/auth/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get("/ops/dashboard", response_model=OpsDashboardResponse, include_in_schema=False)
def ops_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OpsDashboardResponse:
    ensure_ops_admin_access(current_user, settings)
    return build_ops_dashboard(session)


@app.get("/gmail/connect/start", response_model=GmailConnectStartResponse)
def gmail_connect_start(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> GmailConnectStartResponse:
    try:
        authorization_url = build_gmail_connect_authorization_url(
            current_user,
            redirect_origin=request.headers.get("origin"),
            redirect_path="/settings/integrations",
        )
    except GmailIntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return GmailConnectStartResponse(authorization_url=authorization_url)


@app.get("/gmail/connect/callback")
def gmail_connect_callback(
    code: str,
    state: str,
    session: Session = Depends(get_session),
):
    state_payload = decode_gmail_connect_state(state)
    user = session.get(User, state_payload["user_id"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        connect_gmail_account_for_user(session=session, current_user=user, code=code)
    except GmailIntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    redirect_origin = state_payload.get("redirect_origin") or "http://127.0.0.1:5173"
    redirect_path = state_payload.get("redirect_path") or "/settings/integrations"
    redirect_url = f"{redirect_origin.rstrip('/')}{redirect_path}?gmail=connected"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@app.get("/gmail/status", response_model=GmailStatusResponse)
def gmail_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailStatusResponse:
    return get_gmail_status_for_user(session=session, current_user=current_user)


@app.post("/gmail/disconnect", response_model=GmailDisconnectResponse)
def gmail_disconnect(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailDisconnectResponse:
    disconnect_gmail_for_user(session=session, current_user=current_user)
    return GmailDisconnectResponse(disconnected=True)


@app.get("/gmail/sync/status", response_model=GmailSyncStatusResponse)
def gmail_sync_status_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailSyncStatusResponse:
    return get_gmail_sync_status_for_user(session=session, current_user=current_user)


@app.patch("/gmail/sync/settings", response_model=GmailSyncStatusResponse)
def gmail_sync_settings(
    payload: GmailSyncSettingsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailSyncStatusResponse:
    try:
        return update_gmail_sync_settings_for_user(
            session=session,
            current_user=current_user,
            auto_sync_enabled=payload.auto_sync_enabled,
        )
    except GmailNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/gmail/imports", response_model=list[GmailImportedDraftRead])
def gmail_imports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[GmailImportedDraftRead]:
    return serialize_gmail_import_drafts(session=session, current_user=current_user)


@app.post(
    "/gmail/sync",
    response_model=GmailSyncEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def gmail_sync(current_user: User = Depends(get_current_user)) -> GmailSyncEnqueueResponse:
    try:
        return enqueue_gmail_sync_job_for_user(current_user=current_user)
    except GmailIntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GmailNotConnectedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/gmail/sync/{job_id}", response_model=ImportParseJobStatusResponse)
def gmail_sync_status(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImportParseJobStatusResponse:
    return get_gmail_sync_job_status_for_user(
        session=session,
        current_user=current_user,
        job_id=job_id,
    )


@app.post("/ai/parse-order", response_model=ParseOrderResponse)
def parse_order(
    payload: ParseOrderRequest,
    current_user: User = Depends(get_current_user),
) -> ParseOrderResponse:
    del current_user
    try:
        return parse_order_draft_from_text(payload.raw_text)
    except AiOrderParserNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AiOrderParserError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/imports", response_model=DraftImportListResponse)
def get_imports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status: DraftImportStatus | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "desc",
) -> DraftImportListResponse:
    return list_imports_for_user(
        session=session,
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.post("/imports", response_model=DraftImportRead, status_code=status.HTTP_201_CREATED)
def create_import(
    payload: DraftImportCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    try:
        return create_import_for_user(session=session, current_user=current_user, payload=payload)
    except AiOrderParserNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AiOrderParserError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/imports/manual", response_model=DraftImportRead, status_code=status.HTTP_201_CREATED)
def create_manual_import(
    payload: ManualDraftImportCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return create_manual_import_for_user(
        session=session,
        current_user=current_user,
        payload=payload,
    )


@app.post(
    "/imports/parse-jobs",
    response_model=ImportParseJobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_import_parse_job(
    payload: DraftImportCreate,
    current_user: User = Depends(get_current_user),
) -> ImportParseJobEnqueueResponse:
    try:
        return enqueue_import_parse_job_for_user(current_user=current_user, payload=payload)
    except AiOrderParserNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/imports/parse-jobs/{job_id}", response_model=ImportParseJobStatusResponse)
def get_import_parse_job_status(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImportParseJobStatusResponse:
    return get_import_parse_job_status_for_user(
        session=session,
        current_user=current_user,
        job_id=job_id,
    )


@app.get("/imports/{import_id}", response_model=DraftImportRead)
def get_import(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return get_import_for_user(session=session, current_user=current_user, import_id=import_id)


@app.patch("/imports/{import_id}", response_model=DraftImportRead)
def patch_import(
    import_id: int,
    payload: DraftImportUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return update_import_for_user(
        session=session,
        current_user=current_user,
        import_id=import_id,
        payload=payload,
    )


@app.post("/imports/{import_id}/confirm", response_model=DraftImportConfirmResponse)
def confirm_import(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportConfirmResponse:
    return confirm_import_for_user(session=session, current_user=current_user, import_id=import_id)


@app.post("/imports/{import_id}/discard", response_model=DraftImportRead)
def discard_import(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return discard_import_for_user(session=session, current_user=current_user, import_id=import_id)


@app.post("/orders", response_model=OrderCreateResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OrderCreateResponse:
    return create_order_for_user(session=session, current_user=current_user, payload=payload)


@app.get("/orders", response_model=OrderListResponse)
def get_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    retailer: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "desc",
) -> OrderListResponse:
    return list_orders_for_user(
        session=session,
        current_user=current_user,
        page=page,
        page_size=page_size,
        retailer=retailer,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.get("/orders/{order_id}", response_model=OrderDetailResponse)
def get_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OrderDetailResponse:
    return get_order_detail_for_user(session=session, current_user=current_user, order_id=order_id)


@app.get("/inventory", response_model=InventoryListResponse)
def get_inventory(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: str | None = None,
    publisher: str | None = None,
    hold_status: str | None = None,
    grade_status: str | None = None,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "asc",
) -> InventoryListResponse:
    return list_inventory(
        session=session,
        current_user=current_user,
        page=page,
        page_size=page_size,
        search=search,
        publisher=publisher,
        hold_status=hold_status,
        grade_status=grade_status,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.get("/inventory/summary", response_model=InventorySummaryResponse)
def get_inventory_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventorySummaryResponse:
    return inventory_summary(session=session, current_user=current_user)


@app.get("/inventory/{inventory_copy_id}", response_model=InventoryDetailResponse)
def get_inventory_copy(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryDetailResponse:
    return get_inventory_copy_detail(
        session=session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
    )


@app.get(
    "/inventory/{inventory_copy_id}/fmv-history",
    response_model=list[InventoryFmvSnapshotResponse],
)
def get_inventory_copy_fmv_history(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[InventoryFmvSnapshotResponse]:
    return get_inventory_fmv_history(
        session=session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
    )


@app.get("/portfolio/performance", response_model=PortfolioPerformanceResponse)
def get_portfolio_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioPerformanceResponse:
    return portfolio_performance(session=session, current_user=current_user)


@app.patch("/inventory/bulk", response_model=BulkInventoryUpdateResponse)
def patch_inventory_bulk(
    payload: BulkInventoryUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkInventoryUpdateResponse:
    return bulk_update_inventory(session=session, current_user=current_user, payload=payload)


@app.patch("/inventory/{inventory_copy_id}", response_model=InventoryRow)
def patch_inventory_copy(
    inventory_copy_id: int,
    payload: InventoryUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryRow:
    return update_inventory_copy(
        session=session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
        updates=payload,
    )
