from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.services.marketplace_accounts import create_account
from app.services.marketplace_execution import complete_execution, fail_execution, start_execution
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def _owner_id(session: Session, *, email: str) -> int:
    owner = session.exec(select(User).where(User.email == email)).one()
    return int(owner.id or 0)


def _marketplace_id(session: Session, *, code: str) -> int:
    marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == code)).one()
    return int(marketplace.id or 0)


def test_marketplace_execution_creation_and_completion(client: TestClient) -> None:
    register_and_login(client, "execution-owner@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, email="execution-owner@example.com")
        marketplace_id = _marketplace_id(session, code="WHATNOT")
        account = create_account(
            session,
            owner_id=owner_id,
            payload=MarketplaceAccountCreate(
                marketplace_id=marketplace_id,
                account_name="Execution Account",
                account_identifier="execution-account-1",
                status="ACTIVE",
            ),
        )

        started = start_execution(
            session,
            marketplace_id=marketplace_id,
            account_id=account.id,
            execution_type="credential.validate",
            execution_uuid="exec-validate-1",
        )
        completed = complete_execution(session, execution_id=started.id)

        assert started.status == "STARTED"
        assert completed.status == "COMPLETED"
        assert completed.execution_uuid == "exec-validate-1"
        assert completed.completed_at is not None
        assert completed.duration_ms is not None


def test_marketplace_execution_failure(client: TestClient) -> None:
    register_and_login(client, "execution-failure-owner@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        _owner_id(session, email="execution-failure-owner@example.com")
        marketplace_id = _marketplace_id(session, code="EBAY")

        started = start_execution(
            session,
            marketplace_id=marketplace_id,
            account_id=None,
            execution_type="connector.healthcheck",
            execution_uuid="exec-failure-1",
        )
        failed = fail_execution(session, execution_id=started.id)

        assert failed.status == "FAILED"
        assert failed.completed_at is not None
        assert failed.duration_ms is not None
