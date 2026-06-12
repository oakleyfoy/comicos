from __future__ import annotations

from sqlmodel import Session, select

from app.models import (
    InventoryCopy,
    Order,
    RetailerAccount,
    RetailerOrderSnapshot,
    User,
)
from app.services.user_collection_reset import reset_user_collection_data
from test_inventory import create_order, register_and_login


def _seed_retailer_account(session: Session, *, user_id: int) -> RetailerAccount:
    account = RetailerAccount(
        owner_user_id=user_id,
        retailer="midtown",
        display_name="Midtown Comics",
        username="reset-test@example.com",
        encrypted_password="enc",
        credential_version=1,
        status="connected",
        sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def test_reset_user_collection_data_dry_run_and_scoped_delete(client, session) -> None:
    victim_email = "reset-victim@example.com"
    other_email = "reset-other@example.com"
    victim_token = register_and_login(client, victim_email)
    other_token = register_and_login(client, other_email)

    create_order(client, victim_token)
    create_order(client, other_token)

    victim = session.exec(select(User).where(User.email == victim_email)).one()
    other = session.exec(select(User).where(User.email == other_email)).one()
    _seed_retailer_account(session, user_id=int(victim.id))
    session.add(
        RetailerOrderSnapshot(
            owner_user_id=int(victim.id),
            retailer_account_id=int(
                session.exec(
                    select(RetailerAccount.id).where(RetailerAccount.owner_user_id == victim.id)
                ).one()
            ),
            retailer="midtown",
            retailer_order_number="900001",
            order_status="Shipped",
            raw_snapshot_json={},
        )
    )
    session.commit()

    dry = reset_user_collection_data(session, user=victim, execute=False)
    assert dry.dry_run is True
    assert dry.total_rows > 0

    victim_inventory_before_other = len(
        session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == other.id)).all()
    )
    assert victim_inventory_before_other == 1

    reset_user_collection_data(session, user=victim, execute=True)

    assert session.exec(select(User).where(User.email == victim_email)).one() is not None
    assert session.exec(select(RetailerAccount).where(RetailerAccount.owner_user_id == victim.id)).one() is not None
    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == victim.id)).all()) == 0
    assert len(session.exec(select(Order.id).where(Order.user_id == victim.id)).all()) == 0
    assert (
        len(session.exec(select(RetailerOrderSnapshot.id).where(RetailerOrderSnapshot.owner_user_id == victim.id)).all())
        == 0
    )

    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == other.id)).all()) == 1
    assert len(session.exec(select(Order.id).where(Order.user_id == other.id)).all()) == 1
