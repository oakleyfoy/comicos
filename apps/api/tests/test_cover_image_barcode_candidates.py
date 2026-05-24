from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import CoverImage, CoverImageBarcodeCandidate, CoverImageOcrCandidate, InventoryCopy, MetadataAudit
from app.services.cover_images import BARCODE_CANDIDATE_EXTRACTION_VERSION, normalize_barcode_candidate_value
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


def _stub_ocr_enqueue(monkeypatch, cover_id: int) -> None:
    fake_job = type("FakeJob", (), {"id": f"cover-image-ocr-{cover_id}"})()
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_cover_image_ocr_job",
        lambda **kwargs: fake_job,
    )


def _bootstrap_cover(client: TestClient, session: Session, monkeypatch, *, raw_text: str, suffix: str) -> tuple[str, int, int]:
    token = register_and_login(client, f"barcode-{suffix}@example.com")
    inv_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inv_id, make_png_bytes())
    inv_row = session.get(InventoryCopy, inv_id)
    assert inv_row is not None

    run_cover_image_process_job(cover_id, inv_row.user_id)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: raw_text)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract-barcode")
    enq = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enq.status_code == 202
    ocr_result_id = enq.json()["ocr_result_id"]
    assert ocr_result_id is not None
    run_cover_image_ocr_job(cover_id, inv_row.user_id, ocr_result_id)
    return token, inv_id, cover_id


def test_barcode_normalization_rules_are_deterministic() -> None:
    assert normalize_barcode_candidate_value(" 1234-5678-9012 ") == ("123456789012", "upc_a")
    assert normalize_barcode_candidate_value("UPC-E 123456") == ("123456", "upc_e")
    assert normalize_barcode_candidate_value("1234-5678") == ("12345678", "upc_e")
    assert normalize_barcode_candidate_value("12345") is None
    assert normalize_barcode_candidate_value("   ") is None


def test_barcode_extraction_from_ocr_candidate_persists_and_audits(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, inv_id, cover_id = _bootstrap_cover(
        client,
        session,
        monkeypatch,
        raw_text="INVINCIBLE #1 IMAGE UPC 123456789012",
        suffix="ocr-candidate",
    )
    hdrs = auth_headers(token)
    before_inv = session.get(InventoryCopy, inv_id)
    before_cover = session.get(CoverImage, cover_id)
    assert before_inv is not None and before_cover is not None

    response = client.post(f"/cover-images/{cover_id}/extract-barcodes", headers=hdrs)
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] >= 1

    rows = session.exec(
        select(CoverImageBarcodeCandidate)
        .where(CoverImageBarcodeCandidate.cover_image_id == cover_id)
        .order_by(CoverImageBarcodeCandidate.id.asc())
    ).all()
    assert rows
    row = rows[0]
    assert row.raw_barcode_value == "123456789012"
    assert row.normalized_upc_value == "123456789012"
    assert row.barcode_type == "upc_a"
    assert row.source_ocr_result_id is not None
    assert row.source_ocr_candidate_id is not None
    assert row.extraction_version == BARCODE_CANDIDATE_EXTRACTION_VERSION

    candidate_row = session.get(CoverImageOcrCandidate, row.source_ocr_candidate_id)
    assert candidate_row is not None
    assert candidate_row.candidate_type == "barcode"

    detail = client.get(f"/inventory/{inv_id}", headers=hdrs)
    assert detail.status_code == 200
    cover_payload = next(item for item in detail.json()["cover_images"] if item["id"] == cover_id)
    assert cover_payload["barcode_candidates"][0]["normalized_upc_value"] == "123456789012"

    session.expire_all()
    inv_after = session.get(InventoryCopy, inv_id)
    cover_after = session.get(CoverImage, cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash

    audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "barcode_candidate")).all()
    assert any(a.action == "barcode_candidate_created" for a in audits)


def test_barcode_extraction_from_full_text_supports_upc_e(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, _inv_id, cover_id = _bootstrap_cover(
        client,
        session,
        monkeypatch,
        raw_text="notes UPC-E 123456 lower text",
        suffix="upc-e",
    )
    response = client.post(f"/cover-images/{cover_id}/extract-barcodes", headers=auth_headers(token))
    assert response.status_code == 200
    rows = session.exec(
        select(CoverImageBarcodeCandidate).where(CoverImageBarcodeCandidate.cover_image_id == cover_id)
    ).all()
    assert len(rows) == 1
    assert rows[0].normalized_upc_value == "123456"
    assert rows[0].barcode_type == "upc_e"
    assert rows[0].source_ocr_candidate_id is None
    assert rows[0].source_ocr_result_id is not None


def test_barcode_extraction_skips_malformed_and_empty_values_safely(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token_bad, _inv_id_bad, cover_bad = _bootstrap_cover(
        client,
        session,
        monkeypatch,
        raw_text="barcode 12345 and maybe 1234567-890",
        suffix="malformed",
    )
    malformed = client.post(f"/cover-images/{cover_bad}/extract-barcodes", headers=auth_headers(token_bad))
    assert malformed.status_code == 200
    assert malformed.json()["candidate_count"] == 0

    token_empty, _inv_id_empty, cover_empty = _bootstrap_cover(
        client,
        session,
        monkeypatch,
        raw_text="   ",
        suffix="empty",
    )
    empty = client.post(f"/cover-images/{cover_empty}/extract-barcodes", headers=auth_headers(token_empty))
    assert empty.status_code == 200
    assert empty.json()["candidate_count"] == 0


def test_barcode_extraction_rerun_is_idempotent_and_review_persists(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, _inv_id, cover_id = _bootstrap_cover(
        client,
        session,
        monkeypatch,
        raw_text="UPC 123456789012 and UPC-E 123456",
        suffix="idempotent",
    )
    hdrs = auth_headers(token)

    first = client.post(f"/cover-images/{cover_id}/extract-barcodes", headers=hdrs)
    assert first.status_code == 200
    first_ids = [candidate["id"] for candidate in first.json()["candidates"]]
    assert len(first_ids) == 2

    approve = client.patch(f"/barcode-candidates/{first_ids[0]}/approve", headers=hdrs)
    reject = client.patch(f"/barcode-candidates/{first_ids[1]}/reject", headers=hdrs)
    assert approve.status_code == 200
    assert reject.status_code == 200
    assert approve.json()["review_state"] == "approved"
    assert reject.json()["review_state"] == "rejected"

    second = client.post(f"/cover-images/{cover_id}/extract-barcodes", headers=hdrs)
    assert second.status_code == 200
    second_ids = [candidate["id"] for candidate in second.json()["candidates"]]
    assert second_ids == first_ids

    session.expire_all()
    rows = session.exec(
        select(CoverImageBarcodeCandidate)
        .where(CoverImageBarcodeCandidate.cover_image_id == cover_id)
        .order_by(CoverImageBarcodeCandidate.id.asc())
    ).all()
    assert {row.id for row in rows} == set(first_ids)
    by_id = {row.id: row for row in rows}
    assert by_id[first_ids[0]].review_state == "approved"
    assert by_id[first_ids[1]].review_state == "rejected"

    audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "barcode_candidate")).all()
    actions = {audit.action for audit in audits}
    assert "barcode_candidate_created" in actions
    assert "barcode_candidate_approved" in actions
    assert "barcode_candidate_rejected" in actions
