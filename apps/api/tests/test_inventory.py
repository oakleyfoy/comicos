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
    retailer: str = "Whatnot",
    order_date: str = "2026-05-19",
    shipping_amount: float = 0,
    tax_amount: float = 0,
    items: list[dict] | None = None,
) -> dict:
    payload = {
        "retailer": retailer,
        "order_date": order_date,
        "source_type": "manual",
        "shipping_amount": shipping_amount,
        "tax_amount": tax_amount,
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
                "raw_item_price": 5.00,
            }
        ],
    }
    response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()

def test_inventory_unauthenticated_request_fails(client: TestClient) -> None:
    response = client.get("/inventory")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_inventory_user_sees_only_own_inventory(client: TestClient) -> None:
    user_one_token = register_and_login(client, "one@example.com")
    user_two_token = register_and_login(client, "two@example.com")

    create_order(
        client,
        user_one_token,
        items=[
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
                "raw_item_price": 5.00,
            }
        ],
    )
    create_order(
        client,
        user_two_token,
        items=[
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
                "raw_item_price": 6.00,
            }
        ],
    )

    response = client.get("/inventory", headers=auth_headers(user_one_token))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Invincible"


def test_inventory_pagination_works(client: TestClient) -> None:
    token = register_and_login(client, "page@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 3,
                "raw_item_price": 5.00,
            }
        ],
    )

    first_page = client.get("/inventory?page=1&page_size=2", headers=auth_headers(token))
    second_page = client.get("/inventory?page=2&page_size=2", headers=auth_headers(token))

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 1
    assert first_page.json()["items"][0]["inventory_copy_id"] != second_page.json()["items"][0][
        "inventory_copy_id"
    ]


def test_inventory_search_by_title_works(client: TestClient) -> None:
    token = register_and_login(client, "search@example.com")
    create_order(
        client,
        token,
        items=[
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
                "raw_item_price": 5.00,
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
                "raw_item_price": 6.00,
            },
        ],
    )

    response = client.get("/inventory?search=Saga", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Saga"


def test_inventory_rejects_release_year_zero(client: TestClient) -> None:
    token = register_and_login(client, "release-year-zero@example.com")

    response = client.get(
        "/inventory?page=1&page_size=25&release_year=0&sort_by=purchase_date&sort_dir=asc",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_inventory_filter_by_release_year_works(client: TestClient) -> None:
    token = register_and_login(client, "release-year-inv@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "release_year": 2024,
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 6.00,
            }
        ],
    )
    create_order(
        client,
        token,
        items=[
            {
                "title": "Monstress",
                "publisher": "Image",
                "issue_number": "1",
                "release_year": 2026,
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 8.50,
            }
        ],
    )

    filtered = client.get("/inventory?release_year=2024", headers=auth_headers(token))
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["total"] == 1
    row = payload["items"][0]
    assert row["release_year"] == 2024
    assert row["title"] == "Saga"


def test_inventory_filters_by_release_calendar_present_or_missing(
    client: TestClient,
) -> None:
    token = register_and_login(client, "calendar-inv@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Inkblot",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": "2025-06-01",
                "release_year": 2025,
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            }
        ],
    )
    create_order(
        client,
        token,
        items=[
            {
                "title": "Dept H",
                "publisher": "Dark Horse",
                "issue_number": "1",
                "release_year": 2026,
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 3.49,
            }
        ],
    )

    present = client.get("/inventory?release_calendar=present", headers=auth_headers(token))
    missing = client.get("/inventory?release_calendar=missing", headers=auth_headers(token))

    assert present.status_code == 200 and missing.status_code == 200
    assert present.json()["total"] == 1
    assert missing.json()["total"] == 1
    assert present.json()["items"][0]["title"] == "Inkblot"
    assert missing.json()["items"][0]["title"] == "Dept H"
    assert present.json()["items"][0]["release_date"] == "2025-06-01"
    assert present.json()["items"][0]["release_year"] == 2025
    assert missing.json()["items"][0]["release_date"] is None


def test_inventory_filter_by_publisher_works(client: TestClient) -> None:
    token = register_and_login(client, "publisher@example.com")
    create_order(
        client,
        token,
        items=[
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
                "raw_item_price": 5.00,
            },
            {
                "title": "Spider-Man",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "Cover B",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 6.00,
            },
        ],
    )

    response = client.get("/inventory?publisher=Marvel", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["publisher"] == "Marvel"


def test_inventory_filter_by_hold_status_works(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "hold@example.com")
    create_order(
        client,
        token,
        items=[
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
            }
        ],
    )
    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()
    copies[0].hold_status = "sell"
    session.add(copies[0])
    session.commit()

    response = client.get("/inventory?hold_status=sell", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["hold_status"] == "sell"


def test_inventory_filter_by_grade_status_works(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "grade@example.com")
    create_order(
        client,
        token,
        items=[
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
            }
        ],
    )
    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()
    copies[1].grade_status = "graded"
    session.add(copies[1])
    session.commit()

    response = client.get("/inventory?grade_status=graded", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["grade_status"] == "graded"


def test_inventory_sort_by_acquisition_cost_works(client: TestClient) -> None:
    token = register_and_login(client, "sort@example.com")
    create_order(
        client,
        token,
        items=[
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
                "raw_item_price": 5.00,
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
                "raw_item_price": 10.00,
            },
        ],
    )

    response = client.get(
        "/inventory?sort_by=acquisition_cost&sort_dir=desc",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    costs = [Decimal(item["acquisition_cost"]) for item in response.json()["items"]]
    assert costs == sorted(costs, reverse=True)


def test_inventory_invalid_sort_by_fails(client: TestClient) -> None:
    token = register_and_login(client, "bad-sort@example.com")

    response = client.get("/inventory?sort_by=bad_field", headers=auth_headers(token))

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid sort_by value"}


def test_inventory_detail_unauthenticated_request_fails(client: TestClient) -> None:
    response = client.get("/inventory/1")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_inventory_detail_returns_owned_copy(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "detail@example.com")
    create_order(
        client,
        token,
        retailer="MyComicShop",
        order_date="2026-05-20",
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Foil Reprint Cover A",
                "printing": "Foil Edition",
                "ratio": "1:25",
                "variant_type": "Virgin",
                "cover_artist": "Cory Walker",
                "quantity": 1,
                "raw_item_price": 7.65,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy)).one()
    copy.current_fmv = Decimal("12.50")
    copy.grade_status = "graded"
    copy.hold_status = "sell"
    copy.star_rating = 5
    copy.condition_notes = "Sharp corners, clean spine."
    session.add(copy)
    session.commit()

    response = client.get(f"/inventory/{copy.id}", headers=auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert data["inventory_copy_id"] == copy.id
    assert data["copy_number"] == 1
    assert data["title"] == "Invincible"
    assert data["publisher"] == "Image"
    assert data["issue_number"] == "1"
    assert data["cover_name"] == "Foil Reprint Cover A"
    assert data["printing"] == "Foil Edition"
    assert data["ratio"] == "1:25"
    assert data["variant_type"] == "Virgin"
    assert data["cover_artist"] == "Cory Walker"
    assert data["retailer"] == "MyComicShop"
    assert data["order_date"] == "2026-05-20"
    assert data["source_type"] == "manual"
    assert Decimal(data["acquisition_cost"]) == Decimal("7.65")
    assert Decimal(data["current_fmv"]) == Decimal("12.50")
    assert Decimal(data["gain_loss"]) == Decimal("4.85")
    assert data["grade_status"] == "graded"
    assert data["hold_status"] == "sell"
    assert data["star_rating"] == 5
    assert data["condition_notes"] == "Sharp corners, clean spine."
    assert isinstance(data["order_id"], int)
    assert isinstance(data["order_item_id"], int)
    assert isinstance(data["variant_id"], int)
    assert data["created_at"]


def test_inventory_detail_other_user_copy_returns_404(client: TestClient, session: Session) -> None:
    owner_token = register_and_login(client, "owner@example.com")
    intruder_token = register_and_login(client, "intruder@example.com")
    create_order(client, owner_token)
    copy = session.exec(select(InventoryCopy)).one()

    response = client.get(f"/inventory/{copy.id}", headers=auth_headers(intruder_token))

    assert response.status_code == 404
    assert response.json() == {"detail": "Inventory copy not found"}


def test_inventory_detail_missing_copy_returns_404(client: TestClient) -> None:
    token = register_and_login(client, "missing@example.com")

    response = client.get("/inventory/9999", headers=auth_headers(token))

    assert response.status_code == 404
    assert response.json() == {"detail": "Inventory copy not found"}


def test_inventory_summary_metrics_calculate_correctly(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "summary@example.com")
    create_order(
        client,
        token,
        items=[
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
                "cover_name": "Cover B",
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
    copies[0].current_fmv = Decimal("9.00")
    copies[0].grade_status = "raw"
    copies[0].hold_status = "hold"
    copies[1].current_fmv = None
    copies[1].grade_status = "graded"
    copies[1].hold_status = "sell"
    copies[2].current_fmv = Decimal("12.50")
    copies[2].grade_status = "raw"
    copies[2].hold_status = "hold"
    for copy in copies:
        session.add(copy)
    session.commit()

    response = client.get("/inventory/summary", headers=auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert data["total_copies"] == 3
    assert Decimal(data["total_cost_basis"]) == Decimal("20.00")
    assert Decimal(data["total_current_fmv"]) == Decimal("21.50")
    assert Decimal(data["total_unrealized_gain_loss"]) == Decimal("1.50")
    assert data["raw_count"] == 2
    assert data["graded_count"] == 1
    assert data["hold_count"] == 2
    assert data["sell_count"] == 1


def test_inventory_list_enrichment_card_skips_row_attachments(client: TestClient) -> None:
    token = register_and_login(client, "card-list@example.com")
    create_order(client, token)

    full = client.get("/inventory?page=1&page_size=5", headers=auth_headers(token))
    card = client.get(
        "/inventory?page=1&page_size=5&list_enrichment=card",
        headers=auth_headers(token),
    )
    assert full.status_code == 200
    assert card.status_code == 200

    full_item = full.json()["items"][0]
    card_item = card.json()["items"][0]
    assert card_item["title"] == full_item["title"]
    assert card_item["inventory_copy_id"] == full_item["inventory_copy_id"]
    assert card_item.get("inventory_risks") in (None, [])
    assert card_item.get("inventory_action_center") is None
    assert card_item.get("duplicate_ownership") is None
    assert card_item.get("run_detection") is None
