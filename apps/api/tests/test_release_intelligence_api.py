from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.release_import import import_release_feed
from test_inventory import auth_headers, register_and_login


def _seed_release_feed(session: Session, *, owner_user_id: int) -> None:
    payload = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "Marvel",
                    "series_name": "Tomorrow Force",
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": "tomorrow-force-1",
                            "issue_number": "1",
                            "title": "Tomorrow Force First Appearance",
                            "foc_date": "2026-06-02",
                            "release_date": "2026-06-16",
                            "cover_price": 4.99,
                            "release_status": "SCHEDULED",
                            "variants": [
                                {"variant_name": "Open Order", "variant_type": "OPEN_ORDER"},
                                {"variant_name": "1:25 Incentive", "variant_type": "INCENTIVE", "ratio_value": 25},
                            ],
                        }
                    ],
                }
            ]
        }
    )
    import_release_feed(session, owner_user_id=owner_user_id, payload=payload)


def test_release_intelligence_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "release-api@example.com"
    outsider_email = "release-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        _seed_release_feed(session, owner_user_id=owner_user_id)

    new_ones = client.post("/api/v1/release-intelligence/run/new-number-ones", headers=auth_headers(owner_token))
    key_issues = client.post("/api/v1/release-intelligence/run/key-issues", headers=auth_headers(owner_token))
    variants = client.post("/api/v1/release-intelligence/run/variants", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/release-intelligence/dashboard", headers=auth_headers(owner_token))
    series = client.get("/api/v1/release-intelligence/series", headers=auth_headers(owner_token))
    issues = client.get("/api/v1/release-intelligence/issues", headers=auth_headers(owner_token))
    variant_rows = client.get("/api/v1/release-intelligence/variants", headers=auth_headers(owner_token))
    signals = client.get("/api/v1/release-intelligence/signals", headers=auth_headers(owner_token))
    executions = client.get("/api/v1/release-intelligence/executions", headers=auth_headers(owner_token))
    outsider_series = client.get("/api/v1/release-intelligence/series", headers=auth_headers(outsider_token))

    assert new_ones.status_code == 200, new_ones.text
    assert key_issues.status_code == 200, key_issues.text
    assert variants.status_code == 200, variants.text
    assert dashboard.status_code == 200, dashboard.text
    assert series.status_code == 200, series.text
    assert issues.status_code == 200, issues.text
    assert variant_rows.status_code == 200, variant_rows.text
    assert signals.status_code == 200, signals.text
    assert executions.status_code == 200, executions.text
    assert outsider_series.json()["data"]["items"] == []
    assert len(dashboard.json()["data"]["upcoming_releases"]) >= 1
