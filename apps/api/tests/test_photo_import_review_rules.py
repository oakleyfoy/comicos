"""P100-12 photo import review confirm rules."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.photo_import import (
    RECOGNITION_STATUS_AMBIGUOUS,
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportSession,
)
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.photo_import_review_rules import (
    can_confirm_detection,
    qualifies_for_bulk_high_confidence_confirm,
)
from test_inventory import auth_headers, register_and_login


def test_confirm_disabled_without_selected_candidate() -> None:
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        selected_catalog_issue_id=None,
        recognition_status="unknown",
    )
    assert can_confirm_detection(det, best_candidate=None) is False


def test_confirm_all_ignores_unmatched(session: Session) -> None:
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        selected_catalog_issue_id=None,
        ai_confidence=0.95,
        recognition_status="matched",
    )
    cand = PhotoImportCandidate(
        detected_book_id=1,
        catalog_issue_id=99,
        match_score=95.0,
        rank=1,
    )
    assert qualifies_for_bulk_high_confidence_confirm(det, best_candidate=cand) is False


def test_candidate_debug_endpoint_returns_match_reasons(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p100-12-debug@example.com")
    user_id = int(client.get("/auth/me", headers=auth_headers(token)).json()["id"])

    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    series = CatalogSeries(name="X-Factor", normalized_name="x factor", publisher_id=pub.id, start_year=1990)
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="104",
        normalized_issue_number=normalize_issue_number("104"),
    )
    session.add(issue)
    session.flush()

    from datetime import datetime, timedelta, timezone

    import_row = PhotoImportSession(
        user_id=user_id,
        session_token="debugtok12345678901234567890123456789012",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active",
    )
    session.add(import_row)
    session.flush()

    det = PhotoImportDetectedBook(
        session_id=int(import_row.id),
        image_id=1,
        user_id=user_id,
        ai_series="X-Factor",
        ai_issue_number="104",
        ai_publisher="Marvel",
    )
    session.add(det)
    session.flush()

    from app.services.photo_import_candidate_service import refresh_candidates_for_detection

    refresh_candidates_for_detection(session, detected_book_id=int(det.id))

    resp = client.get(
        f"/api/v1/photo-import/detections/{det.id}/candidates",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates"]
    assert body["debug"]["candidate_count"] >= 1
    assert body["candidates"][0]["match_reason"]
    assert body["candidates"][0]["matched_on"]
