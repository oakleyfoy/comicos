from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CoverImage, CoverImageDerivative, DraftImport, InventoryCopy
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


def create_manual_import_with_two_copies(client: TestClient, token: str) -> int:
    response = client.post(
        "/imports/manual",
        headers=auth_headers(token),
        json={
            "raw_text": "manual draft",
            "source_type": "manual_draft",
            "retailer": "Shop",
            "order_date": "2026-03-03",
            "confidence_score": 1,
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "X-Men",
                    "issue_number": "1",
                    "cover_name": None,
                    "quantity": 2,
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
    assert response.status_code == 201
    return response.json()["id"]


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


def test_processed_cover_with_derivatives_becomes_ready(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "cover-ready@example.com")
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    result = run_cover_image_process_job(cover_id, inv.user_id)
    assert result["processing_status"] == "processed"

    session.expire_all()
    cover = session.get(CoverImage, cover_id)
    assert cover is not None
    assert cover.matching_status == "ready"
    assert cover.matching_notes is None
    assert cover.ready_for_matching_at is not None

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    payload = next(row for row in detail.json()["cover_images"] if row["id"] == cover_id)
    assert payload["matching_status"] == "ready"
    assert payload["ready_for_matching_at"] is not None
    assert {row["derivative_type"] for row in payload["derivatives"]} == {"thumb", "medium"}


def test_readiness_missing_derivative_becomes_needs_review(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-missing-derivative@example.com")
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    run_cover_image_process_job(cover_id, inv.user_id)

    medium_derivative = session.exec(
        select(CoverImageDerivative).where(
            CoverImageDerivative.cover_image_id == cover_id,
            CoverImageDerivative.derivative_type == "medium",
        )
    ).first()
    assert medium_derivative is not None
    session.delete(medium_derivative)
    session.commit()

    response = client.post(
        f"/cover-images/{cover_id}/evaluate-matching-readiness",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matching_status"] == "needs_review"
    assert "Missing required medium derivative." in body["matching_notes"]
    assert body["ready_for_matching_at"] is None


def test_failed_processing_does_not_become_ready(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "cover-readiness-failed@example.com")
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())

    cover = session.get(CoverImage, cover_id)
    assert cover is not None
    storage_path = get_settings().cover_images_storage_root / cover.storage_path
    storage_path.unlink()

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    with pytest.raises(ValueError, match="missing on disk"):
        run_cover_image_process_job(cover_id, inv.user_id)

    session.expire_all()
    failed = session.get(CoverImage, cover_id)
    assert failed is not None
    assert failed.processing_status == "failed"
    assert failed.matching_status == "failed"
    assert failed.ready_for_matching_at is None
    assert failed.matching_notes is not None
    assert "missing on disk" in failed.matching_notes


def test_readiness_evaluation_does_not_mutate_linkage_or_primary(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-readiness-immutable@example.com")
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())

    set_primary = client.post(
        f"/inventory/{inventory_copy_id}/cover-images/{cover_id}/primary",
        headers=auth_headers(token),
    )
    assert set_primary.status_code == 200

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    run_cover_image_process_job(cover_id, inv.user_id)

    before_inv = session.get(InventoryCopy, inventory_copy_id)
    before_cover = session.get(CoverImage, cover_id)
    assert before_inv is not None
    assert before_cover is not None

    evaluate = client.post(
        f"/cover-images/{cover_id}/evaluate-matching-readiness",
        headers=auth_headers(token),
    )
    assert evaluate.status_code == 200

    session.expire_all()
    after_inv = session.get(InventoryCopy, inventory_copy_id)
    after_cover = session.get(CoverImage, cover_id)
    assert after_inv is not None
    assert after_cover is not None
    assert after_inv.primary_cover_image_id == before_inv.primary_cover_image_id
    assert after_cover.inventory_copy_id == before_cover.inventory_copy_id
    assert after_cover.draft_import_id == before_cover.draft_import_id
    assert after_cover.canonical_series_id == before_cover.canonical_series_id


def test_matching_readiness_endpoints_follow_cover_permissions(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-ready-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "cover-ready-owner@example.com")
    foreign_token = register_and_login(client, "cover-ready-foreign@example.com")
    ops_token = register_and_login(client, "cover-ready-ops@example.com")

    inventory_copy_id = _inventory_copy_id_for_new_order(client, owner_token)
    cover_id = _upload_inventory_cover(client, owner_token, inventory_copy_id, make_png_bytes())
    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    run_cover_image_process_job(cover_id, inv.user_id)

    owner_response = client.post(
        f"/cover-images/{cover_id}/evaluate-matching-readiness",
        headers=auth_headers(owner_token),
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["matching_status"] == "ready"

    foreign_response = client.post(
        f"/cover-images/{cover_id}/evaluate-matching-readiness",
        headers=auth_headers(foreign_token),
    )
    assert foreign_response.status_code == 404

    ops_response = client.post(
        f"/ops/cover-images/{cover_id}/evaluate-matching-readiness",
        headers=auth_headers(ops_token),
    )
    assert ops_response.status_code == 200
    assert ops_response.json()["matching_status"] == "ready"

    non_admin_ops = client.post(
        f"/ops/cover-images/{cover_id}/evaluate-matching-readiness",
        headers=auth_headers(foreign_token),
    )
    assert non_admin_ops.status_code == 403
    get_settings.cache_clear()


def test_cover_pipeline_closeout_checklist(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-p30-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "cover-p30-owner@example.com")
    ops_token = register_and_login(client, "cover-p30-ops@example.com")
    import_id = create_manual_import_with_two_copies(client, owner_token)
    png = make_png_bytes()

    upload = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers(owner_token),
        files={"file": ("import-scan.png", png, "image/png")},
        data={"source_type": "import_image"},
    )
    assert upload.status_code == 200
    cover_id = upload.json()["id"]

    process_enqueue = client.post(
        f"/cover-images/{cover_id}/process",
        headers=auth_headers(owner_token),
    )
    assert process_enqueue.status_code == 202

    import_before_confirm = client.get(f"/imports/{import_id}", headers=auth_headers(owner_token))
    assert import_before_confirm.status_code == 200
    assert import_before_confirm.json()["cover_images"][0]["matching_status"] == "not_ready"

    draft_import = session.get(DraftImport, import_id)
    assert draft_import is not None
    owner_user_id = draft_import.user_id
    process_result = run_cover_image_process_job(cover_id, owner_user_id)
    assert process_result["processing_status"] == "processed"

    refreshed_import = client.get(f"/imports/{import_id}", headers=auth_headers(owner_token))
    assert refreshed_import.status_code == 200
    import_cover = refreshed_import.json()["cover_images"][0]
    assert import_cover["thumbnail_fetch_path"] == f"/files/cover-images/{cover_id}/derivatives/thumb"
    assert import_cover["medium_fetch_path"] == f"/files/cover-images/{cover_id}/derivatives/medium"
    assert import_cover["matching_status"] == "ready"

    confirm = client.post(f"/imports/{import_id}/confirm", headers=auth_headers(owner_token))
    assert confirm.status_code == 200
    order_id = confirm.json()["order_id"]
    order_detail = client.get(f"/orders/{order_id}", headers=auth_headers(owner_token))
    inventory_copy_ids = [cid for item in order_detail.json()["items"] for cid in item["inventory_copy_ids"]]
    assert len(inventory_copy_ids) == 2
    target_inv_id, duplicate_inv_id = inventory_copy_ids

    assign = client.post(
        f"/inventory/{target_inv_id}/cover-images/assign-existing",
        headers=auth_headers(owner_token),
        json={"cover_image_id": cover_id, "set_primary": True},
    )
    assert assign.status_code == 200
    assert assign.json()["is_primary"] is True

    duplicate_cover_id = _upload_inventory_cover(client, owner_token, duplicate_inv_id, png)
    duplicate_inv = session.get(InventoryCopy, duplicate_inv_id)
    assert duplicate_inv is not None
    run_cover_image_process_job(duplicate_cover_id, duplicate_inv.user_id)

    evaluate = client.post(
        f"/cover-images/{cover_id}/evaluate-matching-readiness",
        headers=auth_headers(owner_token),
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["matching_status"] == "ready"

    inventory_detail = client.get(f"/inventory/{target_inv_id}", headers=auth_headers(owner_token))
    assigned_cover = next(row for row in inventory_detail.json()["cover_images"] if row["id"] == cover_id)
    assert assigned_cover["is_primary"] is True
    assert assigned_cover["matching_status"] == "ready"

    recent_ready = client.get(
        "/ops/cover-images/recent",
        params={"matching_status": "ready"},
        headers=auth_headers(ops_token),
    )
    assert recent_ready.status_code == 200
    recent_ids = {row["id"] for row in recent_ready.json()}
    assert cover_id in recent_ids
    assert duplicate_cover_id in recent_ids

    duplicates = client.get("/ops/cover-images/duplicates", headers=auth_headers(ops_token))
    assert duplicates.status_code == 200
    matched_group = next(
        group for group in duplicates.json() if {row["id"] for row in group["covers"]} >= {cover_id, duplicate_cover_id}
    )
    member_statuses = {row["id"]: row["matching_status"] for row in matched_group["covers"]}
    assert member_statuses[cover_id] == "ready"
    assert member_statuses[duplicate_cover_id] == "ready"
    get_settings.cache_clear()
