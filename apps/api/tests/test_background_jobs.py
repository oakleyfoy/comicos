from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import DraftImport, User
from app.schemas.ai import ParseOrderResponse
from app.tasks.queue import AI_PARSE_IMPORT_JOB_TYPE


def register_and_login(client: TestClient, email: str = "jobs@example.com") -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_mock_draft_payload() -> dict:
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
    ).model_dump(mode="json")


def seed_draft_import(session: Session, user_id: int) -> DraftImport:
    timestamp = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    draft_import = DraftImport(
        user_id=user_id,
        raw_text="Whatnot receipt text",
        parsed_payload_json=build_mock_draft_payload(),
        confidence_score=Decimal("0.66"),
        status="draft",
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(draft_import)
    session.commit()
    session.refresh(draft_import)
    return draft_import


class FakeJob:
    def __init__(
        self,
        *,
        job_id: str,
        status: str,
        user_id: int,
        result: dict | None = None,
        exc_info: str | None = None,
    ) -> None:
        timestamp = datetime(2026, 5, 22, 12, 5, tzinfo=timezone.utc)
        self.id = job_id
        self.meta = {"job_type": AI_PARSE_IMPORT_JOB_TYPE, "user_id": user_id}
        self.result = result
        self.exc_info = exc_info
        self.enqueued_at = timestamp
        self.started_at = timestamp
        self.ended_at = timestamp if status in {"finished", "failed"} else None
        self._status = status

    def get_status(self, refresh: bool = True) -> str:
        del refresh
        return self._status


def test_enqueue_import_parse_job_returns_202(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client)
    queued_job = type("QueuedJob", (), {"id": "job-1-20"})()

    monkeypatch.setattr("app.services.background_jobs.ensure_ai_parser_configured", lambda: None)
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_ai_parse_import_job",
        lambda *, user_id, raw_text: queued_job,
    )

    response = client.post(
        "/imports/parse-jobs",
        json={"raw_text": "Whatnot receipt text"},
        headers=auth_headers(token),
    )

    assert response.status_code == 202
    assert response.json() == {"job_id": "job-1-20", "status": "queued"}


def test_enqueue_import_parse_job_returns_503_when_ai_not_configured(
    client: TestClient,
) -> None:
    token = register_and_login(client)

    response = client.post(
        "/imports/parse-jobs",
        json={"raw_text": "Whatnot receipt text"},
        headers=auth_headers(token),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI parser is not configured."}


def test_get_import_parse_job_status_returns_finished_import_record(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, email="owner@example.com")
    owner = session.exec(select(User).where(User.email == "owner@example.com")).one()
    draft_import = seed_draft_import(session, owner.id)

    fake_job = FakeJob(
        job_id="job-finished",
        status="finished",
        user_id=owner.id,
        result={"import_id": draft_import.id},
    )
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: fake_job)

    response = client.get(
        "/imports/parse-jobs/job-finished",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "job-finished"
    assert data["status"] == "finished"
    assert data["import_id"] == draft_import.id
    assert data["import_record"]["id"] == draft_import.id
    assert data["import_record"]["status"] == "draft"


def test_get_import_parse_job_status_hides_other_users_jobs(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, email="owner@example.com")
    register_and_login(client, email="other@example.com")
    other_user = session.exec(select(User).where(User.email == "other@example.com")).one()

    fake_job = FakeJob(
        job_id="job-other-user",
        status="queued",
        user_id=other_user.id,
    )
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: fake_job)

    response = client.get(
        "/imports/parse-jobs/job-other-user",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}
