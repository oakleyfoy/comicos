from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CoverImage, CoverImageOcrCandidate, InventoryCopy, MetadataAudit
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
    token = register_and_login(client, f"candrev-{suffix}@example.com")
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
        lambda: "tesseract-review",
    )
    enq = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enq.status_code == 202
    ocr_id = enq.json()["ocr_result_id"]
    assert ocr_id is not None
    run_cover_image_ocr_job(cover_id, inv_row.user_id, ocr_id)
    return token, inv_id, cover_id


def test_ocr_candidate_approve_reject_notes_audit_keeps_inventory(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="BATMAN #1 MARVEL",
        suffix="basic",
    )
    hdrs = auth_headers(token)

    cands = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id == cover_id)
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()
    assert len(cands) >= 2
    assert cands[0].id is not None and cands[1].id is not None
    cid0, cid1 = cands[0].id, cands[1].id

    before_inv = session.get(InventoryCopy, inv_id)
    before_cover = session.get(CoverImage, cover_id)
    assert before_inv is not None and before_cover is not None

    assert (
        client.post(f"/ocr-candidates/{cid0}/approve", headers=hdrs).status_code == 200
    )
    assert (
        client.post(f"/ocr-candidates/{cid1}/reject", headers=hdrs).status_code == 200
    )

    rn = client.patch(
        f"/ocr-candidates/{cid1}/review-notes",
        headers=hdrs,
        json={"review_notes": "  note-x  "},
    )
    assert rn.status_code == 200
    assert rn.json()["review_notes"] == "note-x"

    session.expire_all()
    audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_candidate")).all()
    acts = {a.action for a in audits}
    assert "ocr_candidate_approved" in acts
    assert "ocr_candidate_rejected" in acts
    assert "ocr_candidate_review_notes_updated" in acts

    session.expire_all()
    row0 = session.get(CoverImageOcrCandidate, cid0)
    row1 = session.get(CoverImageOcrCandidate, cid1)
    assert row0 is not None and row1 is not None
    assert row0.review_status == "approved"
    assert row1.review_status == "rejected"

    session.expire_all()
    inv_after = session.get(InventoryCopy, inv_id)
    cover_after = session.get(CoverImage, cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.sha256_hash == before_cover.sha256_hash
    assert cover_after.canonical_series_id == before_cover.canonical_series_id


def test_ocr_candidate_review_foreign_blocked_for_non_owner(client: TestClient, session: Session, monkeypatch) -> None:
    _, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="MARVEL BATMAN #1",
        suffix="perms",
    )
    cands = session.exec(
        select(CoverImageOcrCandidate).where(CoverImageOcrCandidate.cover_image_id == cover_id)
    ).all()
    assert cands and cands[0].id is not None
    cid = cands[0].id

    other_token = register_and_login(client, "candrev-foreign-perms@example.com")
    assert client.post(f"/ocr-candidates/{cid}/approve", headers=auth_headers(other_token)).status_code == 404


def test_ocr_candidate_ops_review_endpoints(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "candrev-ops@example.com")
    get_settings.cache_clear()

    _, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="BATMAN #1",
        suffix="ops",
    )
    cands = session.exec(
        select(CoverImageOcrCandidate).where(CoverImageOcrCandidate.cover_image_id == cover_id)
    ).all()
    assert cands and cands[0].id is not None
    cid = cands[0].id

    ops_token = register_and_login(client, "candrev-ops@example.com")

    forbidden = register_and_login(client, "candrev-not-ops@example.com")

    deny = client.post(f"/ops/ocr-candidates/{cid}/approve", headers=auth_headers(forbidden))
    assert deny.status_code == 403

    ok = client.post(f"/ops/ocr-candidates/{cid}/approve", headers=auth_headers(ops_token))
    assert ok.status_code == 200

    patch_ok = client.patch(
        f"/ops/ocr-candidates/{cid}/review-notes",
        headers=auth_headers(ops_token),
        json={"review_notes": "ops note"},
    )
    assert patch_ok.status_code == 200
    assert patch_ok.json()["review_notes"] == "ops note"

    get_settings.cache_clear()
