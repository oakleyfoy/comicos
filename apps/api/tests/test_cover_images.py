from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CoverImage, DraftImport, InventoryCopy
from app.services.cover_images import (
    COVER_CARRY_MULTI_COPY_NOTICE,
    deterministic_relative_storage_path,
    extract_image_dimensions_and_mime,
    list_duplicate_cover_image_groups_for_ops,
    sha256_raw_bytes,
)


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


def auth_headers_(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_order_basic(client: TestClient, token: str) -> dict:
    payload = {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
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
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    }
    response = client.post("/orders", json=payload, headers=auth_headers_(token))
    assert response.status_code == 201
    return response.json()


def make_png_bytes() -> bytes:
    image = Image.new("RGB", (11, 13), color=(30, 120, 200))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_cover_sha256_is_deterministic_for_raw_bytes():
    png = make_png_bytes()
    assert sha256_raw_bytes(png) == sha256_raw_bytes(png)
    alt = png + b"\xff"
    assert sha256_raw_bytes(png) != sha256_raw_bytes(alt)


def test_cover_image_dimensions_and_mime_via_pillow():
    png = make_png_bytes()
    w, h, mime = extract_image_dimensions_and_mime(png, "application/octet-stream")
    assert w == 11 and h == 13
    assert mime == "image/png"


def test_deterministic_storage_path_derived_from_sha_and_mime():
    mime = "image/png"
    sha = "a" * 64
    path = deterministic_relative_storage_path(mime, sha)
    assert path == f"{sha[:2]}/{sha}.png"


def test_duplicate_sha256_hashes_allowed_multiple_rows(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "dup-cover@example.com")
    oid = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(token))
    inventory_copy_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png = make_png_bytes()
    files = {"file": ("test.png", png, "image/png")}
    payload = {"source_type": "upload"}
    r1 = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers_(token),
        files=files,
        data=payload,
    )
    assert r1.status_code == 200
    files2 = {"file": ("other.png", png, "image/png")}
    r2 = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers_(token),
        files=files2,
        data=payload,
    )
    assert r2.status_code == 200
    assert r1.json()["sha256_hash"] == r2.json()["sha256_hash"]
    assert r1.json()["id"] != r2.json()["id"]
    covers = session.exec(
        select(CoverImage).where(CoverImage.inventory_copy_id == inventory_copy_id)
    ).all()
    assert len(covers) == 2


def test_inventory_detail_includes_cover_metadata(client: TestClient) -> None:
    token = register_and_login(client, "detail-cover@example.com")
    oid = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(token))
    inventory_copy_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png = make_png_bytes()
    files = {"file": ("c.png", png, "image/png")}
    up = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers_(token),
        files=files,
        data={"source_type": "upload"},
    )
    assert up.status_code == 200
    cid = up.json()["id"]

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers_(token))
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["cover_images"]) == 1
    cover = body["cover_images"][0]
    assert cover["id"] == cid
    assert cover["mime_type"] == "image/png"
    assert cover["sha256_hash"] == sha256_raw_bytes(png)
    assert cover["fetch_path"] == f"/files/cover-images/{cid}"
    assert cover["inventory_copy_id"] == inventory_copy_id
    assert cover["is_primary"] is False


def test_import_confirm_flow_unaffected_after_cover_introduction(client: TestClient) -> None:
    token = register_and_login(client, "confirm-after-cover@example.com")
    create_response = client.post(
        "/imports/manual",
        headers=auth_headers_(token),
        json={
            "raw_text": "Midtown Comics",
            "source_type": "manual_draft",
            "retailer": "Midtown Comics",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "1",
                    "cover_name": "Cover B",
                    "quantity": 1,
                    "raw_item_price": 4.99,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
                {
                    "publisher": "Image",
                    "title": "Saga",
                    "issue_number": "10",
                    "cover_name": None,
                    "quantity": 2,
                    "raw_item_price": 5.03,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]

    confirm = client.post(f"/imports/{import_id}/confirm", headers=auth_headers_(token))
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["status"] == "confirmed"
    assert payload["total_copies_created"] == 3
    assert payload.get("notices", []) == []


def test_ops_recent_cover_images_denied_for_non_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-cover-deny@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "regular-cover-ops@example.com")

    response = client.get("/ops/cover-images/recent", headers=auth_headers_(token))

    assert response.status_code == 403


def test_ops_recent_cover_images_metadata_filters_and_ops_file_access(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-cover-ok@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "owner-cover-ops@example.com")
    oid = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(owner_token))
    inventory_copy_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png_inv = make_png_bytes()
    inv_up = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers_(owner_token),
        files={"file": ("inventory-cover.png", png_inv, "image/png")},
        data={"source_type": "upload"},
    )
    assert inv_up.status_code == 200
    inv_cover_id = inv_up.json()["id"]

    create_resp = client.post(
        "/imports/manual",
        headers=auth_headers_(owner_token),
        json={
            "raw_text": "Draft for cover ops",
            "source_type": "manual_draft",
            "retailer": "Midtown Comics",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 4.99,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                }
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_resp.status_code == 201
    import_id = create_resp.json()["id"]

    imp_up = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(owner_token),
        files={"file": ("draft-scan.png", make_png_bytes(), "image/png")},
        data={"source_type": "import_image"},
    )
    assert imp_up.status_code == 200
    imp_cover_id = imp_up.json()["id"]

    ops_token = register_and_login(client, "ops-cover-ok@example.com")

    recent = client.get("/ops/cover-images/recent", headers=auth_headers_(ops_token))
    assert recent.status_code == 200
    rows = recent.json()
    assert len(rows) >= 2
    by_id = {r["id"]: r for r in rows}
    assert inv_cover_id in by_id and imp_cover_id in by_id

    inv_row = by_id[inv_cover_id]
    assert inv_row["original_filename"] == "inventory-cover.png"
    assert inv_row["inventory_copy_id"] == inventory_copy_id
    assert inv_row["draft_import_id"] is None
    assert inv_row["source_type"] == "upload"
    assert inv_row["mime_type"] == "image/png"
    assert inv_row["fetch_path"] == f"/files/cover-images/{inv_cover_id}"
    assert "canonical_series_id" in inv_row
    assert inv_row["is_primary"] is False

    imp_row = by_id[imp_cover_id]
    assert imp_row["original_filename"] == "draft-scan.png"
    assert imp_row["draft_import_id"] == import_id
    assert imp_row["inventory_copy_id"] is None
    assert imp_row["source_type"] == "import_image"

    inv_only = client.get(
        "/ops/cover-images/recent",
        params={"linkage": "inventory"},
        headers=auth_headers_(ops_token),
    ).json()
    assert all(r["inventory_copy_id"] is not None for r in inv_only)

    imp_only = client.get(
        "/ops/cover-images/recent",
        params={"linkage": "import"},
        headers=auth_headers_(ops_token),
    ).json()
    assert all(r["draft_import_id"] is not None for r in imp_only)

    upload_only = client.get(
        "/ops/cover-images/recent",
        params={"source_type": "upload"},
        headers=auth_headers_(ops_token),
    ).json()
    assert all(r["source_type"] == "upload" for r in upload_only)

    file_resp = client.get(inv_row["fetch_path"], headers=auth_headers_(ops_token))
    assert file_resp.status_code == 200
    assert file_resp.content == png_inv


def test_inventory_primary_cover_exclusive_sorted_and_switchable(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "primary-inv@example.com")
    oid = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(token))
    inventory_copy_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png = make_png_bytes()
    r1 = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("a.png", png, "image/png")},
        data={"source_type": "upload"},
    )
    r2 = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("b.png", png, "image/png")},
        data={"source_type": "upload"},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    id_a, id_b = r1.json()["id"], r2.json()["id"]
    assert id_a != id_b
    assert r1.json()["is_primary"] is False
    assert r2.json()["is_primary"] is False

    detail0 = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers_(token)).json()
    assert all(c["is_primary"] is False for c in detail0["cover_images"])

    set_b = client.post(
        f"/inventory/{inventory_copy_id}/cover-images/{id_b}/primary",
        headers=auth_headers_(token),
    )
    assert set_b.status_code == 200
    assert set_b.json()["is_primary"] is True

    session.expire_all()
    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    assert inv.primary_cover_image_id == id_b

    detail1 = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers_(token)).json()
    covers1 = detail1["cover_images"]
    assert covers1[0]["id"] == id_b
    assert covers1[0]["is_primary"] is True
    assert sum(1 for c in covers1 if c["is_primary"]) == 1

    set_a = client.post(
        f"/inventory/{inventory_copy_id}/cover-images/{id_a}/primary",
        headers=auth_headers_(token),
    )
    assert set_a.status_code == 200

    session.expire_all()
    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    assert inv.primary_cover_image_id == id_a

    detail2 = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers_(token)).json()
    covers2 = detail2["cover_images"]
    assert covers2[0]["id"] == id_a
    assert sum(1 for c in covers2 if c["is_primary"]) == 1
    b_row = next(c for c in covers2 if c["id"] == id_b)
    assert b_row["is_primary"] is False


def test_draft_import_primary_cover_in_get_import_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "primary-draft@example.com")
    create_resp = client.post(
        "/imports/manual",
        headers=auth_headers_(token),
        json={
            "raw_text": "Draft primary",
            "source_type": "manual_draft",
            "retailer": "Shop",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Spider",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 3.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                }
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_resp.status_code == 201
    import_id = create_resp.json()["id"]
    png = make_png_bytes()

    u1 = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("x.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    u2 = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("y.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    assert u1.status_code == 200 and u2.status_code == 200
    id_x, id_y = u1.json()["id"], u2.json()["id"]

    client.post(
        f"/imports/{import_id}/cover-images/{id_y}/primary",
        headers=auth_headers_(token),
    )

    session.expire_all()
    draft = session.get(DraftImport, import_id)
    assert draft is not None
    assert draft.primary_cover_image_id == id_y

    imported = client.get(f"/imports/{import_id}", headers=auth_headers_(token)).json()
    imgs = imported["cover_images"]
    assert imgs[0]["id"] == id_y
    assert imgs[0]["is_primary"] is True
    assert sum(1 for c in imgs if c["is_primary"]) == 1


def test_set_inventory_primary_rejects_foreign_cover_id(client: TestClient) -> None:
    token = register_and_login(client, "foreign-cover@example.com")
    oid1 = create_order_basic(client, token)
    oid2 = create_order_basic(client, token)
    od1 = client.get(f"/orders/{oid1['order_id']}", headers=auth_headers_(token)).json()
    od2 = client.get(f"/orders/{oid2['order_id']}", headers=auth_headers_(token)).json()
    inv1 = od1["items"][0]["inventory_copy_ids"][0]
    inv2 = od2["items"][0]["inventory_copy_ids"][0]
    png = make_png_bytes()
    up = client.post(
        f"/inventory/{inv1}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("only.png", png, "image/png")},
        data={"source_type": "upload"},
    )
    assert up.status_code == 200
    only_id = up.json()["id"]
    bad = client.post(
        f"/inventory/{inv2}/cover-images/{only_id}/primary",
        headers=auth_headers_(token),
    )
    assert bad.status_code == 404


def test_import_confirm_succeeds_when_primary_cover_selected(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "confirm-primary@example.com")
    create_response = client.post(
        "/imports/manual",
        headers=auth_headers_(token),
        json={
            "raw_text": "Confirm with primary cover",
            "source_type": "manual_draft",
            "retailer": "Midtown Comics",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 4.99,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]
    png = make_png_bytes()
    c1 = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("p1.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    c2 = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("p2.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    assert c1.status_code == 200 and c2.status_code == 200
    id_c2 = c2.json()["id"]
    client.post(
        f"/imports/{import_id}/cover-images/{id_c2}/primary",
        headers=auth_headers_(token),
    )

    confirm = client.post(f"/imports/{import_id}/confirm", headers=auth_headers_(token))
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["status"] == "confirmed"
    assert payload["total_copies_created"] == 1
    assert payload.get("notices", []) == []

    order_json = client.get(f"/orders/{payload['order_id']}", headers=auth_headers_(token)).json()
    inv_copy_id = order_json["items"][0]["inventory_copy_ids"][0]
    inv_detail = client.get(f"/inventory/{inv_copy_id}", headers=auth_headers_(token)).json()
    assert len(inv_detail["cover_images"]) == 2
    primaries = [c for c in inv_detail["cover_images"] if c["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == c2.json()["id"]

    after_import = client.get(f"/imports/{import_id}", headers=auth_headers_(token)).json()
    assert after_import["cover_images"] == []
    assert after_import["cover_image_count"] == 0

    session.expire_all()
    draft_row = session.get(DraftImport, import_id)
    assert draft_row is not None
    assert draft_row.primary_cover_image_id is None
    inv_row = session.get(InventoryCopy, inv_copy_id)
    assert inv_row is not None
    assert inv_row.primary_cover_image_id == id_c2

    assert len(session.exec(select(CoverImage)).all()) == 2


def test_manual_assign_import_cover_to_inventory_updates_linkage_primary_and_detail(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "manual-assign-cover@example.com")
    create_response = client.post(
        "/imports/manual",
        headers=auth_headers_(token),
        json={
            "raw_text": "multi assign",
            "source_type": "manual_draft",
            "retailer": "Shop",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Avengers",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 4.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "2",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 5.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]

    png = make_png_bytes()
    sha = sha256_raw_bytes(png)
    cover_up = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("scan.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    assert cover_up.status_code == 200
    cover_id = cover_up.json()["id"]

    covers_before_assign = session.exec(select(CoverImage)).all()
    row_before = session.get(CoverImage, cover_id)
    assert row_before is not None
    source_before = row_before.source_type
    storage_before = row_before.storage_path

    confirm = client.post(f"/imports/{import_id}/confirm", headers=auth_headers_(token))
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["total_copies_created"] == 2

    order_json = client.get(f"/orders/{payload['order_id']}", headers=auth_headers_(token)).json()
    inv_ids = [cid for row in order_json["items"] for cid in row["inventory_copy_ids"]]
    assert len(inv_ids) == 2
    target_inv = inv_ids[0]

    assign_resp = client.post(
        f"/inventory/{target_inv}/cover-images/assign-existing",
        headers=auth_headers_(token),
        json={"cover_image_id": cover_id, "set_primary": True},
    )
    assert assign_resp.status_code == 200
    assigned = assign_resp.json()
    assert assigned["inventory_copy_id"] == target_inv
    assert assigned["draft_import_id"] is None
    assert assigned["sha256_hash"] == sha
    assert assigned["source_type"] == source_before
    assert assigned["is_primary"] is True

    covers_after_assign = session.exec(select(CoverImage)).all()
    assert len(covers_after_assign) == len(covers_before_assign)

    session.expire_all()
    row_after = session.get(CoverImage, cover_id)
    assert row_after is not None
    assert row_after.inventory_copy_id == target_inv
    assert row_after.draft_import_id is None
    assert row_after.sha256_hash == sha
    assert row_after.storage_path == storage_before
    assert row_after.source_type == source_before

    inv_detail = client.get(f"/inventory/{target_inv}", headers=auth_headers_(token)).json()
    ids_on_inv = [c["id"] for c in inv_detail["cover_images"]]
    assert cover_id in ids_on_inv
    primaries = [c for c in inv_detail["cover_images"] if c["is_primary"]]
    assert len(primaries) == 1 and primaries[0]["id"] == cover_id

    imp = client.get(f"/imports/{import_id}", headers=auth_headers_(token)).json()
    cover_ids_on_import = {c["id"] for c in imp["cover_images"]}
    assert cover_id not in cover_ids_on_import


def test_manual_assign_cover_rejects_foreign_owner_cover(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "assign-ops-exclusive@example.com")
    get_settings.cache_clear()

    token_a = register_and_login(client, "assign-owner-a@example.com")
    token_b = register_and_login(client, "assign-owner-b@example.com")

    create_b = client.post(
        "/imports/manual",
        headers=auth_headers_(token_b),
        json={
            "raw_text": "b draft",
            "source_type": "manual_draft",
            "retailer": "Shop",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Spider",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 3.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                }
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_b.status_code == 201
    import_b = create_b.json()["id"]
    up_b = client.post(
        f"/imports/{import_b}/cover-images",
        headers=auth_headers_(token_b),
        files={"file": ("b.png", make_png_bytes(), "image/png")},
        data={"source_type": "import_image"},
    )
    assert up_b.status_code == 200
    cover_b_id = up_b.json()["id"]

    oid_a = create_order_basic(client, token_a)
    order_a = client.get(f"/orders/{oid_a['order_id']}", headers=auth_headers_(token_a)).json()
    inv_a = order_a["items"][0]["inventory_copy_ids"][0]

    bad = client.post(
        f"/inventory/{inv_a}/cover-images/assign-existing",
        headers=auth_headers_(token_a),
        json={"cover_image_id": cover_b_id, "set_primary": False},
    )
    assert bad.status_code == 403

    session.expire_all()
    row_b = session.get(CoverImage, cover_b_id)
    assert row_b is not None
    assert row_b.draft_import_id == import_b

    get_settings.cache_clear()


def test_return_cover_from_inventory_to_draft_import_restores_import_listing(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "assign-return-draft@example.com")
    create_response = client.post(
        "/imports/manual",
        headers=auth_headers_(token),
        json={
            "raw_text": "multi return",
            "source_type": "manual_draft",
            "retailer": "Shop",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Avengers",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 4.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "2",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 5.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]

    png = make_png_bytes()
    cover_up = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("scan.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    assert cover_up.status_code == 200
    cover_id = cover_up.json()["id"]

    confirm = client.post(f"/imports/{import_id}/confirm", headers=auth_headers_(token))
    assert confirm.status_code == 200
    order_json = client.get(f"/orders/{confirm.json()['order_id']}", headers=auth_headers_(token)).json()
    target_inv = order_json["items"][0]["inventory_copy_ids"][0]

    assign_resp = client.post(
        f"/inventory/{target_inv}/cover-images/assign-existing",
        headers=auth_headers_(token),
        json={"cover_image_id": cover_id, "set_primary": True},
    )
    assert assign_resp.status_code == 200

    ret = client.post(
        f"/cover-images/{cover_id}/return-to-draft-import",
        headers=auth_headers_(token),
        json={"draft_import_id": import_id, "set_primary": False},
    )
    assert ret.status_code == 200
    body = ret.json()
    assert body["draft_import_id"] == import_id
    assert body["inventory_copy_id"] is None

    inv_detail = client.get(f"/inventory/{target_inv}", headers=auth_headers_(token)).json()
    assert all(c["id"] != cover_id for c in inv_detail["cover_images"])

    session.expire_all()
    inv_row = session.get(InventoryCopy, target_inv)
    assert inv_row is not None
    assert inv_row.primary_cover_image_id is None

    imp = client.get(f"/imports/{import_id}", headers=auth_headers_(token)).json()
    ids = [c["id"] for c in imp["cover_images"]]
    assert cover_id in ids


def test_confirm_multiple_inventory_copies_keeps_import_covers_with_notice(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "carry-multi@example.com")
    create_response = client.post(
        "/imports/manual",
        headers=auth_headers_(token),
        json={
            "raw_text": "multi",
            "source_type": "manual_draft",
            "retailer": "Shop",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Avengers",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 4.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "2",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 5.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]
    png = make_png_bytes()
    cover_up = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(token),
        files={"file": ("scan.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    assert cover_up.status_code == 200
    cover_id = cover_up.json()["id"]
    covers_before = len(session.exec(select(CoverImage)).all())

    confirm = client.post(f"/imports/{import_id}/confirm", headers=auth_headers_(token))
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["total_copies_created"] == 2
    assert COVER_CARRY_MULTI_COPY_NOTICE in payload.get("notices", [])

    imp = client.get(f"/imports/{import_id}", headers=auth_headers_(token)).json()
    assert len(imp["cover_images"]) == 1
    assert imp["cover_images"][0]["id"] == cover_id

    order_json = client.get(f"/orders/{payload['order_id']}", headers=auth_headers_(token)).json()
    for row in order_json["items"]:
        for cid in row["inventory_copy_ids"]:
            inv = client.get(f"/inventory/{cid}", headers=auth_headers_(token)).json()
            assert inv["cover_images"] == []

    session.expire_all()
    row = session.get(CoverImage, cover_id)
    assert row is not None
    assert row.draft_import_id == import_id
    assert row.inventory_copy_id is None
    assert len(session.exec(select(CoverImage)).all()) == covers_before


def test_confirm_without_cover_scans_has_empty_notices(client: TestClient) -> None:
    token = register_and_login(client, "carry-none@example.com")
    create_response = client.post(
        "/imports/manual",
        headers=auth_headers_(token),
        json={
            "raw_text": "none",
            "source_type": "manual_draft",
            "retailer": "Midtown Comics",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 4.99,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                },
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]
    confirm = client.post(f"/imports/{import_id}/confirm", headers=auth_headers_(token))
    assert confirm.status_code == 200
    assert confirm.json().get("notices", []) == []


def test_ops_cover_image_duplicates_requires_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dup-gate@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "regular-dup-gate@example.com")
    response = client.get("/ops/cover-images/duplicates", headers=auth_headers_(token))
    assert response.status_code == 403
    get_settings.cache_clear()


def test_ops_cover_image_duplicates_groups_same_hash(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dup-view@example.com")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "owner-dup-view@example.com")
    ops_token = register_and_login(client, "ops-dup-view@example.com")

    oid = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(owner_token))
    inv_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png = make_png_bytes()
    r1 = client.post(
        f"/inventory/{inv_id}/cover-images",
        headers=auth_headers_(owner_token),
        files={"file": ("a.png", png, "image/png")},
        data={"source_type": "upload"},
    )
    r2 = client.post(
        f"/inventory/{inv_id}/cover-images",
        headers=auth_headers_(owner_token),
        files={"file": ("b.png", png, "image/png")},
        data={"source_type": "upload"},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    sha = r1.json()["sha256_hash"]
    assert r2.json()["sha256_hash"] == sha

    dup = client.get("/ops/cover-images/duplicates", headers=auth_headers_(ops_token))
    assert dup.status_code == 200
    groups = dup.json()
    match = [g for g in groups if g["sha256_hash"] == sha]
    assert len(match) == 1
    g0 = match[0]
    assert g0["count"] == 2
    assert len(g0["covers"]) == 2
    assert {c["id"] for c in g0["covers"]} == {r1.json()["id"], r2.json()["id"]}

    paths = sorted(c["fetch_path"] for c in g0["covers"])
    assert paths == sorted(
        [
            f"/files/cover-images/{r1.json()['id']}",
            f"/files/cover-images/{r2.json()['id']}",
        ]
    )
    get_settings.cache_clear()


def test_ops_cover_image_duplicates_excludes_single_hash_row(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dup-single@example.com")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "owner-dup-single@example.com")
    ops_token = register_and_login(client, "ops-dup-single@example.com")

    oid = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(owner_token))
    inv_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png = make_png_bytes()
    up = client.post(
        f"/inventory/{inv_id}/cover-images",
        headers=auth_headers_(owner_token),
        files={"file": ("only.png", png, "image/png")},
        data={"source_type": "upload"},
    )
    assert up.status_code == 200
    sha = up.json()["sha256_hash"]

    dup = client.get("/ops/cover-images/duplicates", headers=auth_headers_(ops_token))
    assert dup.status_code == 200
    assert all(g["sha256_hash"] != sha for g in dup.json())
    get_settings.cache_clear()


def test_duplicate_cover_visibility_ignores_empty_sha256_hashes(client: TestClient) -> None:
    from sqlmodel import Session

    from app.db.session import get_engine

    # Use the same engine as the TestClient app (the bare `session` fixture does not).
    with Session(get_engine()) as session:
        e1 = CoverImage(
            inventory_copy_id=None,
            draft_import_id=None,
            canonical_series_id=None,
            source_type="upload",
            original_filename=None,
            storage_path="aa/empty1.png",
            mime_type="image/png",
            image_width=1,
            image_height=1,
            file_size=1,
            sha256_hash="",
        )
        e2 = CoverImage(
            inventory_copy_id=None,
            draft_import_id=None,
            canonical_series_id=None,
            source_type="upload",
            original_filename=None,
            storage_path="aa/empty2.png",
            mime_type="image/png",
            image_width=1,
            image_height=1,
            file_size=1,
            sha256_hash="",
        )
        session.add(e1)
        session.add(e2)
        session.commit()

        groups = list_duplicate_cover_image_groups_for_ops(session)
        assert groups == []


def test_ops_cover_duplicates_different_hashes_not_combined(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-two-hash@example.com")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "owner-two-hash@example.com")
    ops_token = register_and_login(client, "ops-two-hash@example.com")

    oid = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(owner_token))
    inv_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png_a = make_png_bytes()
    png_b = png_a + b"\x00"

    ids_a = []
    for fname in ("a1.png", "a2.png"):
        resp = client.post(
            f"/inventory/{inv_id}/cover-images",
            headers=auth_headers_(owner_token),
            files={"file": (fname, png_a, "image/png")},
            data={"source_type": "upload"},
        )
        assert resp.status_code == 200
        ids_a.append(resp.json()["id"])
    sha_a = sha256_raw_bytes(png_a)

    ids_b = []
    for fname in ("b1.png", "b2.png"):
        resp = client.post(
            f"/inventory/{inv_id}/cover-images",
            headers=auth_headers_(owner_token),
            files={"file": (fname, png_b, "image/png")},
            data={"source_type": "upload"},
        )
        assert resp.status_code == 200
        ids_b.append(resp.json()["id"])
    sha_b = sha256_raw_bytes(png_b)
    assert sha_a != sha_b

    dup = client.get("/ops/cover-images/duplicates", headers=auth_headers_(ops_token))
    assert dup.status_code == 200
    groups_by_sha = {g["sha256_hash"]: g for g in dup.json()}
    assert set(groups_by_sha.keys()) >= {sha_a, sha_b}
    ga = groups_by_sha[sha_a]
    gb = groups_by_sha[sha_b]
    assert ga["count"] == 2 and {c["id"] for c in ga["covers"]} == set(ids_a)
    assert gb["count"] == 2 and {c["id"] for c in gb["covers"]} == set(ids_b)
    get_settings.cache_clear()


def test_ops_cover_duplicates_linkage_filter_splits_counts(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dup-link@example.com")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "owner-dup-link@example.com")
    ops_token = register_and_login(client, "ops-dup-link@example.com")

    oid = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(owner_token))
    inv_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    create_resp = client.post(
        "/imports/manual",
        headers=auth_headers_(owner_token),
        json={
            "raw_text": "draft dup",
            "source_type": "manual_draft",
            "retailer": "Shop",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "X",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 1,
                    "raw_item_price": 3.0,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                }
            ],
            "shipping_amount": "0",
            "tax_amount": "0",
            "warnings": [],
        },
    )
    import_id = create_resp.json()["id"]
    png = make_png_bytes()
    inv_up = client.post(
        f"/inventory/{inv_id}/cover-images",
        headers=auth_headers_(owner_token),
        files={"file": ("inv.png", png, "image/png")},
        data={"source_type": "upload"},
    )
    imp_up = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers_(owner_token),
        files={"file": ("imp.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    assert inv_up.status_code == 200 and imp_up.status_code == 200
    sha = inv_up.json()["sha256_hash"]
    assert imp_up.json()["sha256_hash"] == sha

    inv_only = client.get(
        "/ops/cover-images/duplicates",
        params={"linkage": "inventory"},
        headers=auth_headers_(ops_token),
    )
    assert inv_only.status_code == 200
    assert not any(g["sha256_hash"] == sha for g in inv_only.json())

    all_rows = client.get("/ops/cover-images/duplicates", headers=auth_headers_(ops_token))
    assert any(g["sha256_hash"] == sha for g in all_rows.json())
    get_settings.cache_clear()


def test_ops_cover_duplicates_source_type_filter(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-src-dup@example.com")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "owner-src-dup@example.com")
    ops_token = register_and_login(client, "ops-src-dup@example.com")

    oid = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(owner_token))
    inv_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]

    png = make_png_bytes()
    for fname in ("u1.png", "u2.png"):
        resp = client.post(
            f"/inventory/{inv_id}/cover-images",
            headers=auth_headers_(owner_token),
            files={"file": (fname, png, "image/png")},
            data={"source_type": "upload"},
        )
        assert resp.status_code == 200
    sha = sha256_raw_bytes(png)

    imp_only = client.get(
        "/ops/cover-images/duplicates",
        params={"source_type": "import_image"},
        headers=auth_headers_(ops_token),
    )
    assert imp_only.status_code == 200
    assert all(g["sha256_hash"] != sha for g in imp_only.json())

    uploads_only = client.get(
        "/ops/cover-images/duplicates",
        params={"source_type": "upload"},
        headers=auth_headers_(ops_token),
    )
    assert uploads_only.status_code == 200
    assert any(g["sha256_hash"] == sha for g in uploads_only.json())
    get_settings.cache_clear()


def test_ops_cover_duplicates_respects_min_count_param(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dup-min@example.com")
    get_settings.cache_clear()
    owner_token = register_and_login(client, "owner-dup-min@example.com")
    ops_token = register_and_login(client, "ops-dup-min@example.com")

    oid = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{oid['order_id']}", headers=auth_headers_(owner_token))
    inv_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]
    png = make_png_bytes()
    for name in ("a.png", "b.png"):
        r = client.post(
            f"/inventory/{inv_id}/cover-images",
            headers=auth_headers_(owner_token),
            files={"file": (name, png, "image/png")},
            data={"source_type": "upload"},
        )
        assert r.status_code == 200
    sha = sha256_raw_bytes(png)

    resp_high = client.get(
        "/ops/cover-images/duplicates",
        params={"min_count": 3},
        headers=auth_headers_(ops_token),
    )
    assert resp_high.status_code == 200
    assert not any(g["sha256_hash"] == sha for g in resp_high.json())

    resp_two = client.get(
        "/ops/cover-images/duplicates",
        params={"min_count": 2},
        headers=auth_headers_(ops_token),
    )
    assert resp_two.status_code == 200
    assert any(g["sha256_hash"] == sha for g in resp_two.json())
    get_settings.cache_clear()

