from datetime import datetime, timezone

import test_cover_image_match_candidates as mcc
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import CanonicalIssueLinkSuggestion, CoverImage, CoverImageFingerprint, MetadataAlias, MetadataAudit


def _set_inventory_identity(session: Session, inv_id: int, metadata_identity_key: str) -> None:
    from app.models import InventoryCopy

    row = session.get(InventoryCopy, inv_id)
    assert row is not None
    row.metadata_identity_key = metadata_identity_key
    session.add(row)
    session.commit()


def _list_actions(session: Session) -> set[str]:
    return {row.action for row in session.exec(select(MetadataAudit)).all()}


def test_exact_identity_key_suggestion_generation(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "canon-issue-exact@example.com")
    headers = mcc.auth_headers(token)
    source_inv_id, source_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(20, 100, 200)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    _set_inventory_identity(session, source_inv_id, "Image|Invincible|1|")

    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert generated.status_code == 200
    payload = generated.json()
    exact = next(row for row in payload["suggestions"] if row["suggestion_type"] == "exact_identity_key")
    assert exact["suggested_metadata_identity_key"] == "Image|Invincible|1|"
    assert exact["canonical_issue_id"] is not None
    assert exact["confidence_bucket"] in {"very_high", "high"}


def test_normalized_title_issue_publisher_suggestion(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "canon-issue-biblio@example.com")
    headers = mcc.auth_headers(token)
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(200, 80, 20)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert generated.status_code == 200
    payload = generated.json()
    strong = next(
        row for row in payload["suggestions"] if row["suggestion_type"] == "normalized_title_issue_publisher"
    )
    assert strong["canonical_issue_id"] is not None
    assert strong["evidence_json"]["normalized_title"] == "Invincible"
    assert strong["evidence_json"]["normalized_issue_number"] == "1"
    assert strong["evidence_json"]["normalized_publisher"] == "Image"


def test_title_issue_only_weaker_suggestion(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "canon-issue-title-issue@example.com")
    headers = mcc.auth_headers(token)
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(140, 80, 50)),
        raw_text="INVINCIBLE #1",
    )
    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert generated.status_code == 200
    payload = generated.json()
    weaker = next(row for row in payload["suggestions"] if row["suggestion_type"] == "normalized_title_issue")
    assert weaker["confidence_bucket"] in {"medium", "low"}


def test_upc_only_does_not_generate_canonical_issue_suggestion(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "canon-issue-upc-only@example.com")
    headers = mcc.auth_headers(token)
    source_inv_id, source_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(10, 10, 10)),
        raw_text="UPC 123456789012",
    )
    _set_inventory_identity(session, source_inv_id, "")
    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert generated.status_code == 200
    assert generated.json()["suggestions"] == []


def test_variant_family_context_surfaces_shared_suggestion(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "canon-issue-vfctx@example.com")
    headers = mcc.auth_headers(token)
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(20, 20, 120)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    _, peer_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(220, 220, 60)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    now = datetime.now(timezone.utc)
    mcc._overwrite_fingerprints_max_hamming(
        session,
        source_cover_id=source_cover_id,
        target_cover_id=peer_cover_id,
        now=now,
    )
    insert_row = session.exec(select(CoverImage).where(CoverImage.id == source_cover_id)).first()
    peer_row = session.exec(select(CoverImage).where(CoverImage.id == peer_cover_id)).first()
    assert insert_row is not None and peer_row is not None
    from app.models import CoverImageMatchCandidate

    session.add(
        CoverImageMatchCandidate(
            source_cover_image_id=source_cover_id,
            candidate_cover_image_id=peer_cover_id,
            candidate_type="combined_similarity",
            confidence_bucket="high",
            deterministic_score=0.88,
            normalized_confidence_score=0.88,
            extraction_version="canon-issue-vfctx",
            ranking_score=0.8,
            matched_signals={"phash_similarity": 0.55},
            hard_match_flags_json={
                "ocr_title_exact_match": True,
                "ocr_issue_number_exact_match": True,
                "ocr_publisher_exact_match": True,
            },
            weak_signal_flags_json={},
            ranking_reason_json={},
            grouping_type="probable_variant_family",
            grouping_key="probable_variant_family:canon-ctx",
        )
    )
    session.commit()

    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert generated.status_code == 200
    payload = generated.json()
    assert any(row["suggestion_type"] == "variant_family_context" for row in payload["suggestions"])


def test_duplicate_scan_context_surfaces_review_only_suggestion(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "canon-issue-dupscan@example.com")
    headers = mcc.auth_headers(token)
    shared_image = mcc.make_png_bytes(color=(50, 50, 50))
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text="INVINCIBLE #1 IMAGE UPC 123456789012"
    )
    _, peer_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text="INVINCIBLE #1 IMAGE UPC 123456789012"
    )
    mcc._prepare_cover_signals(client, token, source_cover_id)
    mcc._prepare_cover_signals(client, token, peer_cover_id)
    gen = client.post(f"/cover-images/{source_cover_id}/generate-match-candidates", headers=headers)
    combined = mcc._candidate_by_type(gen.json(), "combined_similarity")
    decision = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": peer_cover_id,
            "source_match_candidate_id": combined["id"],
            "decision_type": "approved_link",
            "relationship_type": "duplicate_scan",
        },
    )
    assert decision.status_code == 200
    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert generated.status_code == 200
    dup_ctx = next(row for row in generated.json()["suggestions"] if row["suggestion_type"] == "duplicate_scan_context")
    assert dup_ctx["evidence_json"]["review_only_context"] is True


def test_review_state_approve_reject_ignore_and_idempotent_rerun(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "canon-issue-review@example.com")
    headers = mcc.auth_headers(token)
    inv_id, source_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(150, 100, 50)),
        raw_text="INVINCIBLE #1 IMAGE",
    )
    before_cover = session.get(CoverImage, source_cover_id)
    assert before_cover is not None
    before_cover_series_id = before_cover.canonical_series_id
    _set_inventory_identity(session, inv_id, "Image|Invincible|1|")

    generated = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert generated.status_code == 200
    suggestions = generated.json()["suggestions"]
    first_id = suggestions[0]["id"]

    approve = client.patch(
        f"/canonical-issue-suggestions/{first_id}/approve",
        headers=headers,
        json={"reason": "reviewed exact identity"},
    )
    assert approve.status_code == 200
    assert approve.json()["suggestion"]["review_state"] == "approved"

    reject = client.patch(
        f"/canonical-issue-suggestions/{first_id}/reject",
        headers=headers,
        json={"reason": "override to rejected"},
    )
    assert reject.status_code == 200
    assert reject.json()["suggestion"]["review_state"] == "rejected"

    ignore = client.patch(
        f"/canonical-issue-suggestions/{first_id}/ignore",
        headers=headers,
        json={"reason": "ignore duplicate row"},
    )
    assert ignore.status_code == 200
    assert ignore.json()["suggestion"]["review_state"] == "ignored"

    rerun = client.post(
        f"/cover-images/{source_cover_id}/generate-canonical-issue-suggestions",
        headers=headers,
    )
    assert rerun.status_code == 200
    after_rows = session.exec(
        select(CanonicalIssueLinkSuggestion).where(CanonicalIssueLinkSuggestion.cover_image_id == source_cover_id)
    ).all()
    assert len(after_rows) == len({(row.canonical_issue_id, row.suggested_metadata_identity_key, row.suggestion_type, row.confidence_version) for row in after_rows})

    after_cover = session.get(CoverImage, source_cover_id)
    assert after_cover is not None
    assert after_cover.canonical_series_id == before_cover_series_id

    alias_count = len(session.exec(select(MetadataAlias)).all())
    assert alias_count == 0

    actions = _list_actions(session)
    assert "canonical_issue_link_suggestion_created" in actions
    assert "canonical_issue_link_suggestion_approved" in actions
    assert "canonical_issue_link_suggestion_rejected" in actions
    assert "canonical_issue_link_suggestion_ignored" in actions
    assert "canonical_issue_link_suggestion_regenerated" in actions
