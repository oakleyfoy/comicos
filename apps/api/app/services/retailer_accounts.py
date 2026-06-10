from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models import (
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    RetailerSyncRun,
)
from app.schemas.retailer_accounts import (
    RetailerAccountCreate,
    RetailerAccountUpdate,
    RetailerLocalSyncCompleteRequest,
    RetailerLocalSyncStartRequest,
)
from app.services.retailer_credentials import (
    encrypt_retailer_password,
    mask_retailer_username,
    validate_retailer_credential_key,
)
from app.services.retailer_sync.midtown_account_sync import (
    MidtownLocalSyncCapture,
    MidtownLocalSyncStart,
    MidtownSyncResult,
    complete_midtown_browser_sync,
    start_midtown_browser_sync,
    sync_midtown_account,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_sync_run_for_account(session: Session, *, account_id: int) -> RetailerSyncRun | None:
    return session.exec(
        select(RetailerSyncRun)
        .where(RetailerSyncRun.retailer_account_id == account_id)
        .order_by(RetailerSyncRun.started_at.desc(), RetailerSyncRun.id.desc())
    ).first()


def _retry_cooldown_message(summary_json: dict | None) -> str | None:
    if not isinstance(summary_json, dict):
        return None
    error_code = str(summary_json.get("error_code") or "").strip().lower()
    retry_allowed_at = str(summary_json.get("retry_allowed_at") or "").strip()
    if error_code != "captcha_or_security" or not retry_allowed_at:
        return None
    try:
        retry_at = datetime.fromisoformat(retry_allowed_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if retry_at <= utc_now():
        return None
    retry_text = retry_at.astimezone(timezone.utc).isoformat()
    return (
        "Midtown recently presented a CAPTCHA or security challenge. "
        f"Please wait until {retry_text} before retrying."
    )


def get_retailer_account_for_user_or_404(
    session: Session,
    *,
    owner_user_id: int,
    account_id: int,
) -> RetailerAccount:
    account = session.get(RetailerAccount, account_id)
    if account is None or account.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Retailer account not found.")
    return account


def list_retailer_accounts(session: Session, *, owner_user_id: int) -> list[RetailerAccount]:
    return session.exec(
        select(RetailerAccount)
        .where(RetailerAccount.owner_user_id == owner_user_id)
        .order_by(RetailerAccount.retailer.asc(), RetailerAccount.id.asc())
    ).all()


def save_retailer_account(
    session: Session,
    *,
    owner_user_id: int,
    payload: RetailerAccountCreate,
) -> tuple[RetailerAccount, bool]:
    validate_retailer_credential_key()
    existing = session.exec(
        select(RetailerAccount).where(
            RetailerAccount.owner_user_id == owner_user_id,
            RetailerAccount.retailer == payload.retailer,
        )
    ).first()
    created = existing is None
    if existing is None:
        existing = RetailerAccount(
            owner_user_id=owner_user_id,
            retailer=payload.retailer,
            username=payload.username.strip(),
            encrypted_password="",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    existing.display_name = payload.display_name
    existing.username = payload.username.strip()
    existing.encrypted_password = encrypt_retailer_password(payload.password)
    existing.credential_version = 1
    existing.sync_enabled = payload.sync_enabled
    existing.status = "connected"
    existing.last_error = None
    existing.updated_at = utc_now()
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing, created


def update_retailer_account(
    session: Session,
    *,
    owner_user_id: int,
    account_id: int,
    payload: RetailerAccountUpdate,
) -> RetailerAccount:
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=owner_user_id, account_id=account_id
    )
    if payload.username is not None:
        account.username = payload.username.strip()
    if payload.password is not None:
        validate_retailer_credential_key()
        account.encrypted_password = encrypt_retailer_password(payload.password)
        account.credential_version = 1
    if payload.display_name is not None:
        account.display_name = payload.display_name
    if payload.sync_enabled is not None:
        account.sync_enabled = payload.sync_enabled
    if payload.status is not None:
        account.status = payload.status
    if payload.username is not None or payload.password is not None:
        account.status = "connected"
        account.last_error = None
    account.updated_at = utc_now()
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def delete_retailer_account(session: Session, *, owner_user_id: int, account_id: int) -> None:
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=owner_user_id, account_id=account_id
    )
    order_ids = session.exec(
        select(RetailerOrderSnapshot.id).where(
            RetailerOrderSnapshot.retailer_account_id == account.id
        )
    ).all()
    if order_ids:
        session.exec(
            delete(RetailerOrderItemSnapshot).where(
                RetailerOrderItemSnapshot.retailer_order_snapshot_id.in_(order_ids)
            )
        )
        session.exec(
            delete(RetailerOrderSnapshot).where(
                RetailerOrderSnapshot.retailer_account_id == account.id
            )
        )
    session.exec(delete(RetailerSyncRun).where(RetailerSyncRun.retailer_account_id == account.id))
    session.delete(account)
    session.commit()


def list_retailer_sync_runs(
    session: Session,
    *,
    owner_user_id: int,
    account_id: int,
) -> list[RetailerSyncRun]:
    get_retailer_account_for_user_or_404(
        session, owner_user_id=owner_user_id, account_id=account_id
    )
    return session.exec(
        select(RetailerSyncRun)
        .where(RetailerSyncRun.retailer_account_id == account_id)
        .order_by(RetailerSyncRun.started_at.desc(), RetailerSyncRun.id.desc())
    ).all()


def run_retailer_account_test(
    session: Session,
    *,
    owner_user_id: int,
    account_id: int,
) -> MidtownSyncResult:
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=owner_user_id, account_id=account_id
    )
    latest_run = _latest_sync_run_for_account(session, account_id=account_id)
    cooldown_message = _retry_cooldown_message(latest_run.summary_json if latest_run else None)
    if cooldown_message:
        raise HTTPException(status_code=409, detail=cooldown_message)
    return sync_midtown_account(session, account=account, limit_orders=1, test_only=True)


def run_retailer_account_sync(
    session: Session,
    *,
    owner_user_id: int,
    account_id: int,
    limit_orders: int,
) -> MidtownSyncResult:
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=owner_user_id, account_id=account_id
    )
    latest_run = _latest_sync_run_for_account(session, account_id=account_id)
    cooldown_message = _retry_cooldown_message(latest_run.summary_json if latest_run else None)
    if cooldown_message:
        raise HTTPException(status_code=409, detail=cooldown_message)
    return sync_midtown_account(
        session, account=account, limit_orders=limit_orders, test_only=False
    )


def start_retailer_account_local_sync(
    session: Session,
    *,
    owner_user_id: int,
    account_id: int,
    payload: RetailerLocalSyncStartRequest,
) -> MidtownLocalSyncStart:
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=owner_user_id, account_id=account_id
    )
    return start_midtown_browser_sync(
        session,
        account=account,
        limit_orders=payload.limit_orders,
    )


def complete_retailer_account_local_sync(
    session: Session,
    *,
    owner_user_id: int,
    account_id: int,
    sync_run_id: int,
    payload: RetailerLocalSyncCompleteRequest,
) -> MidtownSyncResult:
    account = get_retailer_account_for_user_or_404(
        session, owner_user_id=owner_user_id, account_id=account_id
    )
    return complete_midtown_browser_sync(
        session,
        account=account,
        sync_run_id=sync_run_id,
        helper_token=payload.helper_token,
        history_html=payload.history_html,
        detail_pages=[
            MidtownLocalSyncCapture(
                detail_url=page.detail_url,
                html=page.html,
                retailer_order_number=page.retailer_order_number,
                fallback_order_number=page.fallback_order_number,
            )
            for page in payload.detail_pages
        ],
    )


def list_retailer_orders(
    session: Session,
    *,
    owner_user_id: int,
) -> list[RetailerOrderSnapshot]:
    return session.exec(
        select(RetailerOrderSnapshot)
        .where(RetailerOrderSnapshot.owner_user_id == owner_user_id)
        .order_by(RetailerOrderSnapshot.order_date.desc(), RetailerOrderSnapshot.id.desc())
    ).all()


def get_retailer_order_for_user_or_404(
    session: Session,
    *,
    owner_user_id: int,
    order_id: int,
) -> RetailerOrderSnapshot:
    order = session.get(RetailerOrderSnapshot, order_id)
    if order is None or order.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Retailer order not found.")
    return order


def list_retailer_order_items(
    session: Session,
    *,
    order_snapshot_id: int,
) -> list[RetailerOrderItemSnapshot]:
    return session.exec(
        select(RetailerOrderItemSnapshot)
        .where(RetailerOrderItemSnapshot.retailer_order_snapshot_id == order_snapshot_id)
        .order_by(RetailerOrderItemSnapshot.id.asc())
    ).all()


def masked_username_for_account(account: RetailerAccount) -> str:
    return mask_retailer_username(account.username)
