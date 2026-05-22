from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from rq import Queue
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import DraftImport, GmailAccount, GmailImportRecord, User
from app.schemas.ai import ParseOrderResponse
from app.services.ops_events import record_ops_event
from app.tasks.queue import get_redis_connection


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_draft_payload() -> dict:
    return ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown Comics",
            "order_date": "2026-05-21",
            "source_type": "gmail_draft",
            "shipping_amount": Decimal("4.99"),
            "tax_amount": Decimal("1.50"),
            "items": [
                {
                    "publisher": "DC",
                    "title": "Batman",
                    "issue_number": "1",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                }
            ],
            "warnings": ["Imported from Gmail email"],
            "confidence_score": 0.88,
        }
    ).model_dump(mode="json")


def test_ops_dashboard_denies_non_admins(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "user@example.com")

    response = client.get("/ops/dashboard", headers=auth_headers(token))

    assert response.status_code == 403
    assert response.json() == {"detail": "Operations dashboard access denied"}


def test_ops_dashboard_returns_recent_visibility_data(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")
    owner = session.exec(select(User).where(User.email == "ops@example.com")).one()

    account = GmailAccount(
        user_id=owner.id,
        gmail_email="ops@gmail.com",
        google_subject_id="google-subject-ops",
        access_token_encrypted="encrypted-token",
        auto_sync_enabled=True,
        last_sync_status="success",
        last_sync_started_at=datetime(2026, 5, 23, 15, 0, tzinfo=timezone.utc),
        last_sync_completed_at=datetime(2026, 5, 23, 15, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 23, 14, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 23, 15, 1, tzinfo=timezone.utc),
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    draft = DraftImport(
        user_id=owner.id,
        raw_text="Batman order",
        parsed_payload_json=build_draft_payload(),
        confidence_score=Decimal("0.88"),
        status="draft",
        created_at=datetime(2026, 5, 23, 15, 2, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 23, 15, 2, tzinfo=timezone.utc),
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    session.add(
        GmailImportRecord(
            gmail_account_id=account.id,
            external_message_id="gmail-message-123",
            draft_import_id=draft.id,
            imported_at=datetime(2026, 5, 23, 15, 3, tzinfo=timezone.utc),
        )
    )
    session.commit()

    record_ops_event(
        event_type="gmail_sync",
        status="success",
        user_id=owner.id,
        gmail_account_id=account.id,
        job_id="gmail-job-1",
        queue_name="gmail_sync",
        message="Gmail sync completed",
        details={
            "processed_messages": 2,
            "created_draft_imports": 1,
            "skipped_duplicates": 1,
        },
    )
    record_ops_event(
        event_type="duplicate_skip",
        status="skipped",
        user_id=owner.id,
        gmail_account_id=account.id,
        draft_import_id=draft.id,
        external_message_id="gmail-message-123",
        message="Skipped duplicate Gmail import",
        details={"original_imported_at": "2026-05-23T15:03:00+00:00"},
    )
    record_ops_event(
        event_type="parser_failure",
        status="failed",
        user_id=owner.id,
        gmail_account_id=account.id,
        external_message_id="gmail-message-999",
        message="OpenAI API request failed: insufficient_quota",
        details={"failure_type": "openai_quota_failure"},
    )
    record_ops_event(
        event_type="confirm_success",
        status="success",
        user_id=owner.id,
        draft_import_id=draft.id,
        order_id=7,
        message="Draft import confirmed into order",
        details={"all_in_total": "6.49"},
    )

    queue = Queue("ai_parse", connection=get_redis_connection())
    job = queue.enqueue("app.tasks.jobs.run_worker_heartbeat", result_ttl=300)
    job.meta["job_type"] = "ai_parse_import"
    job.meta["user_id"] = owner.id
    job.save_meta()

    response = client.get("/ops/dashboard", headers=auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert len(data["queue_health"]) == 2
    assert data["gmail_sync_statuses"][0]["processed_messages"] == 2
    assert data["gmail_sync_statuses"][0]["created_draft_imports"] == 1
    assert data["gmail_sync_statuses"][0]["skipped_duplicates"] == 1
    assert data["recent_draft_imports"][0]["draft_id"] == draft.id
    assert data["recent_draft_imports"][0]["warning_count"] == 1
    assert data["duplicate_skip_events"][0]["external_message_id"] == "gmail-message-123"
    assert data["parser_failures"][0]["details"]["failure_type"] == "openai_quota_failure"
    assert data["confirm_events"][0]["order_id"] == 7
    assert any(job_row["job_id"] == job.id for job_row in data["recent_ai_parse_jobs"])
