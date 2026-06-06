import hashlib

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, select

from app.models.ebay_compliance import EbayAccountDeletionAuditLog
from app.services.ebay_account_deletion_compliance import compute_challenge_response


def test_compute_challenge_response_matches_ebay_concat_sha256_hex() -> None:
    challenge = "abc"
    token = "token"
    endpoint = "https://api.example.com/api/v1/ebay/account-deletion"
    expected = hashlib.sha256((challenge + token + endpoint).encode("utf-8")).hexdigest()
    assert (
        compute_challenge_response(
            challenge_code=challenge,
            verification_token=token,
            endpoint_url=endpoint,
        )
        == expected
    )


def test_get_challenge_endpoint(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EBAY_ACCOUNT_DELETION_VERIFICATION_TOKEN", "test-verification-token")
    monkeypatch.setenv(
        "EBAY_ACCOUNT_DELETION_ENDPOINT_URL",
        "https://api.comicosapp.com/api/v1/ebay/account-deletion",
    )
    from app.core.config import get_settings

    get_settings.cache_clear()

    challenge = "challenge-12345"
    token = "test-verification-token"
    endpoint = "https://api.comicosapp.com/api/v1/ebay/account-deletion"
    expected = hashlib.sha256((challenge + token + endpoint).encode("utf-8")).hexdigest()

    rsp = client.get("/api/v1/ebay/account-deletion", params={"challenge_code": challenge})
    assert rsp.status_code == 200
    assert rsp.json() == {"challengeResponse": expected}


def test_post_notification_writes_noop_audit_without_pii(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EBAY_ACCOUNT_DELETION_VERIFICATION_TOKEN", "test-verification-token")
    from app.core.config import get_settings

    get_settings.cache_clear()

    body = {
        "metadata": {"topic": "MARKETPLACE_ACCOUNT_DELETION", "schemaVersion": "1.0"},
        "notification": {
            "notificationId": "notif-uuid-001",
            "eventDate": "2026-06-01T12:00:00.000Z",
            "publishDate": "2026-06-01T12:00:01.000Z",
            "data": {
                "username": "must-not-persist",
                "userId": "must-not-persist",
                "eiasToken": "must-not-persist",
            },
        },
    }
    rsp = client.post("/api/v1/ebay/account-deletion", json=body)
    assert rsp.status_code == 200
    assert rsp.json()["status"] == "ok"
    assert rsp.json()["noop_action"] == "acknowledged_no_user_data_retained"

    rows = session.exec(select(EbayAccountDeletionAuditLog)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_kind == "account_deletion_notification"
    assert row.external_notification_id == "notif-uuid-001"
    assert row.noop_action == "acknowledged_no_user_data_retained"
    assert row.payload_digest is not None
    assert "must-not-persist" not in str(row.model_dump())


def test_endpoint_disabled_returns_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EBAY_ACCOUNT_DELETION_COMPLIANCE_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    rsp = client.get("/api/v1/ebay/account-deletion", params={"challenge_code": "x"})
    assert rsp.status_code == 503
