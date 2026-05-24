from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import CoverImageOcrRegion, InventoryCopy
from app.services.cover_images import OCR_REGION_EXTRACTION_VERSION, sha256_raw_bytes
from app.tasks.jobs import run_cover_image_process_job


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
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
    response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()


def make_png_bytes(
    size: tuple[int, int] = (1400, 900),
    color: tuple[int, int, int] = (30, 120, 200),
) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _inventory_copy_id_for_new_order(client: TestClient, token: str) -> int:
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token))
    return order_detail.json()["items"][0]["inventory_copy_ids"][0]


def _upload_inventory_cover(client: TestClient, token: str, inventory_copy_id: int, body: bytes) -> int:
    response = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", body, "image/png")},
        data={"source_type": "upload"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _make_cover_ready(client: TestClient, session: Session, token: str) -> tuple[int, int, int]:
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())
    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    result = run_cover_image_process_job(cover_id, inv.user_id)
    assert result["processing_status"] == "processed"
    return inventory_copy_id, cover_id, inv.user_id


def test_cover_region_extraction_generates_deterministic_regions(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-region-shape@example.com")
    inventory_copy_id, cover_id, _user_id = _make_cover_ready(client, session, token)

    response = client.get(f"/cover-images/{cover_id}/ocr-regions", headers=auth_headers(token))
    assert response.status_code == 200
    regions = response.json()
    assert [row["region_type"] for row in regions] == [
        "barcode_region",
        "full_cover",
        "issue_region",
        "lower_text_region",
        "publisher_region",
        "title_region",
    ]

    by_type = {row["region_type"]: row for row in regions}
    assert by_type["full_cover"]["image_width"] == 900
    assert by_type["full_cover"]["image_height"] == 579
    assert by_type["title_region"]["image_width"] == 900
    assert by_type["title_region"]["image_height"] == 145
    assert by_type["issue_region"]["image_width"] == 288
    assert by_type["issue_region"]["image_height"] == 127
    assert by_type["publisher_region"]["image_width"] == 315
    assert by_type["publisher_region"]["image_height"] == 104
    assert by_type["barcode_region"]["image_width"] == 252
    assert by_type["barcode_region"]["image_height"] == 127
    assert by_type["lower_text_region"]["image_width"] == 900
    assert by_type["lower_text_region"]["image_height"] == 116
    assert all(row["extraction_version"] == OCR_REGION_EXTRACTION_VERSION for row in regions)

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    cover = next(c for c in detail.json()["cover_images"] if c["id"] == cover_id)
    assert len(cover["ocr_regions"]) == 6


def test_cover_region_files_and_hashes_persist(
    client: TestClient,
    session: Session,
    tmp_path,
) -> None:
    del tmp_path
    token = register_and_login(client, "cover-region-hash@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, token)

    regions = session.exec(
        select(CoverImageOcrRegion)
        .where(CoverImageOcrRegion.cover_image_id == cover_id)
        .order_by(CoverImageOcrRegion.region_type.asc())
    ).all()
    assert len(regions) == 6
    for region in regions:
        region_file = client.get(region.fetch_path if hasattr(region, "fetch_path") else f"/files/cover-images/{cover_id}/ocr-regions/{region.region_type}", headers=auth_headers(token))
        assert region_file.status_code == 200
        assert sha256_raw_bytes(region_file.content) == region.sha256_hash
        assert region.file_size == len(region_file.content)


def test_cover_region_endpoint_enforces_owner_permissions(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-region-ops@example.com")
    owner_token = register_and_login(client, "cover-region-owner@example.com")
    foreign_token = register_and_login(client, "cover-region-foreign@example.com")
    ops_token = register_and_login(client, "cover-region-ops@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, owner_token)

    owner_response = client.get(f"/cover-images/{cover_id}/ocr-regions", headers=auth_headers(owner_token))
    assert owner_response.status_code == 200

    foreign_response = client.get(f"/cover-images/{cover_id}/ocr-regions", headers=auth_headers(foreign_token))
    assert foreign_response.status_code == 404

    region_file = client.get(
        f"/files/cover-images/{cover_id}/ocr-regions/title_region",
        headers=auth_headers(ops_token),
    )
    assert region_file.status_code == 200


def test_cover_region_extraction_is_idempotent(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-region-idempotent@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, token)

    first = client.post(f"/cover-images/{cover_id}/extract-ocr-regions", headers=auth_headers(token))
    second = client.post(f"/cover-images/{cover_id}/extract-ocr-regions", headers=auth_headers(token))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["region_count"] == 6
    assert second.json()["region_count"] == 6

    rows = session.exec(
        select(CoverImageOcrRegion)
        .where(CoverImageOcrRegion.cover_image_id == cover_id)
        .order_by(CoverImageOcrRegion.region_type.asc())
    ).all()
    assert len(rows) == 6
    assert len({row.region_type for row in rows}) == 6


def test_cover_region_extraction_does_not_mutate_cover_linkage(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-region-immutable@example.com")
    inventory_copy_id, cover_id, _ = _make_cover_ready(client, session, token)

    before_inv = session.get(InventoryCopy, inventory_copy_id)
    assert before_inv is not None

    response = client.post(f"/cover-images/{cover_id}/extract-ocr-regions", headers=auth_headers(token))
    assert response.status_code == 200

    session.expire_all()
    after_inv = session.get(InventoryCopy, inventory_copy_id)
    assert after_inv is not None
    assert after_inv.primary_cover_image_id == before_inv.primary_cover_image_id
