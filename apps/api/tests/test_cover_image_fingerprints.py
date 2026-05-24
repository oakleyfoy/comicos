from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CoverImage, CoverImageDerivative, CoverImageFingerprint, InventoryCopy, MetadataAudit
from app.services.cover_images import (
    FINGERPRINT_EXTRACTION_VERSION,
    generate_average_hash,
    generate_difference_hash,
    generate_perceptual_hash,
    resolve_filesystem_path,
    sha256_raw_bytes,
)
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
    *,
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


def _bootstrap_processed_cover(
    client: TestClient,
    session: Session,
    *,
    suffix: str,
    image_bytes: bytes | None = None,
) -> tuple[str, int, int]:
    token = register_and_login(client, f"fingerprint-{suffix}@example.com")
    inv_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inv_id, image_bytes or make_png_bytes())
    inv_row = session.get(InventoryCopy, inv_id)
    assert inv_row is not None
    run_cover_image_process_job(cover_id, inv_row.user_id)
    return token, inv_id, cover_id


def test_cover_fingerprint_generation_helpers_are_deterministic() -> None:
    image_bytes = make_png_bytes()
    first = {
        "ahash": generate_average_hash(image_bytes),
        "dhash": generate_difference_hash(image_bytes),
        "phash": generate_perceptual_hash(image_bytes),
    }
    second = {
        "ahash": generate_average_hash(image_bytes),
        "dhash": generate_difference_hash(image_bytes),
        "phash": generate_perceptual_hash(image_bytes),
    }
    assert first == second
    assert all(len(value) == 16 for value in first.values())


def test_identical_image_produces_identical_fingerprints(
    client: TestClient,
    session: Session,
) -> None:
    image_bytes = make_png_bytes(color=(80, 40, 120))
    token_a, _inv_a, cover_a = _bootstrap_processed_cover(
        client,
        session,
        suffix="same-a",
        image_bytes=image_bytes,
    )
    token_b, _inv_b, cover_b = _bootstrap_processed_cover(
        client,
        session,
        suffix="same-b",
        image_bytes=image_bytes,
    )
    payload_a = client.post(
        f"/cover-images/{cover_a}/generate-fingerprints",
        headers=auth_headers(token_a),
    ).json()
    payload_b = client.post(
        f"/cover-images/{cover_b}/generate-fingerprints",
        headers=auth_headers(token_b),
    ).json()
    by_type_a = {row["fingerprint_type"]: row["fingerprint_value"] for row in payload_a["fingerprints"]}
    by_type_b = {row["fingerprint_type"]: row["fingerprint_value"] for row in payload_b["fingerprints"]}
    assert by_type_a == by_type_b


def test_cover_fingerprint_generation_persists_multiple_types_and_is_idempotent_without_metadata_mutation(
    client: TestClient,
    session: Session,
) -> None:
    token, inv_id, cover_id = _bootstrap_processed_cover(client, session, suffix="persist")
    hdrs = auth_headers(token)
    before_inv = session.get(InventoryCopy, inv_id)
    before_cover = session.get(CoverImage, cover_id)
    assert before_inv is not None and before_cover is not None

    first = client.post(f"/cover-images/{cover_id}/generate-fingerprints", headers=hdrs)
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["fingerprint_count"] == 3
    assert {row["fingerprint_type"] for row in first_payload["fingerprints"]} == {"ahash", "dhash", "phash"}

    second = client.post(f"/cover-images/{cover_id}/generate-fingerprints", headers=hdrs)
    assert second.status_code == 200
    second_payload = second.json()
    assert {row["id"] for row in second_payload["fingerprints"]} == {
        row["id"] for row in first_payload["fingerprints"]
    }

    session.expire_all()
    rows = session.exec(
        select(CoverImageFingerprint)
        .where(CoverImageFingerprint.cover_image_id == cover_id)
        .order_by(CoverImageFingerprint.fingerprint_type.asc())
    ).all()
    assert len(rows) == 3
    assert all(row.derivative_type in {"original", "medium"} for row in rows)
    assert all(row.extraction_version == FINGERPRINT_EXTRACTION_VERSION for row in rows)

    detail = client.get(f"/inventory/{inv_id}", headers=hdrs)
    assert detail.status_code == 200
    cover_payload = next(item for item in detail.json()["cover_images"] if item["id"] == cover_id)
    assert len(cover_payload["fingerprints"]) == 3

    session.expire_all()
    inv_after = session.get(InventoryCopy, inv_id)
    cover_after = session.get(CoverImage, cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash

    audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "cover_fingerprint")).all()
    assert any(a.action == "cover_fingerprint_created" for a in audits)


def test_cover_fingerprint_generation_missing_image_fails_safely(
    client: TestClient,
    session: Session,
) -> None:
    token, _inv_id, cover_id = _bootstrap_processed_cover(client, session, suffix="missing")
    cover = session.get(CoverImage, cover_id)
    assert cover is not None
    cover.storage_path = "missing/original.png"
    session.add(cover)
    medium = session.exec(
        select(CoverImageDerivative).where(
            CoverImageDerivative.cover_image_id == cover_id,
            CoverImageDerivative.derivative_type == "medium",
        )
    ).first()
    if medium is not None:
        medium.storage_path = "missing/medium.webp"
        session.add(medium)
    session.commit()

    response = client.post(
        f"/cover-images/{cover_id}/generate-fingerprints",
        headers=auth_headers(token),
    )
    assert response.status_code == 409
    assert "missing" in response.json()["detail"].lower()


def test_cover_fingerprint_generation_malformed_image_fails_safely(
    client: TestClient,
    session: Session,
) -> None:
    token, _inv_id, cover_id = _bootstrap_processed_cover(client, session, suffix="malformed")
    settings = get_settings()
    cover = session.get(CoverImage, cover_id)
    assert cover is not None
    source_path = resolve_filesystem_path(settings, cover.storage_path)
    corrupted = b"not-a-real-image"
    source_path.write_bytes(corrupted)
    cover.sha256_hash = sha256_raw_bytes(corrupted)
    session.add(cover)
    medium = session.exec(
        select(CoverImageDerivative).where(
            CoverImageDerivative.cover_image_id == cover_id,
            CoverImageDerivative.derivative_type == "medium",
        )
    ).first()
    if medium is not None:
        medium.storage_path = "missing/medium.webp"
        session.add(medium)
    session.commit()

    response = client.post(
        f"/cover-images/{cover_id}/generate-fingerprints",
        headers=auth_headers(token),
    )
    assert response.status_code == 409
