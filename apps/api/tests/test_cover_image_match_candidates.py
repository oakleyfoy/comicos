from datetime import datetime, timezone
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import (
    CoverImage,
    CoverImageFingerprint,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    CoverImageOcrQualityAnalysis,
    CoverImageOcrReconciliationWarning,
    InventoryCopy,
    MetadataAudit,
)
from app.services.cover_images import (
    _bucket_for_match_score,
    FINGERPRINT_EXTRACTION_VERSION,
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
) -> tuple[int, int]:
    inv_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inv_id, image_bytes)
    inv_row = session.get(InventoryCopy, inv_id)
    assert inv_row is not None
    run_cover_image_process_job(cover_id, inv_row.user_id)
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: raw_text)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract-match")
    enq = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enq.status_code == 202
    ocr_result_id = enq.json()["ocr_result_id"]
    assert ocr_result_id is not None
    run_cover_image_ocr_job(cover_id, inv_row.user_id, ocr_result_id)
    return inv_id, cover_id


def _prepare_cover_signals(client: TestClient, token: str, cover_id: int) -> None:
    headers = auth_headers(token)
    assert client.post(f"/cover-images/{cover_id}/extract-barcodes", headers=headers).status_code == 200
    assert client.post(f"/cover-images/{cover_id}/generate-fingerprints", headers=headers).status_code == 200


def _candidate_by_type(payload: dict, candidate_type: str) -> dict:
    return next(row for row in payload["candidates"] if row["candidate_type"] == candidate_type)


def _insert_quality_penalty(
    session: Session,
    *,
    cover_image_id: int,
    quality_type: str = "unreadable_ocr",
    severity: str = "critical",
) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        CoverImageOcrQualityAnalysis(
            cover_image_id=cover_image_id,
            source_ocr_result_id=None,
            quality_type=quality_type,
            deterministic_score=0.05,
            severity=severity,
            detail_json={"seed": "test"},
            extraction_version="test-confidence-quality-v1",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()


def _insert_open_warning(
    session: Session,
    *,
    cover_image_id: int,
    warning_type: str = "title_mismatch",
    severity: str = "critical",
    message: str = "Deterministic warning for test coverage.",
) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        CoverImageOcrReconciliationWarning(
            cover_image_id=cover_image_id,
            inventory_copy_id=None,
            ocr_candidate_id=None,
            warning_type=warning_type,
            severity=severity,
            current_metadata_value="Invincible",
            candidate_value="Invincible",
            message=message,
            status="open",
            created_at=now,
            resolved_at=None,
            resolved_by_user_id=None,
        )
    )
    session.commit()


def _overwrite_fingerprints_max_hamming(
    session: Session,
    *,
    source_cover_id: int,
    target_cover_id: int,
    now: datetime,
) -> None:
    """Force maximally opposing pHashes so perceptual-hash similarity stays below grouping thresholds."""

    rows = session.exec(
        select(CoverImageFingerprint).where(
            CoverImageFingerprint.cover_image_id.in_((source_cover_id, target_cover_id))
        )
    ).all()
    for row in rows:
        session.delete(row)
    session.commit()
    payloads = (
        (
            source_cover_id,
            "0" * 16,
            "a" * 64,
        ),
        (
            target_cover_id,
            "f" * 16,
            "b" * 64,
        ),
    )
    for cover_image_id, fp_value, image_sha256 in payloads:
        session.add(
            CoverImageFingerprint(
                cover_image_id=cover_image_id,
                fingerprint_type="phash",
                fingerprint_value=fp_value,
                derivative_type="medium",
                image_width=1400,
                image_height=900,
                image_sha256=image_sha256,
                extraction_version=FINGERPRINT_EXTRACTION_VERSION,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()


def test_cover_match_candidates_prevent_self_match(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-self@example.com")
    _inv_id, cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(),
        raw_text="INVINCIBLE #1 IMAGE UPC 123456789012",
    )
    _prepare_cover_signals(client, token, cover_id)

    response = client.post(
        f"/cover-images/{cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["candidate_count"] == 0


def test_cover_match_candidates_generate_deterministically_from_barcode_fingerprint_and_ocr(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-signals@example.com")
    shared_image = make_png_bytes(color=(80, 40, 120))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _prepare_cover_signals(client, token, source_cover_id)
    _prepare_cover_signals(client, token, target_cover_id)

    headers = auth_headers(token)
    before_inv = session.get(InventoryCopy, source_inv_id)
    before_cover = session.get(CoverImage, source_cover_id)
    assert before_inv is not None and before_cover is not None

    first = client.post(f"/cover-images/{source_cover_id}/generate-match-candidates", headers=headers)
    assert first.status_code == 200
    first_payload = first.json()
    by_type = {row["candidate_type"]: row for row in first_payload["candidates"]}
    assert set(by_type) == {
        "barcode_similarity",
        "fingerprint_similarity",
        "ocr_similarity",
        "combined_similarity",
    }
    assert by_type["barcode_similarity"]["candidate_cover_image_id"] == target_cover_id
    assert by_type["barcode_similarity"]["deterministic_score"] == 0.72
    assert by_type["barcode_similarity"]["normalized_confidence_score"] == 0.72
    assert by_type["barcode_similarity"]["confidence_bucket"] == "high"
    assert by_type["barcode_similarity"]["matched_signal_count"] == 1
    assert by_type["barcode_similarity"]["hard_match_flags_json"]["barcode_exact_match"] == [
        "123456789012"
    ]
    assert by_type["fingerprint_similarity"]["deterministic_score"] == 0.38
    assert by_type["fingerprint_similarity"]["normalized_confidence_score"] == 0.38
    assert by_type["fingerprint_similarity"]["confidence_bucket"] == "low"
    assert by_type["ocr_similarity"]["deterministic_score"] == 0.48
    assert by_type["ocr_similarity"]["normalized_confidence_score"] == 0.48
    assert by_type["ocr_similarity"]["confidence_bucket"] == "medium"
    assert by_type["combined_similarity"]["deterministic_score"] == 1.58
    assert by_type["combined_similarity"]["normalized_confidence_score"] == 1.0
    assert by_type["combined_similarity"]["confidence_bucket"] == "very_high"
    assert by_type["combined_similarity"]["confidence_explanation_summary"].startswith("Signals:")
    assert by_type["combined_similarity"]["contributing_signals"]
    assert by_type["combined_similarity"]["penalties"] == []
    assert by_type["combined_similarity"]["candidate_rank"] == 1
    assert by_type["barcode_similarity"]["candidate_rank"] == 2
    assert by_type["ocr_similarity"]["candidate_rank"] == 3
    assert by_type["fingerprint_similarity"]["candidate_rank"] == 4
    assert by_type["combined_similarity"]["ranking_version"] == "cover-match-ranking-v1"
    assert by_type["combined_similarity"]["grouping_type"] == "probable_duplicate_scan"
    assert by_type["combined_similarity"]["grouping_confidence_bucket"] == "very_high"
    assert by_type["combined_similarity"]["grouping_key"].startswith("probable_duplicate_scan:")
    assert "duplicate" in by_type["combined_similarity"]["grouping_reason_summary"].lower()
    grp_meta = by_type["combined_similarity"]["ranking_reason_json"]["grouping"]
    assert grp_meta is not None
    assert any(
        isinstance(sig, dict)
        and isinstance(sig.get("value"), dict)
        and sig["value"].get("quantized_slices")
        for sig in grp_meta.get("signals") or []
    )
    assert "ranking_explanation_summary" in by_type["combined_similarity"]["ranking_reason_json"]
    assert "conflicting_signals" in by_type["combined_similarity"]["ranking_reason_json"]
    assert "missing_signals" in by_type["combined_similarity"]["ranking_reason_json"]

    group_response = client.get(
        f"/match-groups/{by_type['combined_similarity']['grouping_key']}",
        headers=headers,
    )
    assert group_response.status_code == 200
    group_payload = group_response.json()
    assert group_payload["grouping_type"] == "probable_duplicate_scan"
    assert group_payload["candidate_count"] >= 1
    assert group_payload["candidates"][0]["candidate_rank"] == 1

    second = client.post(f"/cover-images/{source_cover_id}/generate-match-candidates", headers=headers)
    assert second.status_code == 200
    second_by_type = {row["candidate_type"]: row for row in second.json()["candidates"]}
    assert {
        candidate_type: (
            row["id"],
            row["deterministic_score"],
            row["normalized_confidence_score"],
            row["confidence_bucket"],
            row["confidence_explanation_summary"],
            row["candidate_rank"],
            row["grouping_key"],
            row["grouping_type"],
        )
        for candidate_type, row in second_by_type.items()
    } == {
        candidate_type: (
            row["id"],
            row["deterministic_score"],
            row["normalized_confidence_score"],
            row["confidence_bucket"],
            row["confidence_explanation_summary"],
            row["candidate_rank"],
            row["grouping_key"],
            row["grouping_type"],
        )
        for candidate_type, row in by_type.items()
    }

    rows = session.exec(
        select(CoverImageMatchCandidate)
        .where(CoverImageMatchCandidate.source_cover_image_id == source_cover_id)
        .order_by(CoverImageMatchCandidate.id.asc())
    ).all()
    assert len(rows) == 4

    session.expire_all()
    inv_after = session.get(InventoryCopy, source_inv_id)
    cover_after = session.get(CoverImage, source_cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_match_candidate")
    ).all()
    actions = {a.action for a in audits}
    assert "cover_match_candidate_confidence_generated" in actions


def test_cover_match_candidates_acknowledge_and_dismiss_persist_with_audits(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-review@example.com")
    shared_image = make_png_bytes(color=(120, 90, 20))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _prepare_cover_signals(client, token, source_cover_id)
    _prepare_cover_signals(client, token, target_cover_id)
    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert generated.status_code == 200
    by_type = {row["candidate_type"]: row for row in generated.json()["candidates"]}

    ack = client.patch(
        f"/match-candidates/{by_type['barcode_similarity']['id']}/acknowledge",
        headers=auth_headers(token),
    )
    dismiss = client.patch(
        f"/match-candidates/{by_type['ocr_similarity']['id']}/dismiss",
        headers=auth_headers(token),
    )
    assert ack.status_code == 200
    assert dismiss.status_code == 200
    assert ack.json()["acknowledged_at"] is not None
    assert dismiss.json()["dismissed_at"] is not None

    session.expire_all()
    ack_row = session.get(CoverImageMatchCandidate, by_type["barcode_similarity"]["id"])
    dismiss_row = session.get(CoverImageMatchCandidate, by_type["ocr_similarity"]["id"])
    assert ack_row is not None and dismiss_row is not None
    assert ack_row.acknowledged_at is not None
    assert dismiss_row.dismissed_at is not None

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_match_candidate")
    ).all()
    actions = {audit.action for audit in audits}
    assert "cover_match_candidate_acknowledged" in actions
    assert "cover_match_candidate_dismissed" in actions


def test_cover_match_candidates_fingerprint_only_path_generates_low_bucket(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-fingerprint-only@example.com")
    shared_image = make_png_bytes(color=(10, 150, 80))
    source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text="",
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text="",
    )
    headers = auth_headers(token)
    assert client.post(f"/cover-images/{source_cover_id}/generate-fingerprints", headers=headers).status_code == 200
    assert client.post(f"/cover-images/{target_cover_id}/generate-fingerprints", headers=headers).status_code == 200

    response = client.post(f"/cover-images/{source_cover_id}/generate-match-candidates", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] == 1
    candidate = payload["candidates"][0]
    assert candidate["candidate_type"] == "fingerprint_similarity"
    assert candidate["candidate_cover_image_id"] == target_cover_id
    assert candidate["confidence_bucket"] == "low"
    assert candidate["deterministic_score"] == 0.38
    assert candidate["normalized_confidence_score"] == 0.38

    detail = client.get(f"/inventory/{source_inv_id}", headers=headers)
    assert detail.status_code == 200
    cover_payload = next(item for item in detail.json()["cover_images"] if item["id"] == source_cover_id)
    assert len(cover_payload["match_candidates"]) == 1


def test_cover_match_candidates_ocr_only_path_generates_medium_confidence(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-ocr-only@example.com")
    source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(10, 30, 90)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(200, 10, 20)),
        raw_text="INVINCIBLE #1 IMAGE",
    )

    response = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] == 1
    candidate = _candidate_by_type(payload, "ocr_similarity")
    assert candidate["candidate_cover_image_id"] == target_cover_id
    assert candidate["confidence_bucket"] == "medium"
    assert candidate["deterministic_score"] == 0.48
    assert candidate["normalized_confidence_score"] == 0.48
    assert candidate["candidate_rank"] == 1
    assert candidate["matched_fields"] == ["issue_number", "publisher", "title"]
    assert "Exact OCR title match" in candidate["confidence_explanation_summary"]
    assert candidate["grouping_type"] == "probable_same_issue"
    assert candidate["grouping_key"].startswith("probable_same_issue:")
    assert candidate["grouping_confidence_bucket"] == "medium"
    assert "same issue" in candidate["grouping_reason_summary"].lower()
    biblio_key_first = candidate["grouping_key"]
    rerun = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert rerun.status_code == 200
    biblio_key_second = _candidate_by_type(rerun.json(), "ocr_similarity")["grouping_key"]
    assert biblio_key_first == biblio_key_second

    detail = client.get(f"/inventory/{source_inv_id}", headers=auth_headers(token))
    assert detail.status_code == 200


def test_cover_match_candidates_apply_ocr_quality_penalty(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-quality-penalty@example.com")
    source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(40, 100, 140)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    _target_inv_id, _target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(180, 20, 40)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    _insert_quality_penalty(session, cover_image_id=source_cover_id)

    response = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    candidate = _candidate_by_type(response.json(), "ocr_similarity")
    assert candidate["deterministic_score"] == 0.48
    assert candidate["normalized_confidence_score"] == 0.26
    assert candidate["confidence_bucket"] == "low"
    assert any("quality penalty" in str(item["label"]).lower() for item in candidate["penalties"])

    detail = client.get(f"/inventory/{source_inv_id}", headers=auth_headers(token))
    assert detail.status_code == 200


def test_cover_match_candidates_warning_penalty_regresses_and_improves_confidence(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-warning-penalty@example.com")
    _source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(30, 80, 120)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    _target_inv_id, _target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(120, 40, 30)),
        raw_text="INVINCIBLE #1 IMAGE",
    )

    initial = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert initial.status_code == 200
    baseline = _candidate_by_type(initial.json(), "ocr_similarity")
    assert baseline["normalized_confidence_score"] == 0.48

    _insert_open_warning(
        session,
        cover_image_id=source_cover_id,
        warning_type="title_mismatch",
        severity="critical",
        message="Conflicting OCR title warning.",
    )
    regressed = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert regressed.status_code == 200
    regressed_candidate = _candidate_by_type(regressed.json(), "ocr_similarity")
    assert regressed_candidate["normalized_confidence_score"] == 0.32
    assert regressed_candidate["confidence_bucket"] == "low"

    warning = session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(CoverImageOcrReconciliationWarning.cover_image_id == source_cover_id)
        .order_by(CoverImageOcrReconciliationWarning.id.desc())
    ).first()
    assert warning is not None
    warning.status = "dismissed"
    warning.resolved_at = datetime.now(timezone.utc)
    session.add(warning)
    session.commit()

    improved = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert improved.status_code == 200
    improved_candidate = _candidate_by_type(improved.json(), "ocr_similarity")
    assert improved_candidate["normalized_confidence_score"] == 0.48
    assert improved_candidate["confidence_bucket"] == "medium"

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_match_candidate")
    ).all()
    actions = {audit.action for audit in audits}
    assert "cover_match_candidate_confidence_regressed" in actions
    assert "cover_match_candidate_confidence_improved" in actions


def test_cover_match_candidates_shared_barcode_divergent_fingerprint_rules_out_duplicate_scan(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    """Barcode-only agreement must not classify as probable_duplicate_scan without strong fingerprints."""
    token = register_and_login(client, "match-upc-weakfp@example.com")
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(20, 140, 60)),
        raw_text=shared_text,
    )
    _, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(220, 30, 200)),
        raw_text=shared_text,
    )
    headers = auth_headers(token)
    _prepare_cover_signals(client, token, source_cover_id)
    _prepare_cover_signals(client, token, target_cover_id)

    session.expire_all()
    _overwrite_fingerprints_max_hamming(
        session,
        source_cover_id=source_cover_id,
        target_cover_id=target_cover_id,
        now=datetime.now(timezone.utc),
    )

    before_inv = session.get(InventoryCopy, _source_inv_id)
    before_cover = session.get(CoverImage, source_cover_id)
    assert before_inv is not None and before_cover is not None

    response = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=headers,
    )
    assert response.status_code == 200
    candidates = response.json()["candidates"]
    payload = response.json()
    combined = _candidate_by_type(payload, "combined_similarity")
    assert combined["candidate_cover_image_id"] == target_cover_id
    assert combined["grouping_type"] == "probable_same_issue"
    assert combined["grouping_key"].startswith("probable_same_issue:")

    barcode_row = _candidate_by_type(payload, "barcode_similarity")
    assert barcode_row["grouping_type"] != "probable_duplicate_scan"

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_match_candidate")
    ).all()
    actions = {a.action for a in audits}
    assert "cover_match_candidate_confidence_generated" in actions

    session.expire_all()
    inv_after = session.get(InventoryCopy, _source_inv_id)
    cover_after = session.get(CoverImage, source_cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash

    assert len(candidates) >= 1


def test_cover_match_candidates_group_probable_variant_family_deterministically(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "match-variant-family@example.com")
    _source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(15, 60, 120)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(220, 180, 20)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    now = datetime.now(timezone.utc)
    session.add(
        CoverImageFingerprint(
            cover_image_id=source_cover_id,
            fingerprint_type="phash",
            fingerprint_value="0000000000000000",
            derivative_type="medium",
            image_width=1400,
            image_height=900,
            image_sha256="0" * 64,
            extraction_version="test-variant-family-v1",
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        CoverImageFingerprint(
            cover_image_id=target_cover_id,
            fingerprint_type="phash",
            fingerprint_value="fff0000000000000",
            derivative_type="medium",
            image_width=1400,
            image_height=900,
            image_sha256="f" * 64,
            extraction_version="test-variant-family-v1",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    response = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    candidate = _candidate_by_type(response.json(), "combined_similarity")
    assert candidate["grouping_type"] == "probable_variant_family"
    assert candidate["grouping_key"].startswith("probable_variant_family:")
    assert candidate["grouping_confidence_bucket"] in {"medium", "high"}
    assert "variant family" in candidate["grouping_reason_summary"].lower()
    assert "barcode_exact_match" in candidate["ranking_reason_json"]["missing_signals"]


def test_cover_link_decision_create_approved_link_persists_without_metadata_mutation(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-link-approved@example.com")
    shared_image = make_png_bytes(color=(70, 50, 160))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _prepare_cover_signals(client, token, source_cover_id)
    _prepare_cover_signals(client, token, target_cover_id)

    headers = auth_headers(token)
    before_inv = session.get(InventoryCopy, source_inv_id)
    before_cover = session.get(CoverImage, source_cover_id)
    assert before_inv is not None and before_cover is not None

    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=headers,
    )
    assert generated.status_code == 200
    combined = _candidate_by_type(generated.json(), "combined_similarity")
    assert combined["active_link_decision"] is None

    created = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "source_match_candidate_id": combined["id"],
            "decision_type": "approved_link",
            "relationship_type": "same_cover",
            "decision_reason": "Human-reviewed same cover link.",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["decision_type"] == "approved_link"
    assert payload["relationship_type"] == "same_cover"
    assert payload["decision_state"] == "active"
    assert payload["decision_source"] == "human"
    assert payload["source_match_candidate_id"] == combined["id"]

    session.expire_all()
    persisted = session.get(CoverImageLinkDecision, payload["id"])
    assert persisted is not None
    assert persisted.decision_state == "active"
    assert persisted.pair_key == f"{min(source_cover_id, target_cover_id)}:{max(source_cover_id, target_cover_id)}"

    refreshed = client.get(f"/inventory/{source_inv_id}", headers=headers)
    assert refreshed.status_code == 200
    cover_payload = next(item for item in refreshed.json()["cover_images"] if item["id"] == source_cover_id)
    refreshed_combined = _candidate_by_type(
        {"candidates": cover_payload["match_candidates"]},
        "combined_similarity",
    )
    assert refreshed_combined["active_link_decision"] is not None
    assert refreshed_combined["active_link_decision"]["id"] == payload["id"]
    assert refreshed_combined["active_link_decision"]["decision_type"] == "approved_link"

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_link_decision")
    ).all()
    actions = {audit.action for audit in audits}
    assert "cover_link_decision_created" in actions
    assert "cover_link_decision_approved" in actions

    session.expire_all()
    inv_after = session.get(InventoryCopy, source_inv_id)
    cover_after = session.get(CoverImage, source_cover_id)
    assert inv_after is not None and cover_after is not None
    assert inv_after.primary_cover_image_id == before_inv.primary_cover_image_id
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash


def test_cover_link_decision_rejected_unrelated_is_visible_on_match_candidates(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-link-rejected@example.com")
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(90, 20, 170)),
        raw_text=shared_text,
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=make_png_bytes(color=(90, 20, 170)),
        raw_text=shared_text,
    )
    _prepare_cover_signals(client, token, source_cover_id)
    _prepare_cover_signals(client, token, target_cover_id)

    headers = auth_headers(token)
    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=headers,
    )
    assert generated.status_code == 200
    combined = _candidate_by_type(generated.json(), "combined_similarity")
    assert combined["active_link_decision"] is None

    rejected = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "source_match_candidate_id": combined["id"],
            "decision_type": "rejected_link",
            "relationship_type": "unrelated",
            "decision_reason": "Reviewer marked these covers unrelated.",
        },
    )
    assert rejected.status_code == 200
    decision = rejected.json()
    assert decision["relationship_type"] == "unrelated"

    candidate_list = client.get(
        f"/cover-images/{source_cover_id}/match-candidates",
        headers=headers,
    )
    assert candidate_list.status_code == 200
    combined_after = _candidate_by_type({"candidates": candidate_list.json()}, "combined_similarity")
    assert combined_after["active_link_decision"] is not None
    assert combined_after["active_link_decision"]["decision_type"] == "rejected_link"
    assert combined_after["active_link_decision"]["relationship_type"] == "unrelated"

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_link_decision")
    ).all()
    actions = {audit.action for audit in audits}
    assert "cover_link_decision_created" in actions
    assert "cover_link_decision_rejected" in actions


def test_cover_link_decision_self_link_is_rejected_and_new_active_supersedes_old(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-link-supersede@example.com")
    shared_image = make_png_bytes(color=(40, 130, 140))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _prepare_cover_signals(client, token, source_cover_id)
    _prepare_cover_signals(client, token, target_cover_id)

    headers = auth_headers(token)
    self_link = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": source_cover_id,
            "decision_type": "approved_link",
            "relationship_type": "same_cover",
        },
    )
    assert self_link.status_code == 400

    first = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "decision_type": "needs_review",
            "relationship_type": "same_issue",
            "decision_reason": "Needs another set of eyes.",
        },
    )
    assert first.status_code == 200
    second = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "decision_type": "approved_link",
            "relationship_type": "same_cover",
            "decision_reason": "Confirmed same cover after manual review.",
        },
    )
    assert second.status_code == 200

    session.expire_all()
    first_row = session.get(CoverImageLinkDecision, first.json()["id"])
    second_row = session.get(CoverImageLinkDecision, second.json()["id"])
    assert first_row is not None and second_row is not None
    assert first_row.decision_state == "superseded"
    assert first_row.superseded_by_decision_id == second_row.id
    assert second_row.decision_state == "active"

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_link_decision")
    ).all()
    actions = {audit.action for audit in audits}
    assert "cover_link_decision_superseded" in actions
    assert "cover_link_decision_approved" in actions


def test_cover_link_decision_revert_clears_active_match_candidate_status(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-link-revert@example.com")
    shared_image = make_png_bytes(color=(110, 60, 80))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    source_inv_id, source_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _target_inv_id, target_cover_id = _bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=shared_image,
        raw_text=shared_text,
    )
    _prepare_cover_signals(client, token, source_cover_id)
    _prepare_cover_signals(client, token, target_cover_id)

    headers = auth_headers(token)
    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=headers,
    )
    assert generated.status_code == 200
    combined = _candidate_by_type(generated.json(), "combined_similarity")

    created = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "source_match_candidate_id": combined["id"],
            "decision_type": "approved_link",
            "relationship_type": "duplicate_scan",
        },
    )
    assert created.status_code == 200

    reverted = client.post(
        f"/cover-link-decisions/{created.json()['id']}/revert",
        headers=headers,
    )
    assert reverted.status_code == 200
    assert reverted.json()["decision_state"] == "reverted"
    assert reverted.json()["reverted_at"] is not None

    session.expire_all()
    row = session.get(CoverImageLinkDecision, created.json()["id"])
    assert row is not None
    assert row.decision_state == "reverted"

    refreshed = client.get(f"/inventory/{source_inv_id}", headers=headers)
    assert refreshed.status_code == 200
    cover_payload = next(item for item in refreshed.json()["cover_images"] if item["id"] == source_cover_id)
    combined_after = _candidate_by_type({"candidates": cover_payload["match_candidates"]}, "combined_similarity")
    assert combined_after["active_link_decision"] is None

    audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "cover_link_decision")
    ).all()
    actions = {audit.action for audit in audits}
    assert "cover_link_decision_reverted" in actions


def test_match_candidate_confidence_thresholds_are_stable() -> None:
    assert _bucket_for_match_score(0.9) == "very_high"
    assert _bucket_for_match_score(0.72) == "high"
    assert _bucket_for_match_score(0.45) == "medium"
    assert _bucket_for_match_score(0.2) == "low"
    assert _bucket_for_match_score(0.1999) == "very_low"
