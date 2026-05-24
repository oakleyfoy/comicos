from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.core.config import get_settings
from app.models import CoverImage, InventoryCopy
from app.services.cover_images import generate_cover_image_derivative
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
    size: tuple[int, int] = (2000, 1000),
    color: tuple[int, int, int] = (30, 120, 200),
) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _cover_root() -> Path:
    return get_settings().cover_images_storage_root


def test_generate_cover_derivatives_dimensions_and_original_unchanged(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-deriv-dims@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    body = make_png_bytes()
    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("large.png", body, "image/png")},
        data={"source_type": "upload"},
    )
    assert upload.status_code == 200
    cover = upload.json()

    row = session.get(CoverImage, cover["id"])
    assert row is not None
    original_abs_path = _cover_root() / row.storage_path
    original_before = original_abs_path.read_bytes()

    thumb = generate_cover_image_derivative(
        session,
        settings=get_settings(),
        cover_image_id=cover["id"],
        derivative_type="thumb",
    )
    medium = generate_cover_image_derivative(
        session,
        settings=get_settings(),
        cover_image_id=cover["id"],
        derivative_type="medium",
    )

    assert max(thumb.image_width or 0, thumb.image_height or 0) <= 240
    assert max(medium.image_width or 0, medium.image_height or 0) <= 900
    assert original_abs_path.read_bytes() == original_before


def test_generate_cover_derivative_reuses_existing_row_and_file(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-deriv-reuse@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("large.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    cover_id = upload.json()["id"]

    first = generate_cover_image_derivative(
        session,
        settings=get_settings(),
        cover_image_id=cover_id,
        derivative_type="thumb",
    )
    second = generate_cover_image_derivative(
        session,
        settings=get_settings(),
        cover_image_id=cover_id,
        derivative_type="thumb",
    )
    assert first.id == second.id
    assert first.sha256_hash == second.sha256_hash
    assert first.generated_at == second.generated_at


def test_derivative_missing_file_regenerates_on_next_request(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-deriv-regen@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("large.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    cover_id = upload.json()["id"]

    first = generate_cover_image_derivative(
        session,
        settings=get_settings(),
        cover_image_id=cover_id,
        derivative_type="thumb",
    )
    derivative_abs_path = _cover_root() / f"derivatives/{cover_id}/thumb.{first.mime_type.split('/')[-1]}"
    derivative_abs_path.unlink()

    regenerated = generate_cover_image_derivative(
        session,
        settings=get_settings(),
        cover_image_id=cover_id,
        derivative_type="thumb",
    )
    assert regenerated.id == first.id
    assert derivative_abs_path.is_file()


def test_derivative_endpoint_honors_ownership_rules(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-deriv-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "cover-deriv-owner@example.com")
    foreign_token = register_and_login(client, "cover-deriv-foreign@example.com")
    ops_token = register_and_login(client, "cover-deriv-ops@example.com")
    created = create_order_basic(client, owner_token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(owner_token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(owner_token),
        files={"file": ("large.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    cover_id = upload.json()["id"]
    generate_cover_image_derivative(
        session,
        settings=get_settings(),
        cover_image_id=cover_id,
        derivative_type="thumb",
    )

    denied = client.get(
        f"/files/cover-images/{cover_id}/derivatives/thumb",
        headers=auth_headers(foreign_token),
    )
    assert denied.status_code == 403

    allowed = client.get(
        f"/files/cover-images/{cover_id}/derivatives/thumb",
        headers=auth_headers(ops_token),
    )
    assert allowed.status_code == 200
    get_settings.cache_clear()


def test_processing_job_generates_thumb_and_medium_derivatives(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-deriv-process@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("large.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    cover_id = upload.json()["id"]

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    result = run_cover_image_process_job(cover_id, inv.user_id)
    assert result["processing_status"] == "processed"

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token)).json()
    cover = next(row for row in detail["cover_images"] if row["id"] == cover_id)
    assert cover["thumbnail_fetch_path"] == f"/files/cover-images/{cover_id}/derivatives/thumb"
    assert cover["medium_fetch_path"] == f"/files/cover-images/{cover_id}/derivatives/medium"
    assert {d["derivative_type"] for d in cover["derivatives"]} == {"thumb", "medium"}


def test_cover_payload_falls_back_when_thumb_not_generated_yet(client: TestClient) -> None:
    token = register_and_login(client, "cover-deriv-fallback@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("large.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    assert upload.status_code == 200

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token)).json()
    cover = detail["cover_images"][0]
    assert cover["thumbnail_fetch_path"] is None
    assert cover["medium_fetch_path"] is None
    assert cover["fetch_path"] == f"/files/cover-images/{cover['id']}"
