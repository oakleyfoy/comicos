from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseIssue, User
from app.services.release_platform_validation import validate_release_platform
from release_platform_test_helpers import seed_release_platform_certification_stack
from test_inventory import auth_headers, register_and_login


def test_release_platform_validation_returns_pass_without_mutation(client: TestClient) -> None:
    email = "release-platform-validation@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_release_platform_certification_stack(session, owner_user_id=owner_id)
        issue_count = len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).all())
        result = validate_release_platform(session, owner_user_id=owner_id)
        assert result.overall_status == "PASS"
        assert result.platform_certified is True
        assert len(result.checks) == 9
        assert (
            len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).all()) == issue_count
        )


def test_release_platform_validation_api_is_owner_scoped(client: TestClient) -> None:
    owner_email = "release-platform-validation-owner@example.com"
    outsider_email = "release-platform-validation-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == owner_email)).one().id or 0)
        seed_release_platform_certification_stack(session, owner_user_id=owner_id)

    owner_response = client.get("/api/v1/release-platform/validation", headers=auth_headers(owner_token))
    outsider_response = client.get("/api/v1/release-platform/validation", headers=auth_headers(outsider_token))

    assert owner_response.status_code == 200, owner_response.text
    assert outsider_response.status_code == 200, outsider_response.text
    assert owner_response.json()["data"]["overall_status"] == "PASS"
    assert outsider_response.json()["data"]["checks"][0]["details_json"]["issue_count"] == 0
