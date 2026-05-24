from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

import test_cover_image_match_candidates as mcc
import test_inventory as inv
from app.models import (
    CanonicalIssueLinkSuggestion,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    CoverImageOcrReconciliationWarning,
    CoverRelationshipConflict,
    InventoryCopy,
)
from app.services.cover_link_decisions import cover_link_pair_key


def _create_cover(
    client: TestClient,
    token: str,
    *,
    title: str,
    issue_number: str,
    publisher: str = "Image",
    release_date: str | None = None,
    order_status: str | None = None,
    received_at: str | None = None,
    color: tuple[int, int, int] = (30, 120, 200),
) -> tuple[int, int]:
    payload = {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
        "items": [
            {
                "title": title,
                "publisher": publisher,
                "issue_number": issue_number,
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "release_date": release_date,
                "order_status": order_status,
                "received_at": received_at,
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    }
    created = client.post("/orders", json=payload, headers=inv.auth_headers(token))
    assert created.status_code == 201
    order_detail = client.get(
        f"/orders/{created.json()['order_id']}",
        headers=inv.auth_headers(token),
    )
    assert order_detail.status_code == 200
    inventory_copy_id = order_detail.json()["items"][0]["inventory_copy_ids"][0]
    cover_id = mcc._upload_inventory_cover(
        client,
        token,
        inventory_copy_id,
        mcc.make_png_bytes(color=color),
    )
    return inventory_copy_id, cover_id


def _insert_match_candidate(
    session: Session,
    *,
    source_cover_id: int,
    candidate_cover_id: int,
    grouping_type: str | None,
    grouping_key: str | None,
    candidate_type: str = "combined_similarity",
) -> CoverImageMatchCandidate:
    row = CoverImageMatchCandidate(
        source_cover_image_id=source_cover_id,
        candidate_cover_image_id=candidate_cover_id,
        candidate_type=candidate_type,
        confidence_bucket="high",
        deterministic_score=0.9,
        normalized_confidence_score=0.9,
        extraction_version=f"relationship-conflict-{grouping_type or 'plain'}",
        ranking_score=0.8,
        matched_signals={"phash_similarity": 0.95, "barcode_matches": ["123456789012"]},
        hard_match_flags_json={
            "ocr_title_exact_match": True,
            "ocr_issue_number_exact_match": True,
            "ocr_publisher_exact_match": True,
        },
        weak_signal_flags_json={},
        ranking_reason_json={},
        grouping_type=grouping_type,
        grouping_key=grouping_key,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _insert_link_decision(
    session: Session,
    *,
    source_cover_id: int,
    candidate_cover_id: int,
    decision_type: str,
    relationship_type: str,
    source_match_candidate_id: int | None = None,
) -> CoverImageLinkDecision:
    row = CoverImageLinkDecision(
        source_cover_image_id=source_cover_id,
        candidate_cover_image_id=candidate_cover_id,
        pair_key=cover_link_pair_key(source_cover_id, candidate_cover_id),
        source_match_candidate_id=source_match_candidate_id,
        decision_type=decision_type,
        relationship_type=relationship_type,
        decision_state="active",
        reviewer_user_id=None,
        decision_reason=f"{decision_type}:{relationship_type}",
        decision_source="human",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _insert_suggestion(
    session: Session,
    *,
    cover_image_id: int,
    suggested_metadata_identity_key: str,
) -> CanonicalIssueLinkSuggestion:
    row = CanonicalIssueLinkSuggestion(
        cover_image_id=cover_image_id,
        inventory_copy_id=None,
        canonical_issue_id=None,
        canonical_series_id=None,
        canonical_publisher_id=None,
        suggested_metadata_identity_key=suggested_metadata_identity_key,
        suggestion_type="relationship_context",
        confidence_bucket="medium",
        deterministic_score=0.72,
        confidence_version="canonical-issue-suggestion-v1",
        evidence_json={"seed": suggested_metadata_identity_key},
        suppression_reason=None,
        review_state="pending",
        reviewed_by_user_id=None,
        reviewed_at=None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_duplicate_scan_vs_variant_family_conflict(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-dup-vf@example.com")
    _, source_cover_id = _create_cover(client, token, title="Invincible", issue_number="1", color=(10, 80, 200))
    _, candidate_cover_id = _create_cover(client, token, title="Invincible", issue_number="1", color=(20, 90, 210))
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_duplicate_scan",
        grouping_key="dup-group",
    )
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_variant_family",
        grouping_key="vf-group",
    )

    response = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert response.status_code == 200
    conflict_types = {row["conflict_type"] for row in response.json()["conflicts"]}
    assert "duplicate_scan_vs_variant_family" in conflict_types


def test_approved_link_vs_rejected_link_conflict(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-approved-rejected@example.com")
    _, source_cover_id = _create_cover(client, token, title="Saga", issue_number="1", color=(180, 40, 80))
    _, candidate_cover_id = _create_cover(client, token, title="Saga", issue_number="1", color=(190, 50, 90))
    _insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="approved_link",
        relationship_type="same_issue",
    )
    _insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="rejected_link",
        relationship_type="unrelated",
    )

    response = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert response.status_code == 200
    conflict_types = {row["conflict_type"] for row in response.json()["conflicts"]}
    assert "approved_link_vs_rejected_link" in conflict_types
    assert "same_issue_vs_unrelated" in conflict_types


def test_canonical_suggestion_mismatch_conflict(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-canon-mismatch@example.com")
    _, source_cover_id = _create_cover(client, token, title="Batman", issue_number="1", color=(40, 40, 180))
    _, candidate_cover_id = _create_cover(client, token, title="Batman", issue_number="1", color=(60, 60, 160))
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_same_cover",
        grouping_key="same-cover-group",
    )
    _insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="approved_link",
        relationship_type="same_cover",
    )
    _insert_suggestion(
        session,
        cover_image_id=source_cover_id,
        suggested_metadata_identity_key="dc|batman|1|cover-a",
    )
    _insert_suggestion(
        session,
        cover_image_id=candidate_cover_id,
        suggested_metadata_identity_key="dc|batman|1|cover-b",
    )

    response = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert response.status_code == 200
    conflict_types = {row["conflict_type"] for row in response.json()["conflicts"]}
    assert "canonical_suggestion_mismatch" in conflict_types


def test_preorder_not_in_hand_reconciliation_warning_conflict(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-preorder-warning@example.com")
    inventory_copy_id, cover_id = _create_cover(
        client,
        token,
        title="Spawn",
        issue_number="1",
        release_date="2099-07-15",
        color=(220, 120, 40),
    )
    warning = CoverImageOcrReconciliationWarning(
        cover_image_id=cover_id,
        inventory_copy_id=inventory_copy_id,
        ocr_candidate_id=None,
        warning_type="missing_metadata",
        severity="warning",
        current_metadata_value=None,
        candidate_value="Spawn",
        message="Preorder row should not require reconciliation yet.",
        status="open",
    )
    session.add(warning)
    session.commit()

    response = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert response.status_code == 200
    conflict_types = {row["conflict_type"] for row in response.json()["conflicts"]}
    assert "preorder_not_in_hand_reconciliation_warning" in conflict_types


def test_stale_conflicts_mark_resolved_on_rerun(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-resolve-stale@example.com")
    _, source_cover_id = _create_cover(client, token, title="Monstress", issue_number="1", color=(90, 40, 140))
    _, candidate_cover_id = _create_cover(client, token, title="Monstress", issue_number="1", color=(100, 50, 150))
    duplicate_row = _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_duplicate_scan",
        grouping_key="stale-dup",
    )
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_variant_family",
        grouping_key="stale-vf",
    )

    first = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert first.status_code == 200
    conflict = next(
        row for row in first.json()["conflicts"] if row["conflict_type"] == "duplicate_scan_vs_variant_family"
    )
    conflict_key = conflict["conflict_key"]

    duplicate_row.dismissed_at = datetime.now(timezone.utc)
    session.add(duplicate_row)
    session.commit()

    second = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert second.status_code == 200
    stored = session.exec(
        select(CoverRelationshipConflict).where(CoverRelationshipConflict.conflict_key == conflict_key)
    ).one()
    assert stored.status == "resolved"
    assert stored.resolved_at is not None


def test_acknowledge_dismiss_resolve_state_transitions(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-lifecycle@example.com")
    _, source_cover_id = _create_cover(client, token, title="X-Men", issue_number="1", color=(70, 70, 190))
    _, candidate_cover_id = _create_cover(client, token, title="X-Men", issue_number="1", color=(90, 90, 170))
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_duplicate_scan",
        grouping_key="life-dup",
    )
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_variant_family",
        grouping_key="life-vf",
    )
    detected = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert detected.status_code == 200
    conflict_id = next(
        row["id"] for row in detected.json()["conflicts"] if row["conflict_type"] == "duplicate_scan_vs_variant_family"
    )

    acknowledged = client.patch(
        f"/relationship-conflicts/{conflict_id}/acknowledge",
        headers=inv.auth_headers(token),
        json={"reason": "Seen"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["conflict"]["status"] == "acknowledged"

    dismissed = client.patch(
        f"/relationship-conflicts/{conflict_id}/dismiss",
        headers=inv.auth_headers(token),
        json={"reason": "Still watching"},
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["conflict"]["status"] == "dismissed"

    resolved = client.patch(
        f"/relationship-conflicts/{conflict_id}/resolve",
        headers=inv.auth_headers(token),
        json={"reason": "Reviewed"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["conflict"]["status"] == "resolved"


def test_relationship_conflict_idempotency(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-idempotent@example.com")
    _, source_cover_id = _create_cover(client, token, title="Hellboy", issue_number="1", color=(110, 30, 30))
    _, candidate_cover_id = _create_cover(client, token, title="Hellboy", issue_number="1", color=(120, 40, 40))
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_duplicate_scan",
        grouping_key="idem-dup",
    )
    _insert_match_candidate(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        grouping_type="probable_variant_family",
        grouping_key="idem-vf",
    )

    first = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    second = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert first.status_code == 200
    assert second.status_code == 200

    conflict_key = next(
        row["conflict_key"] for row in second.json()["conflicts"] if row["conflict_type"] == "duplicate_scan_vs_variant_family"
    )
    count = session.exec(
        select(CoverRelationshipConflict).where(CoverRelationshipConflict.conflict_key == conflict_key)
    ).all()
    assert len(count) == 1


def test_detection_does_not_mutate_metadata_or_link_decisions(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-conflict-no-mutation@example.com")
    inventory_copy_id, source_cover_id = _create_cover(
        client,
        token,
        title="Dept. H",
        issue_number="1",
        color=(40, 140, 140),
    )
    _, candidate_cover_id = _create_cover(
        client,
        token,
        title="Dept. H",
        issue_number="1",
        color=(50, 150, 150),
    )
    approved = _insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="approved_link",
        relationship_type="same_issue",
    )
    rejected = _insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="rejected_link",
        relationship_type="unrelated",
    )
    inventory_copy = session.get(InventoryCopy, inventory_copy_id)
    assert inventory_copy is not None
    before_identity = inventory_copy.metadata_identity_key
    before_approved_state = approved.decision_state
    before_rejected_state = rejected.decision_state

    response = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert response.status_code == 200

    session.refresh(inventory_copy)
    session.refresh(approved)
    session.refresh(rejected)
    assert inventory_copy.metadata_identity_key == before_identity
    assert approved.decision_state == before_approved_state
    assert rejected.decision_state == before_rejected_state
