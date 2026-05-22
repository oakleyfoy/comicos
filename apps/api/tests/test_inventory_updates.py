from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy


def register_and_login(client: TestClient, email: str) -> str:
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


def create_order(
    client: TestClient,
    token: str,
    *,
    quantity: int = 1,
) -> None:
    response = client.post(
        "/orders",
        headers=auth_headers(token),
        json={
            "retailer": "Whatnot",
            "order_date": "2026-05-19",
            "source_type": "manual",
            "shipping_amount": 4.99,
            "tax_amount": 1.50,
            "items": [
                {
                    "title": "Invincible",
                    "publisher": "Image",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": quantity,
                    "raw_item_price": 7.65,
                }
            ],
        },
    )
    assert response.status_code == 201


def test_inventory_update_unauthorized_fails(client: TestClient) -> None:
    response = client.patch("/inventory/1", json={"hold_status": "sell"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_user_cannot_update_another_user_inventory(
    client: TestClient,
    session: Session,
) -> None:
    owner_token = register_and_login(client, "owner@example.com")
    other_token = register_and_login(client, "other@example.com")
    create_order(client, owner_token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(other_token),
        json={"hold_status": "sell"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Inventory copy not found"}


def test_single_inventory_update_works(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "single@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={
            "current_fmv": "12.50",
            "hold_status": "sell",
            "star_rating": 4,
            "grade_status": "submitted",
            "condition_notes": "Pressing candidate.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["current_fmv"] == "12.50"
    assert data["hold_status"] == "sell"
    assert data["star_rating"] == 4
    assert data["grade_status"] == "submitted"

    session.expire_all()
    updated_copy = session.get(InventoryCopy, copy.id)
    assert updated_copy is not None
    assert updated_copy.current_fmv == Decimal("12.50")
    assert updated_copy.hold_status == "sell"
    assert updated_copy.star_rating == 4
    assert updated_copy.grade_status == "submitted"
    assert updated_copy.condition_notes == "Pressing candidate."


def test_bulk_inventory_update_works(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "bulk@example.com")
    create_order(client, token, quantity=3)
    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()

    response = client.patch(
        "/inventory/bulk",
        headers=auth_headers(token),
        json={
            "inventory_copy_ids": [copy.id for copy in copies],
            "updates": {"hold_status": "sell"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"updated_count": 3}

    session.expire_all()
    updated_copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()
    assert all(copy.hold_status == "sell" for copy in updated_copies)


def test_invalid_star_rating_fails(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "stars@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"star_rating": 6},
    )

    assert response.status_code == 422


def test_invalid_hold_status_fails(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "holdstatus@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"hold_status": "archive"},
    )

    assert response.status_code == 422


def test_invalid_grade_status_fails(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gradestatus@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"grade_status": "slabbed"},
    )

    assert response.status_code == 422


def test_summary_recalculates_after_fmv_update(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "summary-update@example.com")
    create_order(client, token, quantity=2)
    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()

    response = client.patch(
        f"/inventory/{copies[0].id}",
        headers=auth_headers(token),
        json={"current_fmv": "15.00"},
    )
    assert response.status_code == 200

    summary_response = client.get("/inventory/summary", headers=auth_headers(token))

    assert summary_response.status_code == 200
    data = summary_response.json()
    assert Decimal(data["total_current_fmv"]) == Decimal("15.00")
    assert Decimal(data["total_unrealized_gain_loss"]) == Decimal("-6.80")
