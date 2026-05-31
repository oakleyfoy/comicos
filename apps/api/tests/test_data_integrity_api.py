from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import Order, User
from app.services.change_tracking import track_entity_change
from app.services.data_integrity import run_integrity_check
from app.services.migration_safety import validate_migration_result
from test_inventory import auth_headers, register_and_login


def _seed_integrity_context(session: Session, *, owner_user_id: int) -> None:
    session.add(
        Order(
            user_id=owner_user_id,
            retailer="API Retailer",
            order_date=date(2026, 5, 30),
            shipping_amount="5.00",
            tax_amount="1.00",
            total_amount="2.00",
        )
    )
    session.commit()
    run_integrity_check(session, owner_user_id=owner_user_id)
    validate_migration_result(
        session,
        owner_user_id=owner_user_id,
        migration_revision="20260805_0154",
        pre_count_json={"orders": 1},
        post_count_json={"orders": 1},
    )
    track_entity_change(
        session,
        owner_user_id=owner_user_id,
        actor_id=owner_user_id,
        actor_type="user",
        action_type="inventory_update",
        entity_type="inventory_copy",
        entity_id=44,
        source="api_test",
        before_payload={"grade_status": "raw"},
        after_payload={"grade_status": "graded"},
        event_payload_json={"changed_field_count": 1},
    )


def test_data_integrity_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "integrity-api-owner@example.com"
    outsider_email = "integrity-api-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        _seed_integrity_context(session, owner_user_id=int(owner.id or 0))

    checks = client.get("/api/v1/data-integrity/checks", headers=auth_headers(owner_token))
    issues = client.get("/api/v1/data-integrity/issues", headers=auth_headers(owner_token))
    migrations = client.get("/api/v1/data-integrity/migration-safety", headers=auth_headers(owner_token))
    audits = client.get("/api/v1/data-integrity/audit-events", headers=auth_headers(owner_token))
    run_check = client.post("/api/v1/data-integrity/run", headers=auth_headers(owner_token))

    assert checks.status_code == 200, checks.text
    assert issues.status_code == 200, issues.text
    assert migrations.status_code == 200, migrations.text
    assert audits.status_code == 200, audits.text
    assert run_check.status_code == 200, run_check.text

    check_id = int(checks.json()["data"]["items"][0]["id"])
    audit_event_id = int(audits.json()["data"]["items"][0]["id"])
    check_detail = client.get(f"/api/v1/data-integrity/checks/{check_id}", headers=auth_headers(owner_token))
    audit_detail = client.get(f"/api/v1/data-integrity/audit-events/{audit_event_id}", headers=auth_headers(owner_token))
    outsider_checks = client.get("/api/v1/data-integrity/checks", headers=auth_headers(outsider_token))
    migration_validate = client.post(
        "/api/v1/data-integrity/migration-safety/validate",
        headers=auth_headers(owner_token),
        json={"migration_revision": "20260805_0154", "pre_count_json": {"orders": 1}, "post_count_json": {"orders": 1}},
    )

    assert check_detail.status_code == 200, check_detail.text
    assert audit_detail.status_code == 200, audit_detail.text
    assert migration_validate.status_code == 200, migration_validate.text
    assert checks.json()["data"]["pagination"]["total_count"] >= 1
    assert issues.json()["data"]["pagination"]["total_count"] >= 1
    assert audits.json()["data"]["items"][0]["action_type"] == "inventory_update"
    assert audit_detail.json()["data"]["changes"][0]["field_name"] == "grade_status"
    assert outsider_checks.json()["data"]["pagination"]["total_count"] == 0
