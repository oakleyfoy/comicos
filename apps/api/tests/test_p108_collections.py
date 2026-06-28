"""P108 collection clone + reset tests."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, Order, User
from app.models.p108_collection import COLLECTION_TYPE_REAL, COLLECTION_TYPE_TEST, UserDataCollection
from app.services.collection_context import ensure_default_real_collection
from app.services.p108_collection_service import clone_collection
from test_inventory import auth_headers, register_and_login


def _seed_order_and_copy(session: Session, *, user_id: int, collection_id: int) -> None:
    order = Order(
        user_id=user_id,
        collection_id=collection_id,
        retailer="Test Shop",
        order_date=__import__("datetime").date.today(),
        total_amount=Decimal("10.00"),
    )
    session.add(order)
    session.flush()
    session.add(
        InventoryCopy(
            user_id=user_id,
            collection_id=collection_id,
            copy_number=1,
            acquisition_cost=Decimal("10.00"),
        )
    )
    session.commit()


def test_migration_default_real_collection(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p108-migrate@example.com")
    resp = client.get("/api/collections", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_collection_id"] is not None
    session.expire_all()
    user = session.exec(select(User).where(User.email == "p108-migrate@example.com")).one()
    assert user.active_collection_id == body["active_collection_id"]
    row = session.get(UserDataCollection, int(body["active_collection_id"]))
    assert row is not None
    assert row.collection_type == COLLECTION_TYPE_REAL
    assert row.name == "Oakley Real Collection"
    assert row.is_default is True
    assert len(body["items"]) >= 1


def test_clone_independent_copy(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p108-clone@example.com")
    user = session.exec(select(User).where(User.email == "p108-clone@example.com")).one()
    real = ensure_default_real_collection(session, user_id=int(user.id or 0))
    session.commit()
    _seed_order_and_copy(session, user_id=int(user.id or 0), collection_id=int(real.id or 0))

    resp = client.post(
        f"/api/collections/{real.id}/clone",
        headers=auth_headers(token),
        json={},
    )
    assert resp.status_code == 200
    clone_id = resp.json()["id"]
    session.expire_all()
    assert resp.json()["collection_type"] == COLLECTION_TYPE_TEST
    assert "Test Copy of" in resp.json()["name"]

    source_inv = session.exec(
        select(InventoryCopy).where(InventoryCopy.collection_id == real.id)
    ).all()
    clone_inv = session.exec(
        select(InventoryCopy).where(InventoryCopy.collection_id == clone_id)
    ).all()
    assert len(source_inv) == len(clone_inv) == 1
    assert source_inv[0].id != clone_inv[0].id

    session.delete(clone_inv[0])
    session.commit()
    source_after = session.exec(
        select(InventoryCopy).where(InventoryCopy.collection_id == real.id)
    ).all()
    assert len(source_after) == 1


def test_real_collection_cannot_delete_or_reset(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p108-real-guard@example.com")
    user = session.exec(select(User).where(User.email == "p108-real-guard@example.com")).one()
    real = ensure_default_real_collection(session, user_id=int(user.id or 0))
    session.commit()

    assert client.post(f"/api/collections/{real.id}/reset", headers=auth_headers(token), json={}).status_code == 403
    assert client.delete(f"/api/collections/{real.id}", headers=auth_headers(token)).status_code == 403


def test_test_collection_reset_and_delete(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p108-test-reset@example.com")
    user = session.exec(select(User).where(User.email == "p108-test-reset@example.com")).one()
    real = ensure_default_real_collection(session, user_id=int(user.id or 0))
    clone = clone_collection(session, user_id=int(user.id or 0), source_collection_id=int(real.id or 0))
    session.commit()
    session.add(
        InventoryCopy(
            user_id=int(user.id or 0),
            collection_id=int(clone.id or 0),
            copy_number=1,
            acquisition_cost=Decimal("5.00"),
        )
    )
    session.commit()

    resp = client.post(f"/api/collections/{clone.id}/reset", headers=auth_headers(token), json={})
    assert resp.status_code == 200
    remaining = session.exec(
        select(InventoryCopy).where(InventoryCopy.collection_id == clone.id)
    ).all()
    assert remaining == []

    session.add(
        InventoryCopy(
            user_id=int(user.id or 0),
            collection_id=int(clone.id or 0),
            copy_number=1,
            acquisition_cost=Decimal("5.00"),
        )
    )
    session.commit()
    assert client.delete(f"/api/collections/{clone.id}", headers=auth_headers(token)).status_code == 204
    session.expire_all()
    row = session.get(UserDataCollection, int(clone.id or 0))
    assert row is not None
    assert row.deleted_at is not None


def test_inventory_filtered_by_active_collection(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p108-filter@example.com")
    user = session.exec(select(User).where(User.email == "p108-filter@example.com")).one()
    real = ensure_default_real_collection(session, user_id=int(user.id or 0))
    clone = clone_collection(session, user_id=int(user.id or 0), source_collection_id=int(real.id or 0))
    session.commit()

    session.add(
        InventoryCopy(
            user_id=int(user.id or 0),
            collection_id=int(real.id or 0),
            copy_number=1,
            acquisition_cost=Decimal("1.00"),
        )
    )
    session.commit()

    inv = client.get("/inventory", headers=auth_headers(token))
    assert inv.status_code == 200
    assert inv.json()["total"] >= 1

    client.post("/api/collections/active", headers=auth_headers(token), json={"collection_id": clone.id})
    inv2 = client.get("/inventory", headers=auth_headers(token))
    assert inv2.status_code == 200
    assert inv2.json()["total"] == 0
