"""Fingerprint review fallback when catalog rows lack GCD ids."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.p106_1_gcd_non_barcode_recovery_service import (
    FingerprintRecoveryCandidate,
    IntakeGcdRecoveryHints,
    diagnose_gcd_non_barcode_recovery,
)
from app.services.p106_fingerprint_review_fallback_service import (
    REVIEW_DECISION_TOP,
    attach_fingerprint_review_to_diagnosis,
    build_fingerprint_review_bundle,
    collapse_fingerprint_candidates,
    enhance_diagnosis_with_comicvine_fingerprint_consensus,
    fingerprint_review_agrees_with_identity,
)


def _seed_issue(
    session: Session,
    *,
    series_name: str,
    issue_number: str = "1",
    publisher: str = "Marvel",
    title: str | None = None,
) -> CatalogIssue:
    pub = CatalogPublisher(name=publisher, normalized_name=publisher.lower())
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name=series_name,
        normalized_name=series_name.lower(),
        publisher_id=int(pub.id),
        start_year=2024,
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number=issue_number,
        normalized_issue_number=issue_number,
        title=title or series_name,
        external_source_ids={"_primary_source": "COMICVINE", "COMICVINE": {"12345": True}},
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def test_collapse_same_metadata_family(session: Session) -> None:
    issue = _seed_issue(session, series_name="X-Men")
    iid = int(issue.id or 0)
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series="X-Men",
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        fingerprint_candidates=[
            FingerprintRecoveryCandidate(catalog_issue_id=iid, gcd_issue_id=None, confidence=0.91),
            FingerprintRecoveryCandidate(catalog_issue_id=iid, gcd_issue_id=None, confidence=0.88),
        ],
    )
    groups = collapse_fingerprint_candidates(session, hints.fingerprint_candidates)
    assert len(groups) == 1
    bundle = build_fingerprint_review_bundle(session, hints, limit=3)
    assert len(bundle["top_candidates"]) == 1
    assert bundle["single_family"] is True


def test_conflicting_fingerprint_families(session: Session) -> None:
    a = _seed_issue(session, series_name="X-Men")
    b = _seed_issue(session, series_name="Avengers")
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series=None,
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        fingerprint_candidates=[
            FingerprintRecoveryCandidate(catalog_issue_id=int(a.id), gcd_issue_id=None, confidence=0.9),
            FingerprintRecoveryCandidate(catalog_issue_id=int(b.id), gcd_issue_id=None, confidence=0.89),
        ],
    )
    bundle = build_fingerprint_review_bundle(session, hints, limit=3)
    assert len(bundle["top_candidates"]) == 2
    assert bundle["single_family"] is False


def test_attach_review_candidates_to_diagnosis(session: Session) -> None:
    issue = _seed_issue(session, series_name="Spider-Man")
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series="Spider-Man",
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        fingerprint_candidates=[
            FingerprintRecoveryCandidate(
                catalog_issue_id=int(issue.id),
                gcd_issue_id=None,
                confidence=0.93,
            )
        ],
    )
    diagnosis: dict = {"gcd_match_count": 0, "ready_to_auto_import": False}
    attach_fingerprint_review_to_diagnosis(session, diagnosis, hints=hints, barcode="75960620629200111")
    assert diagnosis["review_decision"] == REVIEW_DECISION_TOP
    assert len(diagnosis["needs_review_top_candidates"]) >= 1
    assert diagnosis["needs_review_top_candidates"][0].get("gcd_issue_id") is None
    assert diagnosis.get("gcd_series")


def test_diagnose_emits_review_candidates_on_insufficient_metadata(session: Session, tmp_path: Path) -> None:
    issue = _seed_issue(session, series_name="X-Men")
    hints = IntakeGcdRecoveryHints(
        publisher=None,
        series=None,
        issue_number=None,
        year=None,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        fingerprint_candidates=[
            FingerprintRecoveryCandidate(catalog_issue_id=int(issue.id), gcd_issue_id=None, confidence=0.9),
        ],
    )
    gcd_path = tmp_path / "gcd.db"
    gcd_path.write_bytes(b"")
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode="75960620629200111",
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0},
    )
    assert diag.get("needs_review_top_candidates")
    assert diag.get("review_decision") == REVIEW_DECISION_TOP


def test_comicvine_fingerprint_agreement_sets_import_ready(session: Session) -> None:
    issue = _seed_issue(session, series_name="Superman", issue_number="39", publisher="DC Comics")
    hints = IntakeGcdRecoveryHints(
        publisher="DC Comics",
        series="Superman",
        issue_number="39",
        year=2015,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        fingerprint_candidates=[
            FingerprintRecoveryCandidate(
                catalog_issue_id=int(issue.id),
                gcd_issue_id=None,
                confidence=0.95,
            )
        ],
        fingerprint_confidence=0.95,
    )
    diagnosis: dict = {"gcd_match_count": 0}
    attach_fingerprint_review_to_diagnosis(
        session,
        diagnosis,
        hints=hints,
        barcode="76194134192703921",
    )
    cv = {
        "publisher": "DC Comics",
        "series": "Superman",
        "issue_number": "39",
        "year": "2015",
    }
    assert fingerprint_review_agrees_with_identity(
        diagnosis["needs_review_top_candidates"],
        publisher="DC Comics",
        series="Superman",
        issue_number="39",
    )
    enhance_diagnosis_with_comicvine_fingerprint_consensus(
        diagnosis,
        hints=hints,
        barcode="76194134192703921",
        comicvine_candidate=cv,
    )
    assert diagnosis.get("comicvine_review_candidate", {}).get("import_ready") is True
    assert diagnosis.get("ready_to_auto_import") is True
    assert diagnosis.get("import_path") == "comicvine_fingerprint_consensus"
