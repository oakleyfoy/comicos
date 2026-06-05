from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import encrypt_secret_value
from app.models import DraftImport, GmailAccount, GmailImportRecord, InventoryCopy, Order, User
from app.schemas.ai import ParseOrderResponse
from app.services.gmail_ingestion import (
    GMAIL_OAUTH_SCOPES,
    GmailReceiptMessage,
    _detect_supported_provider,
    list_recent_supported_receipt_emails,
    sync_gmail_receipts_for_user,
)
from app.tasks.jobs import run_gmail_sync_job
from app.tasks.scheduled import enqueue_due_gmail_auto_sync_jobs


def register_and_login(client: TestClient, email: str = "gmail@example.com") -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def configure_gmail(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/gmail/connect/callback")
    get_settings.cache_clear()


def clear_gmail_config(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "")
    get_settings.cache_clear()


def build_mock_draft() -> ParseOrderResponse:
    return ParseOrderResponse.model_validate(
        {
            "retailer": "Whatnot",
            "order_date": "2026-05-21",
            "source_type": "ai_draft",
            "shipping_amount": Decimal("4.99"),
            "tax_amount": Decimal("1.50"),
            "items": [
                {
                    "publisher": "Image",
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 2,
                    "raw_item_price": Decimal("7.65"),
                }
            ],
            "warnings": ["Review ratio before confirming."],
            "confidence_score": 0.66,
        }
    )


def test_detect_supported_provider_accepts_direct_supported_sender() -> None:
    provider = _detect_supported_provider("orders@midtowncomics.com")

    assert provider == "Midtown Comics"


def test_detect_supported_provider_rejects_unsupported_sender_without_provider_match() -> None:
    provider = _detect_supported_provider("Oakley Foy <ofoy@att.net>", "Fwd: random message")

    assert provider is None


def test_detect_supported_provider_accepts_forwarded_midtown_receipt() -> None:
    provider = _detect_supported_provider(
        "Oakley Foy <ofoy@att.net>",
        "Fw: Order No. 4257558 Confirmation From Midtown Comics",
        "From: info@midtowncomics.com",
    )

    assert provider == "Midtown Comics"


def test_gmail_oauth_endpoints_require_auth(client: TestClient, monkeypatch) -> None:
    configure_gmail(monkeypatch)

    assert client.get("/gmail/connect/start").status_code == 401
    assert client.get("/gmail/status").status_code == 401
    assert client.post("/gmail/disconnect").status_code == 401
    assert client.post("/gmail/sync").status_code == 401


def test_gmail_connect_start_requests_gmail_readonly_scope(
    client: TestClient,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    token = register_and_login(client)

    response = client.get("/gmail/connect/start", headers=auth_headers(token))

    assert response.status_code == 200
    authorization_url = response.json()["authorization_url"]
    parsed = urlparse(authorization_url)
    requested_scopes = parse_qs(parsed.query)["scope"][0].split()
    assert requested_scopes == list(GMAIL_OAUTH_SCOPES)


def test_gmail_connect_start_returns_503_when_not_configured(
    client: TestClient,
    monkeypatch,
) -> None:
    clear_gmail_config(monkeypatch)
    token = register_and_login(client)

    response = client.get("/gmail/connect/start", headers=auth_headers(token))

    assert response.status_code == 503
    assert response.json() == {"detail": "Gmail integration is not configured."}


def test_gmail_status_reports_not_configured_without_env(
    client: TestClient,
    monkeypatch,
) -> None:
    clear_gmail_config(monkeypatch)
    token = register_and_login(client)

    response = client.get("/gmail/status", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "connected": False,
        "gmail_email": None,
        "token_expires_at": None,
    }


def test_gmail_sync_returns_503_when_not_configured(
    client: TestClient,
    monkeypatch,
) -> None:
    clear_gmail_config(monkeypatch)
    token = register_and_login(client)

    response = client.post("/gmail/sync", headers=auth_headers(token))

    assert response.status_code == 503
    assert response.json() == {"detail": "Gmail integration is not configured."}


def test_gmail_connect_callback_stores_encrypted_tokens(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    token = register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()

    monkeypatch.setattr(
        "app.services.gmail_ingestion.exchange_gmail_oauth_code",
        lambda code: {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
        },
    )
    monkeypatch.setattr(
        "app.services.gmail_ingestion.fetch_google_userinfo",
        lambda access_token: {
            "email": "owner@gmail.com",
            "sub": "google-subject-123",
        },
    )

    start_response = client.get("/gmail/connect/start", headers=auth_headers(token))
    authorization_url = start_response.json()["authorization_url"]
    state = authorization_url.split("state=", maxsplit=1)[1].split("&", maxsplit=1)[0]

    callback_response = client.get(
        f"/gmail/connect/callback?code=test-code&state={state}",
        follow_redirects=False,
    )

    assert callback_response.status_code == 302
    account = session.exec(select(GmailAccount).where(GmailAccount.user_id == owner.id)).one()
    assert account.gmail_email == "owner@gmail.com"
    assert account.google_subject_id == "google-subject-123"
    assert account.access_token_encrypted != "access-token-123"
    assert account.refresh_token_encrypted != "refresh-token-123"


def test_gmail_disconnect_clears_tokens(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(account)
    session.commit()

    response = client.post("/gmail/disconnect", headers=auth_headers(token))

    assert response.status_code == 200
    session.refresh(account)
    assert account.access_token_encrypted is None
    assert account.refresh_token_encrypted is None
    assert account.token_expires_at is None


def test_gmail_sync_creates_draft_imports_only_and_skips_duplicates(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    token = register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()

    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    existing_import = DraftImport(
        user_id=owner.id,
        raw_text="Existing imported receipt",
        parsed_payload_json=build_mock_draft().model_dump(mode="json"),
        confidence_score=Decimal("0.66"),
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(existing_import)
    session.commit()
    session.refresh(existing_import)

    session.add(
        GmailImportRecord(
            gmail_account_id=account.id,
            external_message_id="msg-duplicate",
            draft_import_id=existing_import.id,
            imported_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    monkeypatch.setattr(
        "app.services.gmail_ingestion.list_recent_supported_receipt_emails",
        lambda session, account: [
            GmailReceiptMessage(
                external_message_id="msg-duplicate",
                provider_name="Whatnot",
                subject="Existing Receipt",
                sender="orders@whatnot.com",
                received_at=datetime.now(timezone.utc),
                body_text="duplicate body",
            ),
            GmailReceiptMessage(
                external_message_id="msg-new",
                provider_name="Midtown Comics",
                subject="New Receipt",
                sender="orders@midtowncomics.com",
                received_at=datetime.now(timezone.utc),
                body_text="new body",
            ),
        ],
    )
    monkeypatch.setattr(
        "app.services.gmail_ingestion.parse_order_draft_from_text",
        lambda raw_text: build_mock_draft(),
    )

    result = sync_gmail_receipts_for_user(session=session, current_user=owner)

    assert result == {
        "processed_messages": 2,
        "created_draft_imports": 1,
        "skipped_duplicates": 1,
    }

    all_imports = session.exec(select(DraftImport)).all()
    assert len(all_imports) == 2
    assert len(session.exec(select(Order)).all()) == 0
    assert len(session.exec(select(InventoryCopy)).all()) == 0

    imported_record = session.exec(
        select(GmailImportRecord).where(GmailImportRecord.external_message_id == "msg-new")
    ).one()
    created_import = session.get(DraftImport, imported_record.draft_import_id)
    assert created_import is not None
    assert created_import.status == "draft"
    assert created_import.linked_order_id is None
    assert created_import.parsed_payload_json["source_type"] == "gmail_draft"

    queued_job = type("QueuedJob", (), {"id": "gmail-job-1"})()
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_gmail_sync_job",
        lambda *, user_id, gmail_account_id: queued_job,
    )
    sync_response = client.post("/gmail/sync", headers=auth_headers(token))
    assert sync_response.status_code == 202
    assert sync_response.json() == {"job_id": "gmail-job-1", "status": "queued"}


def test_list_recent_supported_receipt_emails_accepts_forwarded_midtown_receipt(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    monkeypatch.setattr(
        "app.services.gmail_ingestion._get_valid_access_token",
        lambda session, account: "access-token",
    )

    def fake_gmail_api_get(access_token: str, url: str) -> dict:
        del access_token
        if "messages?" in url:
            return {"messages": [{"id": "msg-forwarded-midtown"}]}
        return {
            "id": "msg-forwarded-midtown",
            "snippet": "Order No. 4257558 Confirmation From Midtown Comics",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Oakley Foy <ofoy@att.net>"},
                    {
                        "name": "Subject",
                        "value": "Fw: Order No. 4257558 Confirmation From Midtown Comics",
                    },
                    {"name": "Date", "value": "Fri, 22 May 2026 12:00:00 +0000"},
                ],
                "mimeType": "text/plain",
                "body": {
                    "data": (
                        "RnJvbTogaW5mb0BtaWR0b3duY29taWNzLmNvbQpTdWJqZWN0OiBPcmRlciBOby4gNDI1NzU1OCBD"
                        "b25maXJtYXRpb24gRnJvbSBNaWR0b3duIENvbWljcw=="
                    )
                },
            },
        }

    monkeypatch.setattr(
        "app.services.gmail_ingestion._gmail_api_get",
        fake_gmail_api_get,
    )

    messages = list_recent_supported_receipt_emails(session, account)

    assert len(messages) == 1
    assert messages[0].external_message_id == "msg-forwarded-midtown"
    assert messages[0].provider_name == "Midtown Comics"
    assert messages[0].sender == "Oakley Foy <ofoy@att.net>"
    assert "Midtown Comics" in messages[0].subject


def test_gmail_sync_skips_duplicate_forwarded_midtown_receipt(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    existing_import = DraftImport(
        user_id=owner.id,
        raw_text="Forwarded Midtown receipt",
        parsed_payload_json=build_mock_draft().model_dump(mode="json"),
        confidence_score=Decimal("0.66"),
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(existing_import)
    session.commit()
    session.refresh(existing_import)

    session.add(
        GmailImportRecord(
            gmail_account_id=account.id,
            external_message_id="msg-forwarded-midtown",
            draft_import_id=existing_import.id,
            imported_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    monkeypatch.setattr(
        "app.services.gmail_ingestion.list_recent_supported_receipt_emails",
        lambda session, account: [
            GmailReceiptMessage(
                external_message_id="msg-forwarded-midtown",
                provider_name="Midtown Comics",
                subject="Fw: Order No. 4257558 Confirmation From Midtown Comics",
                sender="Oakley Foy <ofoy@att.net>",
                received_at=datetime.now(timezone.utc),
                body_text=(
                    "From: info@midtowncomics.com\n"
                    "Subject: Order No. 4257558 Confirmation From Midtown Comics"
                ),
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.gmail_ingestion.parse_order_draft_from_text",
        lambda raw_text: build_mock_draft(),
    )

    result = sync_gmail_receipts_for_user(session=session, current_user=owner)

    assert result == {
        "processed_messages": 1,
        "created_draft_imports": 0,
        "skipped_duplicates": 1,
    }
    assert len(session.exec(select(DraftImport)).all()) == 1
    assert len(session.exec(select(Order)).all()) == 0
    assert len(session.exec(select(InventoryCopy)).all()) == 0


def test_gmail_sync_returns_503_when_not_connected(
    client: TestClient,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    token = register_and_login(client)

    response = client.post("/gmail/sync", headers=auth_headers(token))

    assert response.status_code == 503
    assert response.json() == {"detail": "Connect a Gmail account before syncing receipts."}


def test_gmail_sync_settings_enable_and_disable_persist(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    token = register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(account)
    session.commit()

    enable_response = client.patch(
        "/gmail/sync/settings",
        json={"auto_sync_enabled": True},
        headers=auth_headers(token),
    )
    assert enable_response.status_code == 200
    assert enable_response.json()["auto_sync_enabled"] is True

    status_response = client.get("/gmail/sync/status", headers=auth_headers(token))
    assert status_response.status_code == 200
    assert status_response.json()["auto_sync_enabled"] is True

    disable_response = client.patch(
        "/gmail/sync/settings",
        json={"auto_sync_enabled": False},
        headers=auth_headers(token),
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["auto_sync_enabled"] is False


def test_scheduled_runner_enqueues_connected_auto_sync_accounts(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        auto_sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "app.tasks.scheduled.enqueue_gmail_sync_job",
        lambda *, user_id, gmail_account_id: calls.append((user_id, gmail_account_id)),
    )
    monkeypatch.setattr(
        "app.tasks.scheduled.find_active_gmail_sync_job_for_account",
        lambda gmail_account_id: None,
    )

    result = enqueue_due_gmail_auto_sync_jobs()

    assert result == {
        "eligible_accounts": 1,
        "enqueued_jobs": 1,
        "skipped_disconnected": 0,
        "skipped_active": 0,
    }
    assert calls == [(owner.id, account.id)]


def test_scheduled_runner_skips_disconnected_accounts(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=None,
        refresh_token_encrypted=None,
        auto_sync_enabled=True,
    )
    session.add(account)
    session.commit()

    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "app.tasks.scheduled.enqueue_gmail_sync_job",
        lambda *, user_id, gmail_account_id: calls.append((user_id, gmail_account_id)),
    )

    result = enqueue_due_gmail_auto_sync_jobs()

    assert result == {
        "eligible_accounts": 1,
        "enqueued_jobs": 0,
        "skipped_disconnected": 1,
        "skipped_active": 0,
    }
    assert calls == []


def test_scheduled_runner_prevents_duplicate_active_syncs(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        auto_sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    monkeypatch.setattr(
        "app.tasks.scheduled.find_active_gmail_sync_job_for_account",
        lambda gmail_account_id: object(),
    )

    def unexpected_enqueue(*, user_id, gmail_account_id):
        del user_id, gmail_account_id
        raise AssertionError("should not enqueue")

    monkeypatch.setattr(
        "app.tasks.scheduled.enqueue_gmail_sync_job",
        unexpected_enqueue,
    )

    result = enqueue_due_gmail_auto_sync_jobs()

    assert result == {
        "eligible_accounts": 1,
        "enqueued_jobs": 0,
        "skipped_disconnected": 0,
        "skipped_active": 1,
    }


def seed_gmail_import_record(
    session: Session,
    *,
    account: GmailAccount,
    owner: User,
    external_message_id: str,
    imported_at: datetime,
    status: str = "draft",
) -> GmailImportRecord:
    draft_import = DraftImport(
        user_id=owner.id,
        raw_text=f"Receipt body for {external_message_id}",
        parsed_payload_json=build_mock_draft().model_dump(mode="json"),
        confidence_score=Decimal("0.66"),
        status=status,
        created_at=imported_at,
        updated_at=imported_at,
    )
    session.add(draft_import)
    session.commit()
    session.refresh(draft_import)
    record = GmailImportRecord(
        gmail_account_id=account.id,
        external_message_id=external_message_id,
        draft_import_id=draft_import.id,
        imported_at=imported_at,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def test_gmail_imports_list_is_lightweight_and_respects_limit(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    token = register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    base_time = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    for index in range(3):
        seed_gmail_import_record(
            session,
            account=account,
            owner=owner,
            external_message_id=f"msg-{index}",
            imported_at=base_time + timedelta(hours=index),
        )

    def fail_if_cover_prefetch(*args, **kwargs):
        del args, kwargs
        raise AssertionError("list_cover_reads_for_draft should not run for GET /gmail/imports")

    monkeypatch.setattr(
        "app.services.imports.list_cover_reads_for_draft",
        fail_if_cover_prefetch,
    )

    default_response = client.get("/gmail/imports", headers=auth_headers(token))
    assert default_response.status_code == 200
    default_payload = default_response.json()
    assert len(default_payload) == 3
    assert default_payload[0]["external_message_id"] == "msg-2"
    assert default_payload[0]["draft_import"]["cover_images"] == []
    assert default_payload[0]["draft_import"]["cover_image_count"] == 0

    limited_response = client.get("/gmail/imports?limit=2", headers=auth_headers(token))
    assert limited_response.status_code == 200
    limited_payload = limited_response.json()
    assert len(limited_payload) == 2
    assert [row["external_message_id"] for row in limited_payload] == ["msg-2", "msg-1"]


def test_failed_gmail_sync_updates_status_and_safe_error(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    configure_gmail(monkeypatch)
    register_and_login(client)
    owner = session.exec(select(User).where(User.email == "gmail@example.com")).one()
    account = GmailAccount(
        user_id=owner.id,
        gmail_email="owner@gmail.com",
        google_subject_id="google-subject-123",
        access_token_encrypted=encrypt_secret_value("access-token"),
        refresh_token_encrypted=encrypt_secret_value("refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        auto_sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    long_error = "gmail sync failed " + ("x" * 400)
    monkeypatch.setattr(
        "app.tasks.jobs.sync_gmail_receipts_for_user",
        lambda session, current_user: (_ for _ in ()).throw(RuntimeError(long_error)),
    )

    try:
        run_gmail_sync_job(owner.id, account.id)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected runtime error from Gmail sync job")

    session.refresh(account)
    assert account.last_sync_started_at is not None
    assert account.last_sync_completed_at is not None
    assert account.last_sync_status == "failed"
    assert account.last_sync_error is not None
    assert len(account.last_sync_error) <= 280
