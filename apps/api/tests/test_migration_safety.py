from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.data_integrity import MigrationSafetyCheck
from app.services.migration_safety import compare_migration_counts, validate_migration_result
from test_inventory import register_and_login


def test_migration_safety_validation_records_count_deltas(client: TestClient) -> None:
    register_and_login(client, "migration-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "migration-owner@example.com")).one()
        owner_user_id = int(owner.id or 0)

        comparison = compare_migration_counts({"orders": 3, "inventory_copies": 5}, {"orders": 3, "inventory_copies": 4})
        result = validate_migration_result(
            session,
            owner_user_id=owner_user_id,
            migration_revision="20260805_0154",
            pre_count_json={"orders": 3, "inventory_copies": 5},
            post_count_json={"orders": 3, "inventory_copies": 4},
        )
        rows = session.exec(select(MigrationSafetyCheck).where(MigrationSafetyCheck.owner_user_id == owner_user_id)).all()

    assert comparison["inventory_copies"]["delta"] == -1
    assert result.check_status == "WARNING"
    assert result.validation_payload_json["negative_delta_entities"] == ["inventory_copies"]
    assert len(rows) == 1
