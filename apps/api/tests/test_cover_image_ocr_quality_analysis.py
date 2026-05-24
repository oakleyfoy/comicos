from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    CoverImage,
    CoverImageDerivative,
    CoverImageOcrQualityAnalysis,
    CoverImageOcrResult,
    InventoryCopy,
    MetadataAudit,
)
from app.services.cover_images import resolve_filesystem_path, sha256_raw_bytes
from app.tasks.jobs import run_cover_image_ocr_job, run_cover_image_process_job


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


def make_checkerboard_png_bytes(
    *,
    size: tuple[int, int] = (1400, 900),
    cell: int = 48,
    blur_radius: float = 0.0,
) -> bytes:
    image = Image.new("RGB", size, color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    width, height = size
    for top in range(0, height, cell):
        for left in range(0, width, cell):
            color = (20, 20, 20) if ((left // cell) + (top // cell)) % 2 == 0 else (235, 235, 235)
            draw.rectangle((left, top, min(left + cell, width), min(top + cell, height)), fill=color)
    if blur_radius > 0:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_solid_png_bytes(
    *,
    size: tuple[int, int] = (1400, 900),
    color: tuple[int, int, int] = (128, 128, 128),
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


def _stub_ocr_enqueue(monkeypatch, cover_id: int) -> None:
    fake_job = type("FakeJob", (), {"id": f"cover-image-ocr-{cover_id}"})()
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_cover_image_ocr_job",
        lambda **kwargs: fake_job,
    )


def _bootstrap_processed_cover(
    client: TestClient,
    session: Session,
    monkeypatch,
    *,
    token: str,
    image_bytes: bytes,
    raw_text: str,
) -> tuple[int, int, int]:
    inv_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inv_id, image_bytes)
    inv_row = session.get(InventoryCopy, inv_id)
    assert inv_row is not None
    run_cover_image_process_job(cover_id, inv_row.user_id)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: raw_text)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract-quality")
    enq = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enq.status_code == 202
    ocr_result_id = enq.json()["ocr_result_id"]
    assert ocr_result_id is not None
    run_cover_image_ocr_job(cover_id, inv_row.user_id, ocr_result_id)
    return inv_id, cover_id, ocr_result_id


def _analysis_by_type(payload: dict) -> dict[str, dict]:
    return {row["quality_type"]: row for row in payload["analyses"]}


def test_ocr_quality_blur_detection_is_deterministic_and_penalizes_blurry_images(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "quality-blur@example.com")
    sharp_image = make_checkerboard_png_bytes()
    blurred_image = make_checkerboard_png_bytes(blur_radius=8.0)
    _sharp_inv, sharp_cover_id, _sharp_ocr = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=sharp_image,
        raw_text="INVINCIBLE IMAGE COMICS ISSUE 1",
    )
    _blur_inv, blurred_cover_id, _blur_ocr = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=blurred_image,
        raw_text="INVINCIBLE IMAGE COMICS ISSUE 1",
    )

    sharp_response = client.post(
        f"/cover-images/{sharp_cover_id}/analyze-ocr-quality",
        headers=auth_headers(token),
    )
    blurred_response = client.post(
        f"/cover-images/{blurred_cover_id}/analyze-ocr-quality",
        headers=auth_headers(token),
    )
    assert sharp_response.status_code == 200
    assert blurred_response.status_code == 200

    sharp_blur = _analysis_by_type(sharp_response.json())["blur_detection"]
    blurred_blur = _analysis_by_type(blurred_response.json())["blur_detection"]
    assert sharp_blur["detail_json"]["laplacian_variance"] > blurred_blur["detail_json"]["laplacian_variance"]
    assert sharp_blur["deterministic_score"] >= blurred_blur["deterministic_score"]


def test_ocr_quality_analysis_flags_low_resolution_and_low_contrast(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "quality-resolution-contrast@example.com")
    image_bytes = make_solid_png_bytes(size=(320, 420), color=(128, 128, 128))
    inv_id, cover_id, _ocr_result_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=image_bytes,
        raw_text="INVINCIBLE IMAGE COMICS ISSUE 1",
    )

    response = client.post(
        f"/cover-images/{cover_id}/analyze-ocr-quality",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_count"] == 6
    by_type = _analysis_by_type(payload)
    assert by_type["low_resolution"]["severity"] == "critical"
    assert by_type["low_resolution"]["deterministic_score"] < 0.5
    assert by_type["low_contrast"]["severity"] == "critical"
    assert by_type["low_contrast"]["deterministic_score"] < 0.5
    assert by_type["overall_quality"]["severity"] == "critical"

    detail = client.get(f"/inventory/{inv_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    cover_payload = next(item for item in detail.json()["cover_images"] if item["id"] == cover_id)
    assert len(cover_payload["ocr_quality_analyses"]) == 6


def test_ocr_quality_analysis_flags_unreadable_ocr_without_rerunning_ocr_or_mutating_metadata(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "quality-unreadable@example.com")
    inv_id, cover_id, _ocr_result_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_checkerboard_png_bytes(),
        raw_text="",
    )
    headers = auth_headers(token)
    before_inv = session.get(InventoryCopy, inv_id)
    before_cover = session.get(CoverImage, cover_id)
    before_ocr_count = session.exec(
        select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id == cover_id)
    ).all()
    assert before_inv is not None and before_cover is not None

    response = client.post(f"/cover-images/{cover_id}/analyze-ocr-quality", headers=headers)
    assert response.status_code == 200
    by_type = _analysis_by_type(response.json())
    assert by_type["unreadable_ocr"]["severity"] == "critical"
    assert by_type["unreadable_ocr"]["deterministic_score"] == 0.0
    assert by_type["unreadable_ocr"]["detail_json"]["raw_text_length"] == 0

    session.expire_all()
    inv_after = session.get(InventoryCopy, inv_id)
    cover_after = session.get(CoverImage, cover_id)
    after_ocr_count = session.exec(
        select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id == cover_id)
    ).all()
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash
    assert len(after_ocr_count) == len(before_ocr_count)


def test_ocr_quality_analysis_is_idempotent_and_records_regeneration_audits(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "quality-idempotent@example.com")
    _inv_id, cover_id, ocr_result_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_checkerboard_png_bytes(),
        raw_text="INVINCIBLE IMAGE COMICS ISSUE 1",
    )
    headers = auth_headers(token)

    first = client.post(f"/cover-images/{cover_id}/analyze-ocr-quality", headers=headers)
    assert first.status_code == 200
    first_by_type = _analysis_by_type(first.json())

    second = client.post(f"/cover-images/{cover_id}/analyze-ocr-quality", headers=headers)
    assert second.status_code == 200
    second_by_type = _analysis_by_type(second.json())
    assert {
        key: (value["id"], value["deterministic_score"], value["severity"])
        for key, value in second_by_type.items()
    } == {
        key: (value["id"], value["deterministic_score"], value["severity"])
        for key, value in first_by_type.items()
    }

    ocr_row = session.get(CoverImageOcrResult, ocr_result_id)
    assert ocr_row is not None
    ocr_row.raw_text = ""
    ocr_row.confidence_score = 0.0
    session.add(ocr_row)
    session.commit()

    regenerated = client.post(f"/cover-images/{cover_id}/analyze-ocr-quality", headers=headers)
    assert regenerated.status_code == 200
    regenerated_by_type = _analysis_by_type(regenerated.json())
    assert regenerated_by_type["unreadable_ocr"]["id"] == first_by_type["unreadable_ocr"]["id"]
    assert regenerated_by_type["unreadable_ocr"]["deterministic_score"] < first_by_type["unreadable_ocr"][
        "deterministic_score"
    ]

    rows = session.exec(
        select(CoverImageOcrQualityAnalysis)
        .where(CoverImageOcrQualityAnalysis.cover_image_id == cover_id)
        .order_by(CoverImageOcrQualityAnalysis.id.asc())
    ).all()
    assert len(rows) == 6

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_quality_analysis")
    ).all()
    actions = {audit.action for audit in audits}
    assert "ocr_quality_analysis_created" in actions
    assert "ocr_quality_analysis_regenerated" in actions


def test_ocr_quality_analysis_malformed_image_fails_safely(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "quality-malformed@example.com")
    _inv_id, cover_id, _ocr_result_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_checkerboard_png_bytes(),
        raw_text="INVINCIBLE IMAGE COMICS ISSUE 1",
    )
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
        f"/cover-images/{cover_id}/analyze-ocr-quality",
        headers=auth_headers(token),
    )
    assert response.status_code == 409
