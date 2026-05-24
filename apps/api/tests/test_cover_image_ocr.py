from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CoverImage, CoverImageOcrCandidate, CoverImageOcrResult, DraftImport, InventoryCopy
from app.services.cover_images import (
    OCR_CANDIDATE_EXTRACTION_VERSION,
    OCR_NORMALIZATION_VERSION,
    OCR_SOURCE_PROCESSING_VERSION,
    normalize_ocr_candidate_text,
)
from app.tasks.jobs import run_cover_image_ocr_job, run_cover_image_process_job
from app.tasks.queue import enqueue_cover_image_ocr_job


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


def _stub_ocr_enqueue(monkeypatch, cover_id: int) -> None:
    fake_job = type("FakeJob", (), {"id": f"cover-image-ocr-{cover_id}"})()
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_cover_image_ocr_job",
        lambda **kwargs: fake_job,
    )


def test_enqueue_cover_image_ocr_job_is_idempotent_for_active_job(monkeypatch) -> None:
    class ExistingJob:
        id = "cover-image-ocr-42"

        def get_status(self, refresh: bool = False) -> str:
            del refresh
            return "started"

    def fail_enqueue(*args, **kwargs):
        raise AssertionError("queue.enqueue should not be called when active OCR job already exists")

    class FakeQueue:
        name = "ai_parse"
        enqueue = staticmethod(fail_enqueue)

    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: ExistingJob())
    monkeypatch.setattr("app.tasks.queue.get_ai_parse_queue", lambda: FakeQueue())

    job = enqueue_cover_image_ocr_job(cover_image_id=42, user_id=7, ocr_result_id=99)
    assert job.id == "cover-image-ocr-42"


def test_cover_ocr_result_persists_and_preserves_raw_text(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-persist@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    raw_text = "  X-MEN   #1\n\n\nMARVEL  "
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: raw_text)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enqueue.status_code == 202
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None

    result = run_cover_image_ocr_job(cover_id, user_id, ocr_result_id)
    assert result["processing_status"] == "processed"

    session.expire_all()
    row = session.get(CoverImageOcrResult, ocr_result_id)
    assert row is not None
    assert row.raw_text == raw_text
    assert row.normalized_text == "X-MEN #1\n\nMARVEL"
    assert row.processing_status == "processed"
    assert row.ocr_engine == "tesseract"
    assert row.ocr_engine_version == "tesseract 5.0.0"

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    cover = next(item for item in detail.json()["cover_images"] if item["id"] == cover_id)
    assert cover["latest_ocr_result"]["id"] == ocr_result_id
    assert cover["latest_ocr_result"]["raw_text"] == raw_text
    assert cover["latest_ocr_result"]["normalized_text"] == "X-MEN #1\n\nMARVEL"
    assert cover["ocr_visibility"]["job_status"] == "idle"
    assert cover["ocr_visibility"]["retry_available"] is True
    assert cover["ocr_visibility"]["ocr_run_count"] == 1
    assert cover["ocr_visibility"]["prior_run_created_ats"] == []
    assert cover["matching_status"] == "ready"


def test_cover_ocr_gating_requires_ready_cover(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-gating@example.com")
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())
    _stub_ocr_enqueue(monkeypatch, cover_id)
    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enqueue.status_code == 202
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None

    with pytest.raises(ValueError, match="matching readiness must be ready"):
        run_cover_image_ocr_job(cover_id, inv.user_id, ocr_result_id)

    session.expire_all()
    row = session.get(CoverImageOcrResult, ocr_result_id)
    assert row is not None
    assert row.processing_status == "failed"
    assert row.processing_error is not None
    assert "matching readiness must be ready" in row.processing_error


def test_cover_ocr_failed_path_marks_result_failed(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-failed@example.com")
    _, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr(
        "app.services.cover_images._run_tesseract_ocr_on_cover_path",
        lambda path: (_ for _ in ()).throw(ValueError("Local Tesseract OCR engine is unavailable on this host.")),
    )

    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enqueue.status_code == 202
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None

    with pytest.raises(ValueError, match="unavailable on this host"):
        run_cover_image_ocr_job(cover_id, user_id, ocr_result_id)

    session.expire_all()
    row = session.get(CoverImageOcrResult, ocr_result_id)
    assert row is not None
    assert row.processing_status == "failed"
    assert row.processing_error is not None
    assert "unavailable on this host" in row.processing_error


def test_cover_ocr_history_rows_are_preserved(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-history@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    outputs = iter(["FIRST PASS", "SECOND PASS"])
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: next(outputs))
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    first_enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    second_enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert first_enqueue.status_code == 202
    assert second_enqueue.status_code == 202

    first_id = first_enqueue.json()["ocr_result_id"]
    second_id = second_enqueue.json()["ocr_result_id"]
    assert first_id is not None and second_id is not None
    assert first_id != second_id

    run_cover_image_ocr_job(cover_id, user_id, first_id)
    run_cover_image_ocr_job(cover_id, user_id, second_id)

    rows = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_id)
        .order_by(CoverImageOcrResult.id.asc())
    ).all()
    assert [row.raw_text for row in rows] == ["FIRST PASS", "SECOND PASS"]

    results = client.get(f"/cover-images/{cover_id}/ocr-results", headers=auth_headers(token))
    assert results.status_code == 200
    assert [row["raw_text"] for row in results.json()] == ["SECOND PASS", "FIRST PASS"]

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    latest = next(item for item in detail.json()["cover_images"] if item["id"] == cover_id)["latest_ocr_result"]
    assert latest["raw_text"] == "SECOND PASS"


def test_cover_ocr_endpoints_follow_cover_permissions(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-ocr-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "cover-ocr-owner@example.com")
    foreign_token = register_and_login(client, "cover-ocr-foreign@example.com")
    ops_token = register_and_login(client, "cover-ocr-ops@example.com")

    _, cover_id, _ = _make_cover_ready(client, session, owner_token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    owner_response = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(owner_token))
    assert owner_response.status_code == 202

    foreign_post = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(foreign_token))
    assert foreign_post.status_code == 404

    ops_post = client.post(f"/ops/cover-images/{cover_id}/run-ocr", headers=auth_headers(ops_token))
    assert ops_post.status_code == 202

    foreign_ops_post = client.post(
        f"/ops/cover-images/{cover_id}/run-ocr",
        headers=auth_headers(foreign_token),
    )
    assert foreign_ops_post.status_code == 403

    owner_results = client.get(f"/cover-images/{cover_id}/ocr-results", headers=auth_headers(owner_token))
    assert owner_results.status_code == 200

    foreign_results = client.get(f"/cover-images/{cover_id}/ocr-results", headers=auth_headers(foreign_token))
    assert foreign_results.status_code == 404
    get_settings.cache_clear()


def test_cover_ocr_enqueue_returns_already_queued_for_active_job(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-already-queued@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, token)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    fake_job = type(
        "FakeJob",
        (),
        {
            "id": f"cover-image-ocr-{cover_id}",
            "get_status": staticmethod(lambda refresh=False: "started"),
        },
    )()
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: fake_job)
    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: fake_job)

    response = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert response.status_code == 202
    assert response.json()["status"] == "already_queued"
    assert response.json()["ocr_result_id"] is None


def test_cover_ocr_pipeline_does_not_change_cover_metadata(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-immutable@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    set_primary = client.post(
        f"/inventory/{inventory_copy_id}/cover-images/{cover_id}/primary",
        headers=auth_headers(token),
    )
    assert set_primary.status_code == 200

    before_cover = session.get(CoverImage, cover_id)
    before_inv = session.get(InventoryCopy, inventory_copy_id)
    assert before_cover is not None
    assert before_inv is not None
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: "IMMUTABLE")
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None
    run_cover_image_ocr_job(cover_id, user_id, ocr_result_id)

    session.expire_all()
    after_cover = session.get(CoverImage, cover_id)
    after_inv = session.get(InventoryCopy, inventory_copy_id)
    assert after_cover is not None
    assert after_inv is not None
    assert after_cover.inventory_copy_id == before_cover.inventory_copy_id
    assert after_cover.draft_import_id == before_cover.draft_import_id
    assert after_cover.canonical_series_id == before_cover.canonical_series_id
    assert after_inv.primary_cover_image_id == before_inv.primary_cover_image_id


def test_cover_ocr_can_run_for_import_cover_and_results_are_visible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-import@example.com")
    create_response = client.post(
        "/imports/manual",
        headers=auth_headers(token),
        json={
            "raw_text": "import draft",
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
    assert create_response.status_code == 201
    import_id = create_response.json()["id"]

    upload = client.post(
        f"/imports/{import_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("import.png", make_png_bytes(), "image/png")},
        data={"source_type": "import_image"},
    )
    assert upload.status_code == 200
    cover_id = upload.json()["id"]
    _stub_ocr_enqueue(monkeypatch, cover_id)
    draft_import = session.get(DraftImport, import_id)
    assert draft_import is not None
    run_cover_image_process_job(cover_id, draft_import.user_id)

    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: "IMPORT OCR")
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")
    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enqueue.status_code == 202
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None

    run_cover_image_ocr_job(cover_id, draft_import.user_id, ocr_result_id)

    draft_detail = client.get(f"/imports/{import_id}", headers=auth_headers(token))
    assert draft_detail.status_code == 200
    latest = draft_detail.json()["cover_images"][0]["latest_ocr_result"]
    assert latest["raw_text"] == "IMPORT OCR"


def test_cover_ocr_retry_owner_endpoint_queues_like_run_ocr(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-retry-alias@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    response = client.post(f"/cover-images/{cover_id}/retry-ocr", headers=auth_headers(token))
    assert response.status_code == 202
    payload = response.json()
    assert payload["cover_image_id"] == cover_id
    assert payload["status"] in {"queued", "already_queued"}


def test_cover_ocr_retry_ops_endpoint_requires_ops_admin(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-retry-only-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "cover-retry-owner@example.com")
    ops_token = register_and_login(client, "cover-retry-only-ops@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, owner_token)
    _stub_ocr_enqueue(monkeypatch, cover_id)

    forbidden = client.post(
        f"/ops/cover-images/{cover_id}/retry-ocr",
        headers=auth_headers(owner_token),
    )
    assert forbidden.status_code == 403

    ok = client.post(f"/ops/cover-images/{cover_id}/retry-ocr", headers=auth_headers(ops_token))
    assert ok.status_code == 202
    get_settings.cache_clear()


def test_cover_ocr_retry_idempotent_when_active_job(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-retry-active@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, token)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    fake_job = type(
        "FakeJob",
        (),
        {
            "id": f"cover-image-ocr-{cover_id}",
            "get_status": staticmethod(lambda refresh=False: "started"),
        },
    )()
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: fake_job)
    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: fake_job)

    retry = client.post(f"/cover-images/{cover_id}/retry-ocr", headers=auth_headers(token))
    assert retry.status_code == 202
    assert retry.json()["status"] == "already_queued"
    assert retry.json()["ocr_result_id"] is None


def test_cover_ocr_retry_after_success_preserves_prior_result(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-retry-rerun@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    outputs = iter(["FIRST", "SECOND"])
    monkeypatch.setattr(
        "app.services.cover_images._run_tesseract_ocr_on_cover_path",
        lambda path: next(outputs),
    )
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.0.0")

    first = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert first.status_code == 202
    first_id = first.json()["ocr_result_id"]
    assert first_id is not None

    run_cover_image_ocr_job(cover_id, user_id, first_id)

    second = client.post(f"/cover-images/{cover_id}/retry-ocr", headers=auth_headers(token))
    assert second.status_code == 202
    second_id = second.json()["ocr_result_id"]
    assert second_id is not None
    assert second_id != first_id

    run_cover_image_ocr_job(cover_id, user_id, second_id)

    rows = session.exec(
        select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id == cover_id).order_by(CoverImageOcrResult.id.asc())
    ).all()
    assert [row.raw_text for row in rows] == ["FIRST", "SECOND"]

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    cover = next(c for c in detail.json()["cover_images"] if c["id"] == cover_id)
    assert cover["ocr_visibility"]["ocr_run_count"] >= 2
    assert len(cover["ocr_visibility"]["prior_run_created_ats"]) >= 1


def test_inventory_detail_includes_ocr_visibility_shape(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-vis-shape@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: "Z")
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract")

    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None
    run_cover_image_ocr_job(cover_id, user_id, ocr_result_id)

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    cover_payload = next(c for c in detail.json()["cover_images"] if c["id"] == cover_id)
    vis = cover_payload["ocr_visibility"]
    assert vis["job_status"] in {"idle", "queued", "running"}
    assert vis["retry_available"] is True
    assert vis["ocr_run_count"] == 1
    assert vis["prior_run_created_ats"] == []


def test_cover_ocr_replay_requires_existing_result(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-replay-needs-history@example.com")
    _, cover_id, _ = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)

    response = client.post(
        f"/cover-images/{cover_id}/replay-ocr",
        headers=auth_headers(token),
        json={"replay_reason": "manual replay"},
    )
    assert response.status_code == 409
    assert "No prior OCR result exists" in response.json()["detail"]


def test_cover_ocr_replay_persists_snapshot_and_linkage(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-replay-snapshot@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    outputs = iter(["FIRST OCR", "SECOND OCR"])
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: next(outputs))
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.1.0")

    first = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert first.status_code == 202
    first_id = first.json()["ocr_result_id"]
    assert first_id is not None
    run_cover_image_ocr_job(cover_id, user_id, first_id)

    replay = client.post(
        f"/cover-images/{cover_id}/replay-ocr",
        headers=auth_headers(token),
        json={"replay_reason": "manual audit replay"},
    )
    assert replay.status_code == 202
    replay_id = replay.json()["ocr_result_id"]
    assert replay_id is not None
    assert replay_id != first_id
    run_cover_image_ocr_job(cover_id, user_id, replay_id)

    session.expire_all()
    cover = session.get(CoverImage, cover_id)
    replay_row = session.get(CoverImageOcrResult, replay_id)
    assert cover is not None
    assert replay_row is not None
    assert replay_row.replay_of_ocr_result_id == first_id
    assert replay_row.replay_reason == "manual audit replay"
    assert replay_row.source_cover_image_sha256 == cover.sha256_hash
    assert replay_row.source_processing_version == OCR_SOURCE_PROCESSING_VERSION
    assert replay_row.normalization_version == OCR_NORMALIZATION_VERSION
    assert replay_row.source_thumb_derivative_sha256 is not None
    assert replay_row.source_medium_derivative_sha256 is not None

    results = client.get(f"/cover-images/{cover_id}/ocr-results", headers=auth_headers(token))
    assert results.status_code == 200
    payload = results.json()
    assert payload[0]["id"] == replay_id
    assert payload[0]["replay_of_ocr_result_id"] == first_id
    assert payload[0]["replay_reason"] == "manual audit replay"
    assert payload[0]["snapshot"]["source_cover_image_sha256"] == cover.sha256_hash
    assert payload[0]["snapshot"]["source_processing_version"] == OCR_SOURCE_PROCESSING_VERSION
    assert payload[0]["snapshot"]["normalization_version"] == OCR_NORMALIZATION_VERSION

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    cover_payload = next(c for c in detail.json()["cover_images"] if c["id"] == cover_id)
    assert cover_payload["latest_ocr_result"]["id"] == replay_id
    assert cover_payload["latest_ocr_result"]["replay_of_ocr_result_id"] == first_id


def test_cover_ocr_replay_does_not_mutate_cover_metadata_or_linkage(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-replay-immutable@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: "BASELINE OCR")
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.1.0")

    first = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    first_id = first.json()["ocr_result_id"]
    assert first_id is not None
    run_cover_image_ocr_job(cover_id, user_id, first_id)

    before_cover = session.get(CoverImage, cover_id)
    before_inv = session.get(InventoryCopy, inventory_copy_id)
    assert before_cover is not None
    assert before_inv is not None

    replay = client.post(
        f"/cover-images/{cover_id}/replay-ocr",
        headers=auth_headers(token),
        json={"replay_reason": "integrity check"},
    )
    replay_id = replay.json()["ocr_result_id"]
    assert replay_id is not None
    run_cover_image_ocr_job(cover_id, user_id, replay_id)

    session.expire_all()
    after_cover = session.get(CoverImage, cover_id)
    after_inv = session.get(InventoryCopy, inventory_copy_id)
    assert after_cover is not None
    assert after_inv is not None
    assert after_cover.inventory_copy_id == before_cover.inventory_copy_id
    assert after_cover.draft_import_id == before_cover.draft_import_id
    assert after_cover.canonical_series_id == before_cover.canonical_series_id
    assert after_cover.sha256_hash == before_cover.sha256_hash
    assert after_inv.primary_cover_image_id == before_inv.primary_cover_image_id


def test_cover_ocr_candidate_normalization_is_deterministic() -> None:
    assert normalize_ocr_candidate_text("  Batman   #1  ") == "BATMAN #1"
    assert normalize_ocr_candidate_text("\nmarvel   comics\t") == "MARVEL COMICS"
    assert normalize_ocr_candidate_text("   ") is None


def test_cover_ocr_extracts_title_issue_barcode_and_publisher_candidates(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-candidates@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    raw_text = "  Batman   #1  \nMarvel\nUPC 123456789012  "
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: raw_text)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.2.0")

    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enqueue.status_code == 202
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None
    run_cover_image_ocr_job(cover_id, user_id, ocr_result_id)

    session.expire_all()
    rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id == cover_id)
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()
    assert rows
    assert all(row.extraction_version == OCR_CANDIDATE_EXTRACTION_VERSION for row in rows)
    by_type = {(row.candidate_type, row.extraction_source, row.raw_candidate_text): row for row in rows}
    assert ("title", "full_cover", "BATMAN") in by_type
    assert ("issue_number", "full_cover", "1") in by_type
    assert ("publisher", "full_cover", "MARVEL") in by_type
    assert ("barcode", "full_cover", "123456789012") in by_type

    detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    cover = next(item for item in detail.json()["cover_images"] if item["id"] == cover_id)
    assert len(cover["ocr_candidates"]) >= 4
    grouped = {item["candidate_type"] for item in cover["ocr_candidates"]}
    assert {"title", "issue_number", "publisher", "barcode"}.issubset(grouped)


def test_cover_ocr_candidate_history_rows_are_preserved(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-candidate-history@example.com")
    _, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    outputs = iter(["BATMAN #1", "BATMAN #2"])
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: next(outputs))
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.2.0")

    first = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    second = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    first_id = first.json()["ocr_result_id"]
    second_id = second.json()["ocr_result_id"]
    assert first_id is not None and second_id is not None

    run_cover_image_ocr_job(cover_id, user_id, first_id)
    run_cover_image_ocr_job(cover_id, user_id, second_id)

    rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id == cover_id)
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()
    assert any(row.ocr_result_id == first_id and row.raw_candidate_text == "1" for row in rows)
    assert any(row.ocr_result_id == second_id and row.raw_candidate_text == "2" for row in rows)


def test_cover_ocr_candidate_extraction_does_not_mutate_metadata(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-ocr-candidate-immutable@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: "MARVEL BATMAN #1")
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract 5.2.0")

    before_cover = session.get(CoverImage, cover_id)
    before_inv = session.get(InventoryCopy, inventory_copy_id)
    assert before_cover is not None
    assert before_inv is not None

    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None
    run_cover_image_ocr_job(cover_id, user_id, ocr_result_id)

    session.expire_all()
    after_cover = session.get(CoverImage, cover_id)
    after_inv = session.get(InventoryCopy, inventory_copy_id)
    assert after_cover is not None
    assert after_inv is not None
    assert after_cover.inventory_copy_id == before_cover.inventory_copy_id
    assert after_cover.draft_import_id == before_cover.draft_import_id
    assert after_cover.canonical_series_id == before_cover.canonical_series_id
    assert after_inv.primary_cover_image_id == before_inv.primary_cover_image_id
