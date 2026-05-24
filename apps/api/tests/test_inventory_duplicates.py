from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import DuplicateCandidateReview, InventoryCopy
from app.services.inventory import find_duplicate_inventory_candidates


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_order_payload(
    *,
    title: str = "Invincible",
    publisher: str = "Image",
    issue_number: str = "1",
    cover_name: str | None = "Cover A",
    printing: str | None = None,
    ratio: str | None = None,
    variant_type: str | None = None,
    quantity: int = 1,
) -> dict:
    return {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0.00,
        "tax_amount": 0.00,
        "items": [
            {
                "title": title,
                "publisher": publisher,
                "issue_number": issue_number,
                "cover_name": cover_name,
                "printing": printing,
                "ratio": ratio,
                "variant_type": variant_type,
                "cover_artist": None,
                "quantity": quantity,
                "raw_item_price": 7.65,
            }
        ],
    }


def test_find_duplicate_inventory_candidates_groups_matching_identity_keys(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "dupes@example.com")

    response = client.post(
        "/orders",
        json=build_order_payload(quantity=2),
        headers=auth_headers(token),
    )
    assert response.status_code == 201

    duplicates = find_duplicate_inventory_candidates(session)

    assert len(duplicates) == 1
    group = duplicates[0]
    assert group.review_status == "pending"
    assert group.metadata_identity_key == "Image|Invincible|1|Cover A"
    assert group.count == 2
    assert group.publisher == "Image"
    assert group.series_title == "Invincible"
    assert group.issue_number == "1"
    assert group.variant == "Cover A"
    assert len(group.copies) == 2


def test_duplicate_candidates_ignore_single_records_and_empty_keys(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "ignore@example.com")

    grouped_response = client.post(
        "/orders",
        json=build_order_payload(title="Saga", quantity=2),
        headers=auth_headers(token),
    )
    assert grouped_response.status_code == 201

    single_response = client.post(
        "/orders",
        json=build_order_payload(title="Monstress", quantity=1),
        headers=auth_headers(token),
    )
    assert single_response.status_code == 201

    monstress_copy = session.exec(
        select(InventoryCopy).where(
            InventoryCopy.metadata_identity_key == "Image|Monstress|1|Cover A"
        )
    ).one()
    monstress_copy.metadata_identity_key = None
    session.add(monstress_copy)
    session.commit()

    duplicates = find_duplicate_inventory_candidates(session)

    assert len(duplicates) == 1
    assert duplicates[0].review_status == "pending"
    assert duplicates[0].metadata_identity_key == "Image|Saga|1|Cover A"


def test_duplicate_candidates_do_not_group_different_variants(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "variants@example.com")

    cover_a = client.post(
        "/orders",
        json=build_order_payload(title="Geiger", cover_name="Cover A", quantity=1),
        headers=auth_headers(token),
    )
    assert cover_a.status_code == 201

    cover_b = client.post(
        "/orders",
        json=build_order_payload(title="Geiger", cover_name="Cover B", quantity=1),
        headers=auth_headers(token),
    )
    assert cover_b.status_code == 201

    duplicates = find_duplicate_inventory_candidates(session)

    assert duplicates == []


def test_ops_inventory_duplicates_endpoint_returns_expected_group_shape(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    response = client.post(
        "/orders",
        json=build_order_payload(title="Spawn", quantity=2),
        headers=auth_headers(token),
    )
    assert response.status_code == 201

    before_count = len(session.exec(select(InventoryCopy)).all())

    endpoint_response = client.get(
        "/ops/inventory/duplicates?publisher=Image&series_title=Spawn&min_count=2",
        headers=auth_headers(token),
    )

    assert endpoint_response.status_code == 200
    data = endpoint_response.json()
    assert len(data) == 1
    assert data[0]["metadata_identity_key"] == "Image|Spawn|1|Cover A"
    assert data[0]["count"] == 2
    assert data[0]["publisher"] == "Image"
    assert data[0]["series_title"] == "Spawn"
    assert data[0]["issue_number"] == "1"
    assert data[0]["variant"] == "Cover A"
    assert data[0]["review_status"] == "pending"
    assert data[0]["notes"] is None
    assert data[0]["reviewed_at"] is None
    assert data[0]["reviewed_by"] is None
    assert len(data[0]["copies"]) == 2
    assert {"inventory_copy_id", "order_id", "retailer", "order_date", "acquisition_cost"} <= set(
        data[0]["copies"][0]
    )

    after_count = len(session.exec(select(InventoryCopy)).all())
    assert after_count == before_count


def _fetch_inventory_id_key_pairs(session: Session) -> list[tuple[int, str | None]]:
    copies = session.exec(select(InventoryCopy).order_by(InventoryCopy.id)).all()
    return [(copy.id, copy.metadata_identity_key) for copy in copies if copy.id is not None]


def test_duplicate_review_decisions_persist_and_filter(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-review@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-review@example.com")

    create = client.post(
        "/orders",
        json=build_order_payload(title="Paper Girls", quantity=2),
        headers=auth_headers(token),
    )
    assert create.status_code == 201

    listing = client.get("/ops/inventory/duplicates", headers=auth_headers(token))
    assert listing.status_code == 200
    grouped = listing.json()
    assert len(grouped) == 1
    identity_key = grouped[0]["metadata_identity_key"]

    pending_only = client.get(
        "/ops/inventory/duplicates",
        headers=auth_headers(token),
        params={"review_status": "pending"},
    )
    assert len(pending_only.json()) == 1

    mark_confirmed = client.post(
        "/ops/inventory/duplicates/review",
        headers=auth_headers(token),
        json={
            "metadata_identity_key": identity_key,
            "review_status": "confirmed_duplicate",
            "notes": "Both pulls look identical.",
        },
    )
    assert mark_confirmed.status_code == 200
    body = mark_confirmed.json()
    assert body["review_status"] == "confirmed_duplicate"
    assert body["notes"] == "Both pulls look identical."
    assert body["reviewed_by_email"] == "ops-review@example.com"

    reviews = session.exec(select(DuplicateCandidateReview)).all()
    assert len(reviews) == 1

    pending_after = client.get(
        "/ops/inventory/duplicates",
        headers=auth_headers(token),
        params={"review_status": "pending"},
    )
    assert pending_after.json() == []

    confirmed_list = client.get(
        "/ops/inventory/duplicates",
        headers=auth_headers(token),
        params={"review_status": "confirmed_duplicate"},
    ).json()
    assert len(confirmed_list) == 1
    assert confirmed_list[0]["metadata_identity_key"] == identity_key

    mark_distinct = client.post(
        "/ops/inventory/duplicates/review",
        headers=auth_headers(token),
        json={
            "metadata_identity_key": identity_key,
            "review_status": "not_duplicate",
        },
    )
    assert mark_distinct.status_code == 200

    session.expire_all()
    refreshed_reviews = session.exec(select(DuplicateCandidateReview)).all()
    assert len(refreshed_reviews) == 1
    assert refreshed_reviews[0].review_status == "not_duplicate"
    assert refreshed_reviews[0].notes == "Both pulls look identical."

    confirmed_empty = client.get(
        "/ops/inventory/duplicates",
        headers=auth_headers(token),
        params={"review_status": "confirmed_duplicate"},
    ).json()
    assert confirmed_empty == []

    distinct_list = client.get(
        "/ops/inventory/duplicates",
        headers=auth_headers(token),
        params={"review_status": "not_duplicate"},
    ).json()
    assert len(distinct_list) == 1


def test_duplicate_review_notes_patch_creates_pending_row(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-notes@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-notes@example.com")

    assert (
        client.post(
            "/orders",
            json=build_order_payload(title="Copra", quantity=2),
            headers=auth_headers(token),
        ).status_code
        == 201
    )

    listing = client.get("/ops/inventory/duplicates", headers=auth_headers(token))
    identity_key = listing.json()[0]["metadata_identity_key"]

    marked = client.patch(
        "/ops/inventory/duplicates/review/notes",
        headers=auth_headers(token),
        json={
            "metadata_identity_key": identity_key,
            "notes": "Flagged for binder check.",
        },
    )
    assert marked.status_code == 200

    rows = session.exec(select(DuplicateCandidateReview)).all()
    assert len(rows) == 1
    assert rows[0].review_status == "pending"

    surfaced = client.get(
        "/ops/inventory/duplicates",
        headers=auth_headers(token),
        params={"review_status": "pending"},
    ).json()
    assert surfaced[0]["notes"] == "Flagged for binder check."


def test_duplicate_review_operations_leave_inventory_rows_unchanged(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-inv@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-inv@example.com")

    assert (
        client.post(
            "/orders",
            json=build_order_payload(title="Dept H", quantity=2),
            headers=auth_headers(token),
        ).status_code
        == 201
    )

    snapshot_before = _fetch_inventory_id_key_pairs(session)
    listing = client.get("/ops/inventory/duplicates", headers=auth_headers(token))
    identity_key = listing.json()[0]["metadata_identity_key"]

    decision = client.post(
        "/ops/inventory/duplicates/review",
        headers=auth_headers(token),
        json={
            "metadata_identity_key": identity_key,
            "review_status": "confirmed_duplicate",
            "notes": "Inventory must stay frozen.",
        },
    )
    assert decision.status_code == 200

    notes = client.patch(
        "/ops/inventory/duplicates/review/notes",
        headers=auth_headers(token),
        json={"metadata_identity_key": identity_key, "notes": "Still watching."},
    )
    assert notes.status_code == 200

    snapshot_after = _fetch_inventory_id_key_pairs(session)

    assert snapshot_before == snapshot_after


def test_orders_continue_after_duplicate_review_actions(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-flow@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-flow@example.com")

    assert (
        client.post(
            "/orders",
            json=build_order_payload(title="Fire Power", quantity=2),
            headers=auth_headers(token),
        ).status_code
        == 201
    )

    listing = client.get("/ops/inventory/duplicates", headers=auth_headers(token))
    identity_key = listing.json()[0]["metadata_identity_key"]

    decision = client.post(
        "/ops/inventory/duplicates/review",
        headers=auth_headers(token),
        json={"metadata_identity_key": identity_key, "review_status": "not_duplicate"},
    )
    assert decision.status_code == 200

    before_rows = session.exec(select(InventoryCopy)).all()

    follow_up = client.post(
        "/orders",
        json=build_order_payload(title="Rumble", publisher="Image", quantity=1),
        headers=auth_headers(token),
    )
    assert follow_up.status_code == 201

    after_rows = session.exec(select(InventoryCopy)).all()
    assert len(after_rows) == len(before_rows) + 1
