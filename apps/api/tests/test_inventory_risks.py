from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

import test_cover_image_match_candidates as mcc
import test_inventory as inv
import test_relationship_conflicts as rc
import test_run_detection as run_det
from app.models import CoverImage, CoverImageMatchCandidate, CoverImageOcrResult, CoverRelationshipConflict, DuplicateCandidateReview, InventoryCopy


def _insert_failed_ocr_result(session: Session, *, cover_image_id: int) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        CoverImageOcrResult(
            cover_image_id=cover_image_id,
            ocr_engine="tesseract",
            ocr_engine_version="test-risk-v1",
            processing_status="failed",
            raw_text="",
            normalized_text=None,
            confidence_score=None,
            processing_error="synthetic failure",
            processed_at=now,
            created_at=now,
        )
    )
    session.commit()


def _find_inventory_row(client: TestClient, token: str, *, title: str, issue_number: str) -> dict:
    listing = client.get("/inventory?page=1&page_size=100", headers=inv.auth_headers(token))
    assert listing.status_code == 200
    return next(
        row
        for row in listing.json()["items"]
        if row["title"] == title and row["issue_number"] == issue_number
    )


def test_inventory_risk_surface_covers_categories_and_filters(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "risk-user@example.com")

    # Risk source with cover-processing / OCR / canonical / conflict / match / quality signals.
    source_inventory_id, source_cover_id = rc._create_cover(
        client,
        token,
        title="Risk Source",
        issue_number="1",
        color=(30, 120, 200),
    )
    candidate_inventory_id, candidate_cover_id = rc._create_cover(
        client,
        token,
        title="Risk Candidate",
        issue_number="1",
        color=(50, 140, 220),
    )

    source_cover = session.get(CoverImage, source_cover_id)
    assert source_cover is not None
    source_cover.processing_status = "failed"
    session.commit()

    run_det.add_pending_canonical_suggestion(session, inventory_copy_id=source_inventory_id)
    mcc._insert_quality_penalty(session, cover_image_id=source_cover_id, severity="warning")
    _insert_failed_ocr_result(session, cover_image_id=source_cover_id)

    match_candidate = CoverImageMatchCandidate(
        source_cover_image_id=source_cover_id,
        candidate_cover_image_id=candidate_cover_id,
        candidate_type="combined_similarity",
        confidence_bucket="very_high",
        deterministic_score=0.97,
        normalized_confidence_score=0.97,
        confidence_version="risk-test-v1",
        extraction_version="risk-test-v1",
        ranking_score=0.91,
        ranking_version="risk-test-v1",
        grouping_type="probable_variant_family",
        grouping_key="risk-match-1",
        matched_signals={"signal": "seed"},
        hard_match_flags_json={},
        weak_signal_flags_json={},
        ranking_reason_json={},
    )
    session.add(match_candidate)
    session.commit()
    session.refresh(match_candidate)

    session.add(
        CoverRelationshipConflict(
            conflict_type="canonical_suggestion_mismatch",
            severity="critical",
            source_cover_image_id=source_cover_id,
            related_cover_image_id=candidate_cover_id,
            link_decision_id=None,
            match_candidate_id=match_candidate.id,
            canonical_issue_suggestion_id=None,
            conflict_key="risk-test-conflict",
            status="open",
            evidence_json={"signals": ["risk-test"]},
        )
    )
    session.commit()

    # Basic state-only signals.
    _preorder_inventory_id, _ = rc._create_cover(
        client,
        token,
        title="Preorder Gap",
        issue_number="1",
        color=(80, 80, 180),
        order_status="preordered",
    )

    assert client.post(
        "/orders",
        json={
            "retailer": "Whatnot",
            "order_date": "2026-05-19",
            "source_type": "manual",
            "shipping_amount": 0,
            "tax_amount": 0,
            "items": [
                {
                    "title": "Released Not Received",
                    "publisher": "Image",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 4.99,
                    "release_status": "released",
                    "order_status": "ordered",
                }
            ],
        },
        headers=inv.auth_headers(token),
    ).status_code == 201

    assert client.post(
        "/orders",
        json={
            "retailer": "Whatnot",
            "order_date": "2026-05-19",
            "source_type": "manual",
            "shipping_amount": 0,
            "tax_amount": 0,
            "items": [
                {
                    "title": "Duplicate Case",
                    "publisher": "Image",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 2,
                    "raw_item_price": 4.99,
                }
            ],
        },
        headers=inv.auth_headers(token),
    ).status_code == 201

    assert client.post(
        "/orders",
        json={
            "retailer": "Whatnot",
            "order_date": "2026-05-19",
            "source_type": "manual",
            "shipping_amount": 0,
            "tax_amount": 0,
            "items": [
                {
                    "title": "Run Gap",
                    "publisher": "Image",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 4.99,
                },
                {
                    "title": "Run Gap",
                    "publisher": "Image",
                    "issue_number": "3",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 4.99,
                },
            ],
        },
        headers=inv.auth_headers(token),
    ).status_code == 201

    duplicate_row = _find_inventory_row(client, token, title="Duplicate Case", issue_number="1")
    duplicate_copy = session.get(InventoryCopy, duplicate_row["inventory_copy_id"])
    assert duplicate_copy is not None
    session.add(
        DuplicateCandidateReview(
            metadata_identity_key=duplicate_copy.metadata_identity_key,
            review_status="pending",
        )
    )
    session.commit()

    risks_response = client.get("/inventory-risks", headers=inv.auth_headers(token))
    assert risks_response.status_code == 200
    risks_payload = risks_response.json()
    risk_types = {risk["risk_type"] for risk in risks_payload["risks"]}
    assert {
        "needs_canonical_review",
        "needs_conflict_review",
        "needs_scan",
        "needs_ocr_retry",
        "needs_cover_processing_review",
        "preorder_missing_release_date",
        "released_not_received",
        "duplicate_uncertainty",
        "run_gap_detected",
        "low_quality_scan",
        "high_confidence_match_unreviewed",
    }.issubset(risk_types)
    assert risks_payload["summary"]["critical_copies"] >= 1
    assert risks_payload["summary"]["high_copies"] >= 1
    assert risks_payload["summary"]["medium_copies"] >= 1
    assert risks_payload["summary"]["low_copies"] >= 1

    detail_response = client.get(f"/inventory/{source_inventory_id}/risks", headers=inv.auth_headers(token))
    assert detail_response.status_code == 200
    detail_types = {risk["risk_type"] for risk in detail_response.json()["risks"]}
    assert {
        "needs_canonical_review",
        "needs_conflict_review",
        "needs_ocr_retry",
        "needs_cover_processing_review",
        "high_confidence_match_unreviewed",
        "low_quality_scan",
    }.issubset(detail_types)

    filtered_inventory = client.get(
        "/inventory?page=1&page_size=100&needs_attention=true",
        headers=inv.auth_headers(token),
    )
    assert filtered_inventory.status_code == 200
    filtered_payload = filtered_inventory.json()
    assert filtered_payload["total"] < client.get("/inventory?page=1&page_size=100", headers=inv.auth_headers(token)).json()["total"]
    assert all(
        any(risk["priority"] in {"critical", "high"} for risk in row.get("inventory_risks", []))
        for row in filtered_payload["items"]
    )


def test_inventory_risk_endpoints_do_not_mutate_inventory(client: TestClient) -> None:
    token = inv.register_and_login(client, "risk-idempotent@example.com")
    assert client.post(
        "/orders",
        json={
            "retailer": "Whatnot",
            "order_date": "2026-05-19",
            "source_type": "manual",
            "shipping_amount": 0,
            "tax_amount": 0,
            "items": [
                {
                    "title": "Idempotent",
                    "publisher": "Image",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": 4.99,
                }
            ],
        },
        headers=inv.auth_headers(token),
    ).status_code == 201

    before = client.get("/inventory/summary", headers=inv.auth_headers(token)).json()
    assert client.get("/inventory-risks", headers=inv.auth_headers(token)).status_code == 200
    assert client.get("/inventory-risks/summary", headers=inv.auth_headers(token)).status_code == 200
    assert client.get("/inventory?page=1&page_size=10&needs_attention=true", headers=inv.auth_headers(token)).status_code == 200
    after = client.get("/inventory/summary", headers=inv.auth_headers(token)).json()

    assert before == after


def test_ops_inventory_risk_endpoints_require_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    user_token = inv.register_and_login(client, "risk-user@example.com")
    ops_token = inv.register_and_login(client, "ops@example.com")

    denied = client.get("/ops/inventory-risks", headers=inv.auth_headers(user_token))
    assert denied.status_code == 403

    allowed = client.get("/ops/inventory-risks", headers=inv.auth_headers(ops_token))
    assert allowed.status_code == 200
    assert "summary" in allowed.json()
