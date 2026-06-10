from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import select
from test_inventory import auth_headers, register_and_login

from app.models import (
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    RetailerSyncRun,
)
from app.services.retailer_credentials import decrypt_retailer_password
from app.services.retailer_sync.midtown_parser import (
    MidtownOrderDetail,
    MidtownOrderHistoryEntry,
    MidtownOrderItem,
)
from app.services.retailer_sync.midtown_account_sync import MidtownSyncResult


def _persist_fake_sync(session, *, account: RetailerAccount) -> MidtownSyncResult:
    run = RetailerSyncRun(
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id),
        retailer=account.retailer,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        orders_seen=1,
        orders_imported=1,
        items_seen=1,
        items_imported=1,
        items_updated=0,
        summary_json={"orders_seen": 1},
    )
    session.add(run)
    order = session.exec(
        select(RetailerOrderSnapshot).where(
            RetailerOrderSnapshot.owner_user_id == account.owner_user_id,
            RetailerOrderSnapshot.retailer_account_id == int(account.id),
            RetailerOrderSnapshot.retailer_order_number == "ABC123",
        )
    ).first()
    if order is None:
        order = RetailerOrderSnapshot(
            owner_user_id=account.owner_user_id,
            retailer_account_id=int(account.id),
            retailer=account.retailer,
            retailer_order_number="ABC123",
            order_date=date(2026, 6, 8),
            order_status="Shipped",
            order_total=Decimal("9.98"),
            raw_snapshot_json={},
        )
        session.add(order)
        session.flush()
        item = RetailerOrderItemSnapshot(
            owner_user_id=account.owner_user_id,
            retailer_order_snapshot_id=int(order.id),
            retailer=account.retailer,
            retailer_order_number="ABC123",
            retailer_item_id="SKU-1",
            title="Immortal Thor #1 Cover A",
            quantity=1,
            unit_price=Decimal("4.99"),
            raw_item_json={},
        )
        session.add(item)
    account.last_sync_at = run.finished_at
    account.last_success_at = run.finished_at
    account.last_error = None
    account.status = "connected"
    session.add(account)
    session.commit()
    session.refresh(account)
    session.refresh(run)
    return MidtownSyncResult(account=account, run=run, orders=[])


def test_retailer_account_api_lifecycle(client, session, monkeypatch) -> None:
    token = register_and_login(client, "retailer-api@example.com")

    created = client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(token),
        json={
            "retailer": "midtown",
            "username": "collector@example.com",
            "password": "supersafe",
            "display_name": "Midtown Comics",
            "sync_enabled": True,
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]
    assert created.json()["masked_username"].startswith("co")

    account = session.exec(select(RetailerAccount).where(RetailerAccount.id == account_id)).one()
    assert decrypt_retailer_password(account.encrypted_password) == "supersafe"

    listed = client.get("/api/v1/retailer-accounts", headers=auth_headers(token))
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["retailer"] == "midtown"

    def fake_sync(db_session, *, account, limit_orders=None, test_only=False):
        return _persist_fake_sync(db_session, account=account)

    monkeypatch.setattr("app.services.retailer_accounts.sync_midtown_account", fake_sync)

    tested = client.post(
        f"/api/v1/retailer-accounts/{account_id}/test", headers=auth_headers(token)
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["run"]["status"] == "succeeded"

    synced = client.post(
        f"/api/v1/retailer-accounts/{account_id}/sync",
        headers=auth_headers(token),
        json={"limit_orders": 5},
    )
    assert synced.status_code == 200, synced.text
    assert synced.json()["orders"][0]["retailer_order_number"] == "ABC123"

    deleted = client.delete(f"/api/v1/retailer-accounts/{account_id}", headers=auth_headers(token))
    assert deleted.status_code == 204, deleted.text
    assert (
        client.get("/api/v1/retailer-accounts", headers=auth_headers(token)).json()["items"] == []
    )


def test_retailer_account_routes_are_user_scoped(client) -> None:
    owner = register_and_login(client, "retailer-owner@example.com")
    outsider = register_and_login(client, "retailer-outsider@example.com")

    created = client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(owner),
        json={
            "retailer": "midtown",
            "username": "collector@example.com",
            "password": "supersafe",
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]

    denied = client.patch(
        f"/api/v1/retailer-accounts/{account_id}",
        headers=auth_headers(outsider),
        json={"display_name": "Nope"},
    )
    assert denied.status_code == 404, denied.text


def test_retailer_account_sync_respects_challenge_cooldown(client, session) -> None:
    token = register_and_login(client, "retailer-cooldown@example.com")
    created = client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(token),
        json={
            "retailer": "midtown",
            "username": "collector@example.com",
            "password": "supersafe",
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]

    account = session.exec(select(RetailerAccount).where(RetailerAccount.id == account_id)).one()
    session.add(
        RetailerSyncRun(
            owner_user_id=account.owner_user_id,
            retailer_account_id=int(account.id),
            retailer=account.retailer,
            status="needs_attention",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            summary_json={
                "error_code": "captcha_or_security",
                "retry_allowed_at": "2999-01-01T00:00:00+00:00",
            },
            error_message="Midtown presented a CAPTCHA or security challenge.",
        )
    )
    session.commit()

    blocked = client.post(
        f"/api/v1/retailer-accounts/{account_id}/sync",
        headers=auth_headers(token),
        json={"limit_orders": 5},
    )
    assert blocked.status_code == 409, blocked.text
    assert "Please wait until" in blocked.text


def test_retailer_account_browser_sync_lifecycle(client, session, monkeypatch) -> None:
    token = register_and_login(client, "retailer-browser-sync@example.com")
    created = client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(token),
        json={
            "retailer": "midtown",
            "username": "collector@example.com",
            "password": "supersafe",
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]

    monkeypatch.setattr(
        "app.services.retailer_sync.midtown_account_sync.parse_midtown_order_history",
        lambda html_text: [
            MidtownOrderHistoryEntry(
                retailer_order_number="ABC123",
                order_date=date(2026, 6, 8),
                order_status="Shipped",
                order_total=Decimal("9.98"),
                detail_url="https://www.midtowncomics.com/account/orders/view/ABC123",
                raw_fragment=html_text,
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.retailer_sync.midtown_account_sync.parse_midtown_order_detail",
        lambda html_text, fallback_order_number=None, detail_url=None: MidtownOrderDetail(
            retailer_order_number=fallback_order_number or "ABC123",
            order_date=date(2026, 6, 8),
            order_status="Shipped",
            order_total=Decimal("9.98"),
            detail_url=detail_url,
            items=[
                MidtownOrderItem(
                    retailer_item_id="SKU-1",
                    title="Immortal Thor #1 Cover A",
                    quantity=1,
                    unit_price=Decimal("4.99"),
                    total_price=Decimal("4.99"),
                    item_status="Shipped",
                    raw_fragment=html_text,
                )
            ],
            raw_html=html_text,
        ),
    )

    started = client.post(
        f"/api/v1/retailer-accounts/{account_id}/local-sync/start",
        headers=auth_headers(token),
        json={"limit_orders": 5},
    )
    assert started.status_code == 200, started.text
    assert started.json()["run"]["status"] == "awaiting_browser"
    assert started.json()["capture_url"].endswith("/account-settings")

    completed = client.post(
        f"/api/v1/retailer-accounts/{account_id}/local-sync/{started.json()['run']['id']}/complete",
        headers=auth_headers(token),
        json={
            "helper_token": started.json()["helper_token"],
            "history_html": "<html>history</html>",
            "detail_pages": [
                {
                    "detail_url": "https://www.midtowncomics.com/account/orders/view/ABC123",
                    "retailer_order_number": "ABC123",
                    "fallback_order_number": "ABC123",
                    "html": "<html>detail</html>",
                }
            ],
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["run"]["status"] == "succeeded"
    assert completed.json()["run"]["summary_json"]["sync_path"] == "browser_assisted"
    assert completed.json()["orders"][0]["retailer_order_number"] == "ABC123"


def test_retailer_account_browser_sync_invalid_helper_token_returns_needs_attention(
    client, session, monkeypatch
) -> None:
    token = register_and_login(client, "retailer-browser-sync-invalid@example.com")
    created = client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(token),
        json={
            "retailer": "midtown",
            "username": "collector@example.com",
            "password": "supersafe",
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]

    monkeypatch.setattr(
        "app.services.retailer_sync.midtown_account_sync.parse_midtown_order_history",
        lambda html_text: [
            MidtownOrderHistoryEntry(
                retailer_order_number="ABC123",
                order_date=date(2026, 6, 8),
                order_status="Shipped",
                order_total=Decimal("9.98"),
                detail_url="https://www.midtowncomics.com/account/orders/view/ABC123",
                raw_fragment=html_text,
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.retailer_sync.midtown_account_sync.parse_midtown_order_detail",
        lambda html_text, fallback_order_number=None, detail_url=None: MidtownOrderDetail(
            retailer_order_number=fallback_order_number or "ABC123",
            order_date=date(2026, 6, 8),
            order_status="Shipped",
            order_total=Decimal("9.98"),
            detail_url=detail_url,
            items=[
                MidtownOrderItem(
                    retailer_item_id="SKU-1",
                    title="Immortal Thor #1 Cover A",
                    quantity=1,
                    unit_price=Decimal("4.99"),
                    total_price=Decimal("4.99"),
                    item_status="Shipped",
                    raw_fragment=html_text,
                )
            ],
            raw_html=html_text,
        ),
    )

    started = client.post(
        f"/api/v1/retailer-accounts/{account_id}/local-sync/start",
        headers=auth_headers(token),
        json={"limit_orders": 5},
    )
    assert started.status_code == 200, started.text

    completed = client.post(
        f"/api/v1/retailer-accounts/{account_id}/local-sync/{started.json()['run']['id']}/complete",
        headers=auth_headers(token),
        json={
            "helper_token": "definitely-wrong-token",
            "history_html": "<html>history</html>",
            "detail_pages": [
                {
                    "detail_url": "https://www.midtowncomics.com/account/orders/view/ABC123",
                    "retailer_order_number": "ABC123",
                    "fallback_order_number": "ABC123",
                    "html": "<html>detail</html>",
                }
            ],
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["run"]["status"] == "needs_attention"
    assert completed.json()["run"]["summary_json"]["error_code"] == "browser_capture_failed"
