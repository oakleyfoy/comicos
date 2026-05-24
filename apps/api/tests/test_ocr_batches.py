from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import CoverImage, CoverImageOcrResult, InventoryCopy, MetadataAudit, OcrBatch, OcrBatchItem
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


def _make_cover_ready(client: TestClient, session: Session, token: str) -> tuple[int, int, int]:
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())
    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    run_cover_image_process_job(cover_id, inv.user_id)
    return inventory_copy_id, cover_id, inv.user_id


class _FakeQueuedJob:
    def __init__(self, job_id: str):
        self.id = job_id
        self.exc_info = None

    def get_status(self, refresh: bool = False) -> str:
        del refresh
        return "queued"


class _FakeRunningJob:
    def __init__(self, job_id: str):
        self.id = job_id
        self.exc_info = None

    def get_status(self, refresh: bool = False) -> str:
        del refresh
        return "started"


def _stub_batch_enqueue(monkeypatch) -> None:
    monkeypatch.setattr("app.services.ocr_batches.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr(
        "app.services.ocr_batches.enqueue_cover_image_ocr_job",
        lambda *, cover_image_id, user_id, ocr_result_id: _FakeQueuedJob(f"cover-image-ocr-{cover_image_id}"),
    )


def test_create_ocr_batch_dedupes_ids_orders_items_and_skips_invalid_ids(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "ocr-batch-create@example.com")
    _inv_a, cover_a, _user_a = _make_cover_ready(client, session, token)
    _inv_b, cover_b, _user_b = _make_cover_ready(client, session, token)

    response = client.post(
        "/ocr-batches",
        headers=auth_headers(token),
        json={"cover_image_ids": [cover_b, 999999, cover_a, cover_a]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["total_items"] == 2
    assert [item["cover_image_id"] for item in payload["items"]] == [cover_a, cover_b]
    assert payload["status"] == "pending"
    assert payload["batch_options_json"]["invalid_cover_image_ids"] == [999999]
    assert payload["batch_options_json"]["duplicate_cover_image_ids"] == [cover_a]

    audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_batch")).all()
    assert any(a.action == "ocr_batch_created" for a in audits)


def test_enqueue_ocr_batch_marks_items_queued_without_metadata_mutation(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ocr-batch-enqueue@example.com")
    inv_id, cover_id, _user_id = _make_cover_ready(client, session, token)
    create = client.post("/ocr-batches", headers=auth_headers(token), json={"cover_image_ids": [cover_id]})
    assert create.status_code == 201
    batch_id = create.json()["id"]
    _stub_batch_enqueue(monkeypatch)
    before_inv = session.get(InventoryCopy, inv_id)
    before_cover = session.get(CoverImage, cover_id)
    assert before_inv is not None and before_cover is not None

    enqueue = client.post(f"/ocr-batches/{batch_id}/enqueue", headers=auth_headers(token))
    assert enqueue.status_code == 200
    payload = enqueue.json()
    assert payload["status"] == "running"
    assert payload["pending_count"] == 1
    assert payload["items"][0]["status"] == "queued"
    assert payload["items"][0]["attempt_count"] == 1
    assert payload["items"][0]["job_id"] == f"cover-image-ocr-{cover_id}"

    session.expire_all()
    inv_after = session.get(InventoryCopy, inv_id)
    cover_after = session.get(CoverImage, cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.sha256_hash == before_cover.sha256_hash
    assert cover_after.canonical_series_id == before_cover.canonical_series_id


def test_ocr_batch_success_updates_item_and_batch_counts(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ocr-batch-success@example.com")
    _inv_id, cover_id, user_id = _make_cover_ready(client, session, token)
    create = client.post("/ocr-batches", headers=auth_headers(token), json={"cover_image_ids": [cover_id]})
    batch_id = create.json()["id"]
    _stub_batch_enqueue(monkeypatch)
    client.post(f"/ocr-batches/{batch_id}/enqueue", headers=auth_headers(token))

    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: "INVINCIBLE #1")
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract-batch")
    monkeypatch.setattr(
        "app.tasks.jobs.get_current_job",
        lambda: type("FakeCurrentJob", (), {"id": f"cover-image-ocr-{cover_id}"})(),
    )
    ocr_result = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_id)
        .order_by(CoverImageOcrResult.id.desc())
    ).first()
    assert ocr_result is not None
    run_cover_image_ocr_job(cover_id, user_id, ocr_result.id)

    detail = client.get(f"/ocr-batches/{batch_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "completed"
    assert payload["completed_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["items"][0]["status"] == "completed"

    item_audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_batch_item")).all()
    assert any(a.action == "ocr_batch_item_completed" for a in item_audits)


def test_ocr_batch_failure_retry_and_history_preservation(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ocr-batch-retry@example.com")
    _inv_id, cover_id, user_id = _make_cover_ready(client, session, token)
    create = client.post("/ocr-batches", headers=auth_headers(token), json={"cover_image_ids": [cover_id]})
    batch_id = create.json()["id"]
    _stub_batch_enqueue(monkeypatch)
    client.post(f"/ocr-batches/{batch_id}/enqueue", headers=auth_headers(token))

    monkeypatch.setattr(
        "app.services.cover_images._run_tesseract_ocr_on_cover_path",
        lambda path: (_ for _ in ()).throw(ValueError("OCR engine unavailable")),
    )
    monkeypatch.setattr(
        "app.tasks.jobs.get_current_job",
        lambda: type("FakeCurrentJob", (), {"id": f"cover-image-ocr-{cover_id}"})(),
    )
    first_ocr = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_id)
        .order_by(CoverImageOcrResult.id.desc())
    ).first()
    assert first_ocr is not None
    try:
        run_cover_image_ocr_job(cover_id, user_id, first_ocr.id)
    except ValueError:
        pass

    failed = client.get(f"/ocr-batches/{batch_id}", headers=auth_headers(token))
    assert failed.status_code == 200
    failed_payload = failed.json()
    assert failed_payload["status"] == "failed"
    assert failed_payload["failed_count"] == 1
    assert failed_payload["items"][0]["status"] == "failed"

    _stub_batch_enqueue(monkeypatch)
    retry = client.post(f"/ocr-batches/{batch_id}/retry-failed", headers=auth_headers(token))
    assert retry.status_code == 200
    retry_payload = retry.json()
    assert retry_payload["items"][0]["status"] == "queued"
    assert retry_payload["items"][0]["attempt_count"] == 1

    session.expire_all()
    rows_after_retry = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_id)
        .order_by(CoverImageOcrResult.id.asc())
    ).all()
    assert len(rows_after_retry) == 2
    assert {row.processing_status for row in rows_after_retry} == {"failed", "pending"}

    batch_audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_batch")).all()
    actions = {audit.action for audit in batch_audits}
    assert "ocr_batch_retry_requested" in actions
    assert "ocr_batch_failed" in actions


def test_ocr_batch_cancel_marks_pending_or_queued_items_cancelled(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ocr-batch-cancel@example.com")
    _inv_a, cover_a, _user_a = _make_cover_ready(client, session, token)
    _inv_b, cover_b, _user_b = _make_cover_ready(client, session, token)
    create = client.post(
        "/ocr-batches",
        headers=auth_headers(token),
        json={"cover_image_ids": [cover_a, cover_b]},
    )
    batch_id = create.json()["id"]
    _stub_batch_enqueue(monkeypatch)
    client.post(f"/ocr-batches/{batch_id}/enqueue", headers=auth_headers(token))

    cancel = client.post(f"/ocr-batches/{batch_id}/cancel", headers=auth_headers(token))
    assert cancel.status_code == 200
    payload = cancel.json()
    assert payload["status"] == "cancelled"
    assert {item["status"] for item in payload["items"]} == {"cancelled"}

    rows = session.exec(select(OcrBatchItem).where(OcrBatchItem.batch_id == batch_id)).all()
    assert rows and all(row.status == "cancelled" for row in rows)
    batch = session.get(OcrBatch, batch_id)
    assert batch is not None
    assert batch.status == "cancelled"

    item_audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_batch_item")).all()
    assert any(a.action == "ocr_batch_item_cancelled" for a in item_audits)
