from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    CoverImage,
    CoverImageOcrCandidate,
    CoverImageOcrReconciliationWarning,
    InventoryCopy,
    MetadataAudit,
)
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


def _bootstrap_cover_candidates(
    client: TestClient,
    session: Session,
    monkeypatch,
    *,
    raw_text: str,
    suffix: str,
) -> tuple[str, int, int]:
    token = register_and_login(client, f"ocr-recon-{suffix}@example.com")
    inv_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inv_id, make_png_bytes())
    inv_row = session.get(InventoryCopy, inv_id)
    assert inv_row is not None

    run_cover_image_process_job(cover_id, inv_row.user_id)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr(
        "app.services.cover_images._run_tesseract_ocr_on_cover_path",
        lambda path: raw_text,
    )
    monkeypatch.setattr(
        "app.services.cover_images.get_tesseract_engine_version",
        lambda: "tesseract-reconciliation",
    )
    enq = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enq.status_code == 202
    ocr_id = enq.json()["ocr_result_id"]
    assert ocr_id is not None
    run_cover_image_ocr_job(cover_id, inv_row.user_id, ocr_id)
    return token, inv_id, cover_id


def _candidate_by_type(session: Session, cover_id: int, candidate_type: str) -> CoverImageOcrCandidate:
    row = session.exec(
        select(CoverImageOcrCandidate)
        .where(
            CoverImageOcrCandidate.cover_image_id == cover_id,
            CoverImageOcrCandidate.candidate_type == candidate_type,
        )
        .order_by(CoverImageOcrCandidate.id.asc())
    ).first()
    assert row is not None
    return row


def _open_warnings(session: Session, cover_id: int) -> list[CoverImageOcrReconciliationWarning]:
    return session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(
            CoverImageOcrReconciliationWarning.cover_image_id == cover_id,
            CoverImageOcrReconciliationWarning.status == "open",
        )
        .order_by(CoverImageOcrReconciliationWarning.id.asc())
    ).all()


def test_ocr_reconciliation_approved_title_mismatch_is_recorded_without_metadata_mutation(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="BATMAN #1 MARVEL",
        suffix="approved-title",
    )
    hdrs = auth_headers(token)
    title_candidate = _candidate_by_type(session, cover_id, "title")
    assert title_candidate.id is not None

    before_inv = session.get(InventoryCopy, inv_id)
    before_cover = session.get(CoverImage, cover_id)
    assert before_inv is not None and before_cover is not None

    approve_response = client.post(f"/ocr-candidates/{title_candidate.id}/approve", headers=hdrs)
    assert approve_response.status_code == 200

    reconcile = client.post(f"/cover-images/{cover_id}/reconcile-ocr-metadata", headers=hdrs)
    assert reconcile.status_code == 200
    payload = reconcile.json()
    title_warning = next(
        warning for warning in payload["warnings"] if warning["warning_type"] == "title_mismatch"
    )
    assert title_warning["severity"] == "warning"
    assert title_warning["current_metadata_value"] == "Invincible"
    assert title_warning["candidate_value"] == "BATMAN"

    session.expire_all()
    inv_after = session.get(InventoryCopy, inv_id)
    cover_after = session.get(CoverImage, cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_reconciliation_warning")
    ).all()
    assert any(a.action == "ocr_reconciliation_warning_created" for a in audits)


def test_ocr_reconciliation_rejected_candidates_are_ignored(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="BATMAN #1 MARVEL",
        suffix="rejected",
    )
    hdrs = auth_headers(token)
    title_candidate = _candidate_by_type(session, cover_id, "title")
    assert title_candidate.id is not None

    reject_response = client.post(f"/ocr-candidates/{title_candidate.id}/reject", headers=hdrs)
    assert reject_response.status_code == 200

    reconcile = client.post(f"/cover-images/{cover_id}/reconcile-ocr-metadata", headers=hdrs)
    assert reconcile.status_code == 200
    warning_types = {warning["warning_type"] for warning in reconcile.json()["warnings"]}
    assert "title_mismatch" not in warning_types


def test_ocr_reconciliation_pending_candidate_creates_lower_severity_warning(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="BATMAN #1 IMAGE",
        suffix="pending",
    )
    reconcile = client.post(
        f"/cover-images/{cover_id}/reconcile-ocr-metadata",
        headers=auth_headers(token),
    )
    assert reconcile.status_code == 200
    title_warning = next(
        warning for warning in reconcile.json()["warnings"] if warning["warning_type"] == "title_mismatch"
    )
    assert title_warning["severity"] == "info"


def test_ocr_reconciliation_barcode_candidate_creates_info_warning(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="INVINCIBLE #1 IMAGE 123456789012",
        suffix="barcode",
    )
    reconcile = client.post(
        f"/cover-images/{cover_id}/reconcile-ocr-metadata",
        headers=auth_headers(token),
    )
    assert reconcile.status_code == 200
    barcode_warning = next(
        warning for warning in reconcile.json()["warnings"] if warning["warning_type"] == "barcode_present"
    )
    assert barcode_warning["severity"] == "info"
    assert barcode_warning["candidate_value"] == "123456789012"


def test_ocr_reconciliation_warning_acknowledge_dismiss_and_idempotent_refresh(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="BATMAN #2 MARVEL 123456789012",
        suffix="status-flow",
    )
    hdrs = auth_headers(token)
    title_candidate = _candidate_by_type(session, cover_id, "title")
    issue_candidate = _candidate_by_type(session, cover_id, "issue_number")
    barcode_candidate = _candidate_by_type(session, cover_id, "barcode")
    assert title_candidate.id is not None
    assert issue_candidate.id is not None
    assert barcode_candidate.id is not None

    client.post(f"/ocr-candidates/{title_candidate.id}/approve", headers=hdrs)
    issue_candidate.confidence_score = 0.42
    session.add(issue_candidate)
    session.commit()

    first = client.post(f"/cover-images/{cover_id}/reconcile-ocr-metadata", headers=hdrs)
    assert first.status_code == 200
    first_payload = first.json()
    first_ids = [warning["id"] for warning in first_payload["warnings"]]
    assert len(first_ids) >= 3

    second = client.post(f"/cover-images/{cover_id}/reconcile-ocr-metadata", headers=hdrs)
    assert second.status_code == 200
    second_payload = second.json()
    assert [warning["id"] for warning in second_payload["warnings"]] == first_ids

    title_warning_id = next(
        warning["id"] for warning in second_payload["warnings"] if warning["warning_type"] == "title_mismatch"
    )
    barcode_warning_id = next(
        warning["id"] for warning in second_payload["warnings"] if warning["warning_type"] == "barcode_present"
    )

    ack = client.patch(f"/ocr-reconciliation-warnings/{title_warning_id}/acknowledge", headers=hdrs)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    assert ack.json()["resolved_by_user_id"] is not None

    dismiss = client.patch(f"/ocr-reconciliation-warnings/{barcode_warning_id}/dismiss", headers=hdrs)
    assert dismiss.status_code == 200
    assert dismiss.json()["status"] == "dismissed"
    assert dismiss.json()["resolved_by_user_id"] is not None

    session.expire_all()
    title_warning = session.get(CoverImageOcrReconciliationWarning, title_warning_id)
    barcode_warning = session.get(CoverImageOcrReconciliationWarning, barcode_warning_id)
    assert title_warning is not None and barcode_warning is not None
    assert title_warning.status == "acknowledged"
    assert barcode_warning.status == "dismissed"
    assert title_warning.resolved_at is not None
    assert barcode_warning.resolved_at is not None

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_reconciliation_warning")
    ).all()
    actions = {audit.action for audit in audits}
    assert "ocr_reconciliation_warning_created" in actions
    assert "ocr_reconciliation_warning_acknowledged" in actions
    assert "ocr_reconciliation_warning_dismissed" in actions

    assert len(_open_warnings(session, cover_id)) == sum(
        1 for warning in second_payload["warnings"] if warning["id"] not in {title_warning_id, barcode_warning_id}
    )


def test_ocr_reconciliation_ops_endpoints_work_for_admin(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ocr-recon-ops@example.com")
    get_settings.cache_clear()

    _, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="BATMAN #1 MARVEL",
        suffix="ops",
    )
    ops_token = register_and_login(client, "ocr-recon-ops@example.com")
    forbidden = register_and_login(client, "ocr-recon-not-ops@example.com")

    deny = client.post(
        f"/ops/cover-images/{cover_id}/reconcile-ocr-metadata",
        headers=auth_headers(forbidden),
    )
    assert deny.status_code == 403

    ok = client.post(
        f"/ops/cover-images/{cover_id}/reconcile-ocr-metadata",
        headers=auth_headers(ops_token),
    )
    assert ok.status_code == 200
    warning_id = ok.json()["warnings"][0]["id"]

    ack = client.patch(
        f"/ops/ocr-reconciliation-warnings/{warning_id}/acknowledge",
        headers=auth_headers(ops_token),
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    get_settings.cache_clear()
