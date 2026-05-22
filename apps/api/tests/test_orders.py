from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    Order,
    OrderItem,
    Publisher,
    Variant,
)


def register_and_login(client: TestClient, email: str = "user@example.com") -> str:
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


def build_order_payload(quantity: int = 1) -> dict:
    return {
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
                "cover_name": "Foil Reprint Cover A",
                "printing": "Foil Edition",
                "ratio": None,
                "variant_type": "Cover A",
                "cover_artist": "Cory Walker",
                "quantity": quantity,
                "raw_item_price": 7.65,
            }
        ],
    }


def test_orders_unauthenticated_request_fails(client: TestClient) -> None:
    response = client.post("/orders", json=build_order_payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_orders_single_item_quantity_one_creates_one_copy(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)

    response = client.post(
        "/orders",
        json=build_order_payload(quantity=1),
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["total_items"] == 1
    assert response.json()["total_copies_created"] == 1

    copies = session.exec(select(InventoryCopy)).all()
    assert len(copies) == 1
    assert copies[0].copy_number == 1


def test_orders_quantity_three_creates_three_copies(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)

    response = client.post(
        "/orders",
        json=build_order_payload(quantity=3),
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["total_copies_created"] == 3

    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.copy_number)).all()
    assert len(copies) == 3
    assert [copy.copy_number for copy in copies] == [1, 2, 3]


def test_orders_multiple_items_create_correct_copy_count(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)
    payload = build_order_payload(quantity=2)
    payload["items"].append(
        {
            "title": "Saga",
            "publisher": "Image",
            "issue_number": "1",
            "cover_name": None,
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 3,
            "raw_item_price": 5.25,
        }
    )

    response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert response.status_code == 201
    assert response.json()["total_items"] == 2
    assert response.json()["total_copies_created"] == 5

    copy_count = len(session.exec(select(InventoryCopy)).all())
    assert copy_count == 5


def test_orders_and_copies_are_assigned_to_current_user(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)

    response = client.post(
        "/orders",
        json=build_order_payload(quantity=2),
        headers=auth_headers(token),
    )
    order_id = response.json()["order_id"]

    created_order = session.get(Order, order_id)
    copies = session.exec(select(InventoryCopy)).all()

    assert created_order is not None
    assert created_order.user_id is not None
    assert all(copy.user_id == created_order.user_id for copy in copies)


def test_duplicate_entities_are_reused(client: TestClient, session: Session) -> None:
    token = register_and_login(client)
    payload = build_order_payload(quantity=1)

    first_response = client.post("/orders", json=payload, headers=auth_headers(token))
    second_response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assert len(session.exec(select(Publisher)).all()) == 1
    assert len(session.exec(select(ComicTitle)).all()) == 1
    assert len(session.exec(select(ComicIssue)).all()) == 1
    assert len(session.exec(select(Variant)).all()) == 1


def test_shipping_tax_allocation_is_reasonable_and_deterministic(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)
    payload = {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 5.00,
        "tax_amount": 1.00,
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
                "quantity": 2,
                "raw_item_price": 5.00,
            },
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
            },
        ],
    }

    first_response = client.post("/orders", json=payload, headers=auth_headers(token))
    second_response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    order_items = session.exec(select(OrderItem).order_by(OrderItem.id)).all()
    first_order_items = order_items[:2]
    second_order_items = order_items[2:]

    first_shipping = sum(item.allocated_shipping for item in first_order_items)
    first_tax = sum(item.allocated_tax for item in first_order_items)
    second_shipping = sum(item.allocated_shipping for item in second_order_items)
    second_tax = sum(item.allocated_tax for item in second_order_items)

    assert first_shipping == Decimal("5.00")
    assert first_tax == Decimal("1.00")
    assert second_shipping == Decimal("5.00")
    assert second_tax == Decimal("1.00")
    assert [item.allocated_shipping for item in first_order_items] == [
        item.allocated_shipping for item in second_order_items
    ]
    assert [item.allocated_tax for item in first_order_items] == [
        item.allocated_tax for item in second_order_items
    ]


def test_invalid_quantity_creates_no_partial_records(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)
    payload = build_order_payload(quantity=0)

    response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert response.status_code == 422
    assert len(session.exec(select(Order)).all()) == 0
    assert len(session.exec(select(OrderItem)).all()) == 0
    assert len(session.exec(select(InventoryCopy)).all()) == 0


def test_blank_retailer_rejected(client: TestClient) -> None:
    token = register_and_login(client)
    payload = build_order_payload()
    payload["retailer"] = "   "

    response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert response.status_code == 422


def test_blank_title_rejected(client: TestClient) -> None:
    token = register_and_login(client)
    payload = build_order_payload()
    payload["items"][0]["title"] = "   "

    response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert response.status_code == 422


def test_blank_publisher_rejected(client: TestClient) -> None:
    token = register_and_login(client)
    payload = build_order_payload()
    payload["items"][0]["publisher"] = "   "

    response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert response.status_code == 422


def test_blank_issue_number_rejected(client: TestClient) -> None:
    token = register_and_login(client)
    payload = build_order_payload()
    payload["items"][0]["issue_number"] = "   "

    response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert response.status_code == 422


def test_zero_items_rejected(client: TestClient) -> None:
    token = register_and_login(client)
    payload = build_order_payload()
    payload["items"] = []

    response = client.post("/orders", json=payload, headers=auth_headers(token))

    assert response.status_code == 422


def test_whitespace_normalized_publisher_title_reuse(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)
    first_payload = build_order_payload()
    first_payload["items"][0]["publisher"] = "  Image  "
    first_payload["items"][0]["title"] = "  Invincible  "
    second_payload = build_order_payload()

    first_response = client.post("/orders", json=first_payload, headers=auth_headers(token))
    second_response = client.post("/orders", json=second_payload, headers=auth_headers(token))

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    publishers = session.exec(select(Publisher)).all()
    titles = session.exec(select(ComicTitle)).all()
    assert len(publishers) == 1
    assert publishers[0].name == "Image"
    assert len(titles) == 1
    assert titles[0].name == "Invincible"


def test_orders_list_unauthenticated_request_fails(client: TestClient) -> None:
    response = client.get("/orders")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_orders_list_user_sees_only_own_orders(client: TestClient) -> None:
    user_one_token = register_and_login(client, "orders-one@example.com")
    user_two_token = register_and_login(client, "orders-two@example.com")

    client.post(
        "/orders",
        json=build_order_payload(quantity=1),
        headers=auth_headers(user_one_token),
    )
    other_payload = build_order_payload(quantity=1)
    other_payload["retailer"] = "Unknown Comics"
    other_payload["items"][0]["title"] = "Saga"
    client.post("/orders", json=other_payload, headers=auth_headers(user_two_token))

    response = client.get("/orders", headers=auth_headers(user_one_token))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["retailer"] == "Whatnot"


def test_orders_list_pagination_works(client: TestClient) -> None:
    token = register_and_login(client, "orders-page@example.com")
    for retailer in ["A-Shop", "B-Shop", "C-Shop"]:
        payload = build_order_payload(quantity=1)
        payload["retailer"] = retailer
        payload["order_date"] = "2026-05-19"
        response = client.post("/orders", json=payload, headers=auth_headers(token))
        assert response.status_code == 201

    first_page = client.get("/orders?page=1&page_size=2", headers=auth_headers(token))
    second_page = client.get("/orders?page=2&page_size=2", headers=auth_headers(token))

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 1


def test_orders_list_retailer_filter_works(client: TestClient) -> None:
    token = register_and_login(client, "orders-filter@example.com")
    whatnot_payload = build_order_payload(quantity=1)
    mycomicshop_payload = build_order_payload(quantity=1)
    mycomicshop_payload["retailer"] = "MyComicShop"

    assert client.post(
        "/orders", json=whatnot_payload, headers=auth_headers(token)
    ).status_code == 201
    assert client.post(
        "/orders", json=mycomicshop_payload, headers=auth_headers(token)
    ).status_code == 201

    response = client.get("/orders?retailer=MyComicShop", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["retailer"] == "MyComicShop"


def test_order_detail_works(client: TestClient) -> None:
    token = register_and_login(client, "orders-detail@example.com")
    payload = {
        "retailer": "MyComicShop",
        "order_date": "2026-05-20",
        "source_type": "manual",
        "shipping_amount": 5.00,
        "tax_amount": 1.00,
        "items": [
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Foil Reprint Cover A",
                "printing": "Foil Edition",
                "ratio": "1:25",
                "variant_type": "Cover A",
                "cover_artist": "Cory Walker",
                "quantity": 2,
                "raw_item_price": 7.65,
            },
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover B",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.25,
            },
        ],
    }
    create_response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert create_response.status_code == 201
    order_id = create_response.json()["order_id"]

    response = client.get(f"/orders/{order_id}", headers=auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == order_id
    assert data["retailer"] == "MyComicShop"
    assert data["order_date"] == "2026-05-20"
    assert data["source_type"] == "manual"
    assert data["shipping_amount"] == "5.00"
    assert data["tax_amount"] == "1.00"
    assert data["total_amount"] == "26.55"
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Invincible"
    assert data["items"][0]["quantity"] == 2
    assert len(data["items"][0]["inventory_copy_ids"]) == 2
    assert data["items"][1]["title"] == "Saga"
    assert len(data["items"][1]["inventory_copy_ids"]) == 1


def test_user_cannot_fetch_another_users_order(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "orders-owner@example.com")
    other_token = register_and_login(client, "orders-other@example.com")
    create_response = client.post(
        "/orders",
        json=build_order_payload(quantity=1),
        headers=auth_headers(owner_token),
    )
    assert create_response.status_code == 201
    order = session.get(Order, create_response.json()["order_id"])
    assert order is not None

    response = client.get(f"/orders/{order.id}", headers=auth_headers(other_token))

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_missing_order_returns_404(client: TestClient) -> None:
    token = register_and_login(client, "orders-missing@example.com")

    response = client.get("/orders/9999", headers=auth_headers(token))

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_order_list_totals_and_counts_are_correct(client: TestClient) -> None:
    token = register_and_login(client, "orders-counts@example.com")
    payload = build_order_payload(quantity=3)

    create_response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert create_response.status_code == 201

    response = client.get("/orders", headers=auth_headers(token))

    assert response.status_code == 200
    row = response.json()["items"][0]
    assert row["total_items"] == 1
    assert row["total_copies"] == 3
    assert row["total_amount"] == "29.44"
