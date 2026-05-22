from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, InventoryFmvSnapshot


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
    items: list[dict] | None = None,
) -> None:
    response = client.post(
        "/orders",
        headers=auth_headers(token),
        json={
            "retailer": "Whatnot",
            "order_date": "2026-05-19",
            "source_type": "manual",
            "shipping_amount": 0,
            "tax_amount": 0,
            "items": items
            or [
                {
                    "title": "Invincible",
                    "publisher": "Image",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 7.65,
                }
            ],
        },
    )
    assert response.status_code == 201


def test_fmv_update_creates_snapshot(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "history-create@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"current_fmv": "12.50"},
    )

    assert response.status_code == 200
    session.expire_all()
    snapshots = session.exec(select(InventoryFmvSnapshot)).all()
    assert len(snapshots) == 1
    assert snapshots[0].inventory_copy_id == copy.id
    assert snapshots[0].previous_fmv is None
    assert snapshots[0].new_fmv == Decimal("12.50")
    assert snapshots[0].source == "manual"


def test_unchanged_fmv_creates_no_snapshot(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "history-unchanged@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()

    first_update = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"current_fmv": "12.50"},
    )
    assert first_update.status_code == 200

    second_update = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"current_fmv": "12.50"},
    )
    assert second_update.status_code == 200

    session.expire_all()
    snapshots = session.exec(select(InventoryFmvSnapshot)).all()
    assert len(snapshots) == 1


def test_user_cannot_access_another_user_history(
    client: TestClient,
    session: Session,
) -> None:
    owner_token = register_and_login(client, "history-owner@example.com")
    intruder_token = register_and_login(client, "history-intruder@example.com")
    create_order(client, owner_token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.get(
        f"/inventory/{copy.id}/fmv-history",
        headers=auth_headers(intruder_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Inventory copy not found"}


def test_history_ordering_is_newest_first(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "history-order@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()

    first_update = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"current_fmv": "10.00"},
    )
    assert first_update.status_code == 200
    second_update = client.patch(
        f"/inventory/{copy.id}",
        headers=auth_headers(token),
        json={"current_fmv": "15.00"},
    )
    assert second_update.status_code == 200

    snapshots = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id == copy.id)
        .order_by(InventoryFmvSnapshot.id.asc())
    ).all()
    snapshots[0].changed_at = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    snapshots[1].changed_at = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    for snapshot in snapshots:
        session.add(snapshot)
    session.commit()

    response = client.get(
        f"/inventory/{copy.id}/fmv-history",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert [item["new_fmv"] for item in data] == ["15.00", "10.00"]
    assert data[0]["previous_fmv"] == "10.00"
    assert data[1]["previous_fmv"] is None
    assert data[0]["source"] == "manual"


def test_performance_metrics_calculate_correctly(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "performance@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.00,
            },
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "B",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 6.00,
            },
            {
                "title": "Department of Truth",
                "publisher": "Image",
                "issue_number": "5",
                "cover_name": "C",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 7.00,
            },
            {
                "title": "Ultimate Spider-Man",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "D",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 8.00,
            },
            {
                "title": "Batman",
                "publisher": "DC",
                "issue_number": "125",
                "cover_name": "E",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 9.00,
            },
            {
                "title": "X-Men",
                "publisher": "Marvel",
                "issue_number": "35",
                "cover_name": "F",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
            },
        ],
    )

    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()
    fmvs = [
        Decimal("15.00"),
        Decimal("4.00"),
        Decimal("20.00"),
        Decimal("6.00"),
        Decimal("18.00"),
        Decimal("9.00"),
    ]
    for copy, current_fmv in zip(copies, fmvs, strict=True):
        copy.current_fmv = current_fmv
        session.add(copy)
    session.commit()

    response = client.get("/portfolio/performance", headers=auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["total_cost_basis"]) == Decimal("45.00")
    assert Decimal(data["total_current_fmv"]) == Decimal("72.00")
    assert Decimal(data["total_unrealized_gain_loss"]) == Decimal("27.00")

    assert [item["title"] for item in data["top_gainers"]] == [
        "Department of Truth",
        "Invincible",
        "Batman",
    ]
    assert [item["title"] for item in data["top_losers"]] == [
        "Saga",
        "Ultimate Spider-Man",
        "X-Men",
    ]
    assert [item["title"] for item in data["highest_value_books"]] == [
        "Department of Truth",
        "Batman",
        "Invincible",
        "X-Men",
        "Ultimate Spider-Man",
    ]
    assert len(data["highest_value_books"]) == 5
