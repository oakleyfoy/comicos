from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import DraftImport, InventoryCopy, Order, ReleaseIssue, ReleaseSeries, User
from app.schemas.ai import ParseOrderResponse

VALID_PUBLISHER_AUTOFILL_SOURCES = frozenset(
    {
        "metadata_catalog",
        "metadata_registry",
        "metadata_prior_issue",
        "metadata_ai",
    }
)
PUBLISHER_AUTOFILL_CONFIDENCE_MIN = 0.84


def assert_publisher_autofill_applied(item: dict, *, expected_publisher: str) -> None:
    assert item["publisher"] == expected_publisher
    assert item["metadata_autofill_source"] in VALID_PUBLISHER_AUTOFILL_SOURCES
    assert item["publisher_autofill_confidence"] is not None
    assert item["publisher_autofill_confidence"] >= PUBLISHER_AUTOFILL_CONFIDENCE_MIN
    assert item["metadata_review_required"] is False
    review_notes = item.get("metadata_review_notes") or []
    assert not any("Publisher missing" in note for note in review_notes)


def assert_publisher_autofill_unresolved(item: dict) -> None:
    assert item.get("publisher") is None
    assert item.get("metadata_autofill_source") is None
    assert item.get("publisher_autofill_confidence") is None
    assert item["metadata_review_required"] is True
    review_notes = item.get("metadata_review_notes") or []
    assert any("Publisher missing" in note for note in review_notes)


def assert_explicit_publisher_not_autofilled(item: dict, *, expected_publisher: str) -> None:
    assert item["publisher"] == expected_publisher
    assert item.get("metadata_autofill_source") is None
    assert item.get("publisher_autofill_confidence") is None


def _owner_user_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_release_catalog_issue(
    session: Session,
    *,
    owner_user_id: int,
    series_name: str,
    publisher: str,
    issue_number: str = "1",
) -> None:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher=publisher,
        series_name=series_name,
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    session.add(
        ReleaseIssue(
            owner_user_id=owner_user_id,
            release_uuid=f"import-test-{series_name.lower().replace(' ', '-')}-{issue_number}",
            series_id=int(series.id or 0),
            issue_number=issue_number,
            title=f"{series_name} #{issue_number}",
            release_status="SCHEDULED",
            release_date=date.today() + timedelta(days=14),
        )
    )
    session.commit()


def register_and_login(client: TestClient, email: str = "imports@example.com") -> str:
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


def build_mock_draft() -> ParseOrderResponse:
    return ParseOrderResponse.model_validate(
        {
            "retailer": "Whatnot",
            "order_date": "2026-05-21",
            "source_type": "ai_draft",
            "shipping_amount": Decimal("4.99"),
            "tax_amount": Decimal("1.50"),
            "items": [
                {
                    "publisher": "Image",
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 2,
                    "raw_item_price": Decimal("7.65"),
                }
            ],
            "warnings": ["Review ratio before confirming."],
            "confidence_score": 0.66,
        }
    )


def mock_parser(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.imports.parse_order_draft_from_text",
        lambda raw_text: build_mock_draft(),
    )


def seed_import(
    session: Session,
    *,
    user_id: int,
    raw_text: str,
    status: str = "draft",
    retailer: str | None = "Whatnot",
    confidence_score: Decimal = Decimal("0.66"),
    created_at: datetime,
    updated_at: datetime,
    linked_order_id: int | None = None,
) -> DraftImport:
    draft = build_mock_draft().model_copy(
        update={
            "retailer": retailer,
            "confidence_score": float(confidence_score),
        }
    )
    draft_import = DraftImport(
        user_id=user_id,
        raw_text=raw_text,
        parsed_payload_json=draft.model_dump(mode="json"),
        confidence_score=confidence_score,
        status=status,
        linked_order_id=linked_order_id,
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(draft_import)
    session.commit()
    session.refresh(draft_import)
    return draft_import


def test_create_import_saves_draft_without_creating_inventory(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client)
    mock_parser(monkeypatch)

    response = client.post(
        "/imports",
        json={"raw_text": "Whatnot receipt text"},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert data["order_id"] is None
    assert data["parsed_payload_json"]["retailer"] == "Whatnot"
    assert len(session.exec(select(DraftImport)).all()) == 1
    assert len(session.exec(select(Order)).all()) == 0
    assert len(session.exec(select(InventoryCopy)).all()) == 0


def test_create_manual_import_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/imports/manual",
        json={
            "raw_text": "manual notes",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "shipping_amount": "4.99",
            "tax_amount": "1.50",
            "items": [
                {
                    "publisher": "Image",
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "7.65",
                }
            ],
        },
    )

    assert response.status_code == 401


def test_create_manual_import_saves_draft_without_creating_inventory(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)

    response = client.post(
        "/imports/manual",
        json={
            "raw_text": "manual notes",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "4.99",
            "tax_amount": "1.50",
            "items": [
                {
                    "publisher": "Image",
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 2,
                    "raw_item_price": "7.65",
                }
            ],
            "warnings": ["Manual draft review required."],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert data["order_id"] is None
    assert data["raw_text"] == "manual notes"
    assert data["parsed_payload_json"]["source_type"] == "manual_draft"
    assert data["parsed_payload_json"]["retailer"] == "Midtown"
    assert len(session.exec(select(DraftImport)).all()) == 1
    assert len(session.exec(select(Order)).all()) == 0
    assert len(session.exec(select(InventoryCopy)).all()) == 0


def test_get_imports_filters_search_sort_and_pagination(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, email="owner@example.com")
    other_token = register_and_login(client, email="other@example.com")
    del other_token

    owner = session.exec(select(User).where(User.email == "owner@example.com")).one()
    other = session.exec(select(User).where(User.email == "other@example.com")).one()
    base_time = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

    seed_import(
        session,
        user_id=owner.id,
        raw_text="Whatnot Midtown receipt",
        status="draft",
        retailer="Whatnot",
        confidence_score=Decimal("0.80"),
        created_at=base_time,
        updated_at=base_time + timedelta(minutes=1),
    )
    seed_import(
        session,
        user_id=owner.id,
        raw_text="Discarded ebay invoice text",
        status="discarded",
        retailer="eBay",
        confidence_score=Decimal("0.30"),
        created_at=base_time + timedelta(minutes=2),
        updated_at=base_time + timedelta(minutes=3),
    )
    seed_import(
        session,
        user_id=owner.id,
        raw_text="Confirmed retailer invoice",
        status="confirmed",
        retailer="Midtown",
        confidence_score=Decimal("0.55"),
        created_at=base_time + timedelta(minutes=4),
        updated_at=base_time + timedelta(minutes=5),
        linked_order_id=42,
    )
    seed_import(
        session,
        user_id=other.id,
        raw_text="Other user import",
        status="draft",
        retailer="Forbidden",
        confidence_score=Decimal("0.99"),
        created_at=base_time + timedelta(minutes=6),
        updated_at=base_time + timedelta(minutes=7),
    )

    list_response = client.get(
        "/imports?sort_by=confidence_score&sort_dir=asc&page=1&page_size=2",
        headers=auth_headers(token),
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total"] == 3
    assert [item["status"] for item in data["items"]] == ["discarded", "confirmed"]

    second_page = client.get(
        "/imports?sort_by=confidence_score&sort_dir=asc&page=2&page_size=2",
        headers=auth_headers(token),
    )
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 3
    assert [item["status"] for item in second_page.json()["items"]] == ["draft"]

    filtered_response = client.get(
        "/imports?status=confirmed&search=midtown",
        headers=auth_headers(token),
    )
    assert filtered_response.status_code == 200
    assert filtered_response.json()["total"] == 1
    assert filtered_response.json()["items"][0]["status"] == "confirmed"
    assert filtered_response.json()["items"][0]["order_id"] == 42


def test_get_imports_invalid_status_returns_validation_error(client: TestClient) -> None:
    token = register_and_login(client)

    response = client.get("/imports?status=bad-status", headers=auth_headers(token))

    assert response.status_code == 422


def test_get_imports_invalid_sort_by_returns_400(client: TestClient) -> None:
    token = register_and_login(client)

    response = client.get("/imports?sort_by=bad_sort", headers=auth_headers(token))

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid sort_by value"}


def test_get_detail_and_patch_import_flow(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client)
    mock_parser(monkeypatch)

    create_response = client.post(
        "/imports",
        json={"raw_text": "Whatnot receipt text"},
        headers=auth_headers(token),
    )
    import_id = create_response.json()["id"]

    detail_response = client.get(f"/imports/{import_id}", headers=auth_headers(token))
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == import_id
    assert detail_response.json()["order_id"] is None

    patch_response = client.patch(
        f"/imports/{import_id}",
        json={
            "raw_text": "Updated pasted text",
            "parsed_payload_json": {
                "retailer": "eBay",
                "order_date": "2026-05-20",
                "source_type": "ai_draft",
                "shipping_amount": "0.00",
                "tax_amount": "0.00",
                "items": [
                    {
                        "publisher": "Marvel",
                        "title": "Ultimate Spider-Man",
                        "issue_number": "2",
                        "cover_name": None,
                        "printing": None,
                        "ratio": None,
                        "variant_type": None,
                        "cover_artist": None,
                        "quantity": 1,
                        "raw_item_price": "9.99",
                    }
                ],
                "warnings": [],
                "confidence_score": 0.5,
            },
            "confidence_score": 0.5,
        },
        headers=auth_headers(token),
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["raw_text"] == "Updated pasted text"
    assert patch_response.json()["parsed_payload_json"]["retailer"] == "eBay"


def test_patch_import_auto_fills_obvious_publishers_server_side(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client, email="normalize@example.com")
    mock_parser(monkeypatch)

    create_response = client.post(
        "/imports",
        json={"raw_text": "Batman #1 preorder"},
        headers=auth_headers(token),
    )
    import_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/imports/{import_id}",
        json={
            "raw_text": "Batman #1 preorder",
            "parsed_payload_json": {
                "retailer": "Midtown",
                "order_date": "2026-05-20",
                "source_type": "gmail_draft",
                "shipping_amount": "0.00",
                "tax_amount": "0.00",
                "items": [
                    {
                        "publisher": None,
                        "title": "Batman",
                        "issue_number": "1",
                        "cover_name": None,
                        "printing": None,
                        "ratio": None,
                        "variant_type": None,
                        "cover_artist": None,
                        "quantity": 1,
                        "raw_item_price": "4.99",
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            },
        },
        headers=auth_headers(token),
    )

    assert patch_response.status_code == 200
    payload = patch_response.json()["parsed_payload_json"]
    item = payload["items"][0]
    assert_publisher_autofill_applied(item, expected_publisher="DC")
    assert item["metadata_autofill_source"] == "metadata_ai"


def test_confirm_import_uses_deterministic_publisher_normalization(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, email="normalized-confirm@example.com")

    create_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Invincible #1",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "4.99",
            "tax_amount": "1.50",
            "items": [
                {
                    "publisher": None,
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 2,
                    "raw_item_price": "7.65",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    created_item = create_response.json()["parsed_payload_json"]["items"][0]
    assert_publisher_autofill_applied(created_item, expected_publisher="Image")
    assert created_item["metadata_autofill_source"] == "metadata_ai"

    import_id = create_response.json()["id"]
    confirm_response = client.post(f"/imports/{import_id}/confirm", headers=auth_headers(token))

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"
    assert len(session.exec(select(Order)).all()) == 1
    assert len(session.exec(select(InventoryCopy)).all()) == 2


def test_confirm_import_still_rejects_items_with_unresolved_publishers(
    client: TestClient,
) -> None:
    token = register_and_login(client, email="unresolved-publisher@example.com")

    create_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Babylon Cove #1",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": None,
                    "title": "Babylon Cove",
                    "issue_number": "1",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    unresolved_item = create_response.json()["parsed_payload_json"]["items"][0]
    assert_publisher_autofill_unresolved(unresolved_item)

    import_id = create_response.json()["id"]
    confirm_response = client.post(f"/imports/{import_id}/confirm", headers=auth_headers(token))

    assert confirm_response.status_code == 422
    assert "items[1]: publisher" in confirm_response.json()["detail"]


def test_manual_import_blank_publisher_odin_resolves_from_release_catalog(
    client: TestClient,
) -> None:
    email = "odin-catalog-autofill@example.com"
    token = register_and_login(client, email=email)
    with Session(get_engine()) as session:
        _seed_release_catalog_issue(
            session,
            owner_user_id=_owner_user_id(session, email),
            series_name="Odin",
            publisher="Image Comics",
            issue_number="1",
        )

    create_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Odin #1",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": None,
                    "title": "Odin",
                    "issue_number": "1",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    item = create_response.json()["parsed_payload_json"]["items"][0]
    assert_publisher_autofill_applied(item, expected_publisher="Image Comics")
    assert item["metadata_autofill_source"] == "metadata_catalog"


def test_get_imports_can_filter_for_metadata_review_items(client: TestClient) -> None:
    token = register_and_login(client, email="review-filter@example.com")

    flagged_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Indie House Babylon Cove #01",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Indie House",
                    "title": "Babylon Cove",
                    "issue_number": "01",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert flagged_response.status_code == 201
    flagged_id = flagged_response.json()["id"]
    assert_explicit_publisher_not_autofilled(
        flagged_response.json()["parsed_payload_json"]["items"][0],
        expected_publisher="Indie House",
    )

    clean_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Marvel Comics Ultimate Spider-Man #001",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Marvel Comics",
                    "title": "Ultimate Spider-Man",
                    "issue_number": "001",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "5.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert clean_response.status_code == 201
    clean_id = clean_response.json()["id"]

    review_only = client.get("/imports?needs_metadata_review=true", headers=auth_headers(token))
    assert review_only.status_code == 200
    review_items = review_only.json()["items"]
    assert [item["id"] for item in review_items] == [flagged_id]
    assert review_items[0]["needs_metadata_review"] is True
    assert review_items[0]["metadata_review_item_count"] == 1

    no_review = client.get("/imports?needs_metadata_review=false", headers=auth_headers(token))
    assert no_review.status_code == 200
    assert [item["id"] for item in no_review.json()["items"]] == [clean_id]
    assert no_review.json()["items"][0]["needs_metadata_review"] is False


def test_import_response_payload_includes_metadata_review_fields(client: TestClient) -> None:
    token = register_and_login(client, email="review-payload@example.com")

    response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Indie House Babylon Cove #01",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Indie House",
                    "title": "Babylon Cove",
                    "issue_number": "01",
                    "cover_name": "  foil edition ",
                    "printing": None,
                    "ratio": None,
                    "variant_type": "  cover a ",
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    data = response.json()
    item = data["parsed_payload_json"]["items"][0]

    assert data["needs_metadata_review"] is True
    assert data["metadata_review_item_count"] == 1
    assert item["raw_publisher"] == "Indie House"
    assert item["canonical_publisher"] == "Indie House"
    assert item["raw_title"] == "Babylon Cove"
    assert item["canonical_title"] == "Babylon Cove"
    assert item["raw_issue_number"] == "01"
    assert item["canonical_issue_number"] == "1"
    assert item["raw_variant_text"] == "foil edition / cover a"
    assert item["canonical_variant_text"] == "Foil Edition / Cover A"
    assert item["metadata_review_required"] is True
    assert_explicit_publisher_not_autofilled(item, expected_publisher="Indie House")
    assert item["metadata_review_notes"] == [
        "Publisher preserved from raw parse. Review canonical publisher if needed."
    ]


def test_confirm_import_is_only_path_that_creates_order_and_inventory(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client)
    mock_parser(monkeypatch)

    create_response = client.post(
        "/imports",
        json={"raw_text": "Whatnot receipt text"},
        headers=auth_headers(token),
    )
    import_id = create_response.json()["id"]

    assert len(session.exec(select(Order)).all()) == 0
    assert len(session.exec(select(InventoryCopy)).all()) == 0

    confirm_response = client.post(f"/imports/{import_id}/confirm", headers=auth_headers(token))

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"
    assert confirm_response.json()["total_copies_created"] == 2
    assert len(session.exec(select(Order)).all()) == 1
    assert len(session.exec(select(InventoryCopy)).all()) == 2

    saved_import = session.get(DraftImport, import_id)
    assert saved_import is not None
    assert saved_import.status == "confirmed"
    assert saved_import.linked_order_id == confirm_response.json()["order_id"]

    detail_response = client.get(f"/imports/{import_id}", headers=auth_headers(token))
    assert detail_response.status_code == 200
    assert detail_response.json()["order_id"] == confirm_response.json()["order_id"]


def test_confirm_manual_import_creates_order_and_inventory(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client)

    create_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "manual notes",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "4.99",
            "tax_amount": "1.50",
            "items": [
                {
                    "publisher": "Image",
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 2,
                    "raw_item_price": "7.65",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    import_id = create_response.json()["id"]

    confirm_response = client.post(f"/imports/{import_id}/confirm", headers=auth_headers(token))

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"
    assert confirm_response.json()["total_copies_created"] == 2
    assert len(session.exec(select(Order)).all()) == 1
    assert len(session.exec(select(InventoryCopy)).all()) == 2

    saved_import = session.get(DraftImport, import_id)
    assert saved_import is not None
    assert saved_import.status == "confirmed"
    assert saved_import.linked_order_id == confirm_response.json()["order_id"]


def test_manual_import_user_ownership_enforced(
    client: TestClient,
) -> None:
    owner_token = register_and_login(client, email="manual-owner@example.com")
    other_token = register_and_login(client, email="manual-other@example.com")

    create_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "manual notes",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "4.99",
            "tax_amount": "1.50",
            "items": [
                {
                    "publisher": "Image",
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "7.65",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(owner_token),
    )
    import_id = create_response.json()["id"]

    detail_response = client.get(f"/imports/{import_id}", headers=auth_headers(other_token))
    assert detail_response.status_code == 404

    confirm_response = client.post(
        f"/imports/{import_id}/confirm",
        headers=auth_headers(other_token),
    )
    assert confirm_response.status_code == 404


def test_discard_import_marks_status_and_blocks_confirm(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client)
    mock_parser(monkeypatch)

    create_response = client.post(
        "/imports",
        json={"raw_text": "Whatnot receipt text"},
        headers=auth_headers(token),
    )
    import_id = create_response.json()["id"]

    discard_response = client.post(f"/imports/{import_id}/discard", headers=auth_headers(token))
    assert discard_response.status_code == 200
    assert discard_response.json()["status"] == "discarded"

    confirm_response = client.post(f"/imports/{import_id}/confirm", headers=auth_headers(token))
    assert confirm_response.status_code == 409
