from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import (
    DraftImport,
    GmailAccount,
    GmailImportRecord,
    InventoryCopy,
    MarketSource,
    Order,
    Publisher,
    ReleaseWatchlist,
    RetailerAccount,
    User,
)
from app.services.user_collection_reset import COLLECTION_RESET_CONFIRMATION_PHRASE
from test_inventory import auth_headers, create_order, register_and_login


def _seed_retailer_account(session: Session, *, user_id: int) -> RetailerAccount:
    account = RetailerAccount(
        owner_user_id=user_id,
        retailer="midtown",
        display_name="Midtown Comics",
        username="reset-api@example.com",
        encrypted_password="enc",
        credential_version=1,
        status="connected",
        sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _seed_gmail(session: Session, *, user_id: int) -> GmailAccount:
    account = GmailAccount(
        user_id=user_id,
        gmail_email="reset-api@gmail.com",
        google_subject_id="google-subject-reset-api",
    )
    session.add(account)
    session.flush()
    draft = DraftImport(
        user_id=user_id,
        raw_text="gmail receipt",
        parsed_payload_json={"items": [], "retailer": "Test", "confidence_score": "0.5"},
        confidence_score=Decimal("0.5"),
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(draft)
    session.flush()
    session.add(
        GmailImportRecord(
            gmail_account_id=int(account.id),
            external_message_id="msg-reset-test",
            draft_import_id=int(draft.id),
            imported_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        ReleaseWatchlist(
            owner_user_id=user_id,
            watchlist_name="My watchlist",
            watchlist_type="manual",
        )
    )
    session.commit()
    session.refresh(account)
    return account


def test_reset_collection_data_api_scoped_and_preserves_credentials(client, session) -> None:
    victim_email = "reset-api-victim@example.com"
    other_email = "reset-api-other@example.com"
    victim_token = register_and_login(client, victim_email)
    other_token = register_and_login(client, other_email)

    create_order(client, victim_token)
    create_order(client, other_token)

    victim = session.exec(select(User).where(User.email == victim_email)).one()
    other = session.exec(select(User).where(User.email == other_email)).one()
    _seed_retailer_account(session, user_id=int(victim.id))
    _seed_gmail(session, user_id=int(victim.id))

    publishers_before = len(session.exec(select(Publisher.id)).all())
    market_sources_before = len(session.exec(select(MarketSource.id)).all())

    preview = client.post(
        "/api/v1/account/reset-collection-data/preview",
        headers=auth_headers(victim_token),
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["dry_run"] is True
    assert preview_body["summary"]["inventory_copies"] >= 1
    assert preview_body["summary"]["orders"] >= 1
    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == victim.id)).all()) >= 1

    bad_phrase = client.post(
        "/api/v1/account/reset-collection-data",
        headers=auth_headers(victim_token),
        json={
            "confirmation_phrase": "WRONG PHRASE",
            "acknowledge_permanent_delete": True,
        },
    )
    assert bad_phrase.status_code == 400

    no_ack = client.post(
        "/api/v1/account/reset-collection-data",
        headers=auth_headers(victim_token),
        json={
            "confirmation_phrase": COLLECTION_RESET_CONFIRMATION_PHRASE,
            "acknowledge_permanent_delete": False,
        },
    )
    assert no_ack.status_code == 400

    executed = client.post(
        "/api/v1/account/reset-collection-data",
        headers=auth_headers(victim_token),
        json={
            "confirmation_phrase": COLLECTION_RESET_CONFIRMATION_PHRASE,
            "acknowledge_permanent_delete": True,
        },
    )
    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["status"] == "success"
    assert body["deleted"]["inventory_copies"] >= 1
    assert body["remaining"]["inventory_copies"] == 0
    assert body["remaining"]["orders"] == 0
    assert body["remaining"]["draft_imports"] == 0

    assert session.exec(select(User).where(User.email == victim_email)).one() is not None
    assert session.exec(select(RetailerAccount).where(RetailerAccount.owner_user_id == victim.id)).one() is not None
    assert session.exec(select(GmailAccount).where(GmailAccount.user_id == victim.id)).one() is not None
    assert len(session.exec(select(GmailImportRecord)).all()) == 0
    assert len(session.exec(select(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == victim.id)).all()) == 1

    assert len(session.exec(select(Publisher.id)).all()) == publishers_before
    assert len(session.exec(select(MarketSource.id)).all()) == market_sources_before

    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == other.id)).all()) == 1
    assert len(session.exec(select(Order.id).where(Order.user_id == other.id)).all()) == 1

    outsider_preview = client.post(
        "/api/v1/account/reset-collection-data/preview",
        headers=auth_headers(other_token),
    )
    assert outsider_preview.status_code == 200
    assert outsider_preview.json()["summary"]["inventory_copies"] >= 1
