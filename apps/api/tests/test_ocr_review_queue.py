"""Queue / summary endpoints for human OCR review (P31-14)."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    CoverImageOcrCandidate,
    CoverImageOcrReconciliationWarning,
    CoverImageOcrResult,
    InventoryCopy,
    MetadataAudit,
)
from tests.test_cover_image_ocr_reconciliation_warnings import (
    auth_headers,
    make_png_bytes,
    register_and_login,
    _inventory_copy_id_for_new_order,
    _upload_inventory_cover,
    _bootstrap_cover_candidates,
)


def test_ocr_review_queue_requires_auth(client: TestClient) -> None:
    assert client.get("/ocr-review-queue").status_code == 401


def test_ocr_review_summary_requires_auth(client: TestClient) -> None:
    assert client.get("/ocr-review-summary").status_code == 401


def test_bulk_warning_ack_requires_auth(client: TestClient) -> None:
    assert (
        client.post(
            "/ocr-review/bulk/reconciliation-warnings/acknowledge",
            json={"ids": [1]},
        ).status_code
        == 401
    )


def test_ocr_review_queue_candidate_order_high_confidence_first(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    from tests.test_cover_image_ocr_reconciliation_warnings import _stub_ocr_enqueue
    from app.tasks.jobs import run_cover_image_ocr_job, run_cover_image_process_job

    monkeypatch.delenv("OPS_ADMIN_EMAILS", raising=False)

    suffix = "qorder"
    token = register_and_login(client, f"ocr-q-{suffix}@example.com")
    inv_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inv_id, make_png_bytes())

    inv_row = session.get(InventoryCopy, inv_id)
    assert inv_row is not None and inv_row.user_id is not None

    run_cover_image_process_job(cover_id, inv_row.user_id)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr(
        "app.services.cover_images._run_tesseract_ocr_on_cover_path",
        lambda path: "title text",
    )
    monkeypatch.setattr(
        "app.services.cover_images.get_tesseract_engine_version",
        lambda: "tesseract-q",
    )
    enq = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enq.status_code == 202
    ocr_id = enq.json()["ocr_result_id"]
    run_cover_image_ocr_job(cover_id, inv_row.user_id, ocr_id)

    for stale in session.exec(
        select(CoverImageOcrCandidate).where(CoverImageOcrCandidate.cover_image_id == cover_id)
    ).all():
        session.delete(stale)
    session.commit()

    latest_ocr = session.exec(
        select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id == cover_id).order_by(
            CoverImageOcrResult.id.desc()
        )
    ).first()
    assert latest_ocr and latest_ocr.id is not None

    cand_low = CoverImageOcrCandidate(
        cover_image_id=cover_id,
        ocr_result_id=latest_ocr.id,
        candidate_type="title",
        raw_candidate_text="Low",
        normalized_candidate_text=None,
        confidence_score=0.2,
        extraction_source="full_cover",
        extraction_version="extract-v-test",
        review_status="pending",
    )
    cand_high = CoverImageOcrCandidate(
        cover_image_id=cover_id,
        ocr_result_id=latest_ocr.id,
        candidate_type="title",
        raw_candidate_text="High",
        normalized_candidate_text=None,
        confidence_score=0.94,
        extraction_source="full_cover",
        extraction_version="extract-v-test",
        review_status="pending",
    )
    session.add_all([cand_low, cand_high])
    session.commit()
    session.refresh(cand_low)
    session.refresh(cand_high)

    q = client.get(
        "/ocr-review-queue",
        headers=auth_headers(token),
        params={"item_kind": "ocr_candidate", "queue_scope": "all"},
    )
    assert q.status_code == 200, q.text
    body = q.json()
    items = body["items"]
    ocr_items = [i for i in items if i["item_kind"] == "ocr_candidate"]
    entity_order = [i["entity_id"] for i in ocr_items]
    assert cand_high.id in entity_order and cand_low.id in entity_order
    assert entity_order.index(cand_high.id) < entity_order.index(cand_low.id)


def test_ocr_review_pagination_stable_total(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="X",
        suffix="pager",
    )
    inv = session.get(InventoryCopy, inv_id)
    assert inv is not None and inv.id is not None

    warns = session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(CoverImageOcrReconciliationWarning.cover_image_id == cover_id)
        .where(CoverImageOcrReconciliationWarning.status == "open")
    ).all()

    ids = sorted({row.id for row in warns if row.id is not None})
    if len(ids) < 5:
        for i in range(5 - len(ids)):
            session.add(
                CoverImageOcrReconciliationWarning(
                    cover_image_id=cover_id,
                    inventory_copy_id=int(inv.id),
                    ocr_candidate_id=None,
                    warning_type="missing_metadata",
                    severity="warning",
                    current_metadata_value=None,
                    candidate_value=None,
                    message=f"w-extra-{i}",
                    status="open",
                )
            )
        session.commit()

    p1 = client.get(
        "/ocr-review-queue",
        headers=auth_headers(token),
        params={
            "item_kind": "reconciliation_warning",
            "queue_scope": "all",
            "page": 1,
            "page_size": 2,
        },
    )
    p2 = client.get(
        "/ocr-review-queue",
        headers=auth_headers(token),
        params={
            "item_kind": "reconciliation_warning",
            "queue_scope": "all",
            "page": 2,
            "page_size": 2,
        },
    )
    assert p1.status_code == 200 and p2.status_code == 200
    assert p1.json()["total"] == p2.json()["total"]
    ids1 = {x["entity_id"] for x in p1.json()["items"]}
    ids2 = {x["entity_id"] for x in p2.json()["items"]}
    assert len(ids1) == 2 and len(ids2) == 2
    assert not ids1.intersection(ids2)


def test_bulk_warning_ack_skips_and_audit_increases(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token, _inv_id, cover_id = _bootstrap_cover_candidates(
        client,
        session,
        monkeypatch,
        raw_text="title line",
        suffix="bulk",
    )

    warns = session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(CoverImageOcrReconciliationWarning.cover_image_id == cover_id)
        .where(CoverImageOcrReconciliationWarning.status == "open")
    ).all()
    if not warns:
        session.add(
            CoverImageOcrReconciliationWarning(
                cover_image_id=cover_id,
                inventory_copy_id=_inv_id,
                ocr_candidate_id=None,
                warning_type="missing_metadata",
                severity="warning",
                current_metadata_value=None,
                candidate_value=None,
                message="ensure-open-warning",
                status="open",
            )
        )
        session.commit()
        warns = session.exec(
            select(CoverImageOcrReconciliationWarning)
            .where(CoverImageOcrReconciliationWarning.cover_image_id == cover_id)
            .where(CoverImageOcrReconciliationWarning.status == "open")
        ).all()
    wid = warns[0].id
    assert wid is not None

    before_audits = len(session.exec(select(MetadataAudit)).all())

    r1 = client.post(
        "/ocr-review/bulk/reconciliation-warnings/acknowledge",
        headers=auth_headers(token),
        json={"ids": [wid]},
    )
    assert r1.status_code == 200
    assert wid in r1.json()["succeeded"]

    r2 = client.post(
        "/ocr-review/bulk/reconciliation-warnings/acknowledge",
        headers=auth_headers(token),
        json={"ids": [wid]},
    )
    assert r2.status_code == 200
    assert str(wid) in r2.json()["skipped"]

    after_audits = len(session.exec(select(MetadataAudit)).all())
    assert after_audits > before_audits


def test_ops_review_queue_blocked_without_admin(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-block@example.com")
    monkeypatch.setenv("APP_ENV", "production")

    monkeypatch.delenv("DEBUG_RUNTIME", raising=False)
    get_settings.cache_clear()
    client.post("/auth/register", json={"email": "nocover@example.com", "password": "supersecret123"})
    blocked = client.get(
        "/ops/ocr-review-queue",
        headers=auth_headers(
            client.post("/auth/login", json={"email": "nocover@example.com", "password": "supersecret123"}).json()[
                "access_token"
            ]
        ),
    )
    assert blocked.status_code == 403


def test_ops_review_queue_ok_for_configured_admin(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-ok-queue@example.com")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DEBUG_RUNTIME", raising=False)
    get_settings.cache_clear()
    mail = "ops-ok-queue@example.com"
    token = register_and_login(client, mail)
    r = client.get("/ops/ocr-review-queue", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "items" in body
