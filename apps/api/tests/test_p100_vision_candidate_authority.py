"""P100-23 vision candidate authority — catalog validates vision, does not override it."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.photo_import import (
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportImage,
    PhotoImportSession,
)
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.photo_import_candidate_service import (
    ScoredCatalogRow,
    VISION_EXACT_MATCH_BOOST,
    _apply_vision_candidate_authority,
    refresh_candidates_for_detection,
)
from app.services.photo_import_detection_service import detection_to_read


def _engine(tmp_path, monkeypatch):
    import app.services.photo_import_crop_service as crop_mod
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir(exist_ok=True)
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)
    monkeypatch.setattr(storage_mod, "LEGACY_APPS_ROOT", tmp_path / "apps")
    monkeypatch.setattr(storage_mod, "PHOTO_IMPORT_ROOT", api_root / "data" / "photo_import")
    monkeypatch.setattr(crop_mod, "REPO_ROOT", api_root)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine, api_root


def _add_issue(session: Session, *, publisher: str, series: str, issue: str) -> tuple[CatalogIssue, CatalogSeries, CatalogPublisher]:
    pub = session.exec(select(CatalogPublisher).where(CatalogPublisher.name == publisher)).first()
    if pub is None:
        pub = CatalogPublisher(name=publisher, normalized_name=publisher.lower())
        session.add(pub)
        session.flush()
    ser = CatalogSeries(name=series, normalized_name=normalize_series_name(series), publisher_id=pub.id)
    session.add(ser)
    session.flush()
    iss = CatalogIssue(
        series_id=int(ser.id),
        publisher_id=int(pub.id),
        issue_number=issue,
        normalized_issue_number=normalize_issue_number(issue),
    )
    session.add(iss)
    session.flush()
    return iss, ser, pub


def _vision_det(**kwargs) -> PhotoImportDetectedBook:
    defaults = dict(
        session_id=1,
        image_id=1,
        user_id=1,
        recognition_mode="vision_first",
        ai_series="Falcon",
        ai_issue_number="1",
        ai_publisher="Marvel",
        ai_visible_title_text="Falcon",
    )
    defaults.update(kwargs)
    return PhotoImportDetectedBook(**defaults)


def test_vision_authority_penalizes_disagreeing_series() -> None:
    falcon_iss = CatalogIssue(id=1, series_id=1, publisher_id=1, issue_number="1", normalized_issue_number="1")
    falcon_ser = CatalogSeries(id=1, name="Falcon", normalized_name="falcon", publisher_id=1)
    legacy_iss = CatalogIssue(id=2, series_id=2, publisher_id=1, issue_number="1", normalized_issue_number="1")
    legacy_ser = CatalogSeries(id=2, name="Marvel Legacy", normalized_name="marvel legacy", publisher_id=1)
    pub = CatalogPublisher(id=1, name="Marvel", normalized_name="marvel")

    legacy_row = ScoredCatalogRow(
        legacy_iss,
        legacy_ser,
        pub,
        85.0,
        "Character/title fallback",
        "character_title_fallback",
    )
    falcon_row = ScoredCatalogRow(
        falcon_iss,
        falcon_ser,
        pub,
        70.0,
        "Exact series and issue",
        "exact_series_issue",
    )
    det = _vision_det()
    ranked = _apply_vision_candidate_authority(det, [legacy_row, falcon_row])
    assert ranked[0].series.name == "Falcon"
    assert ranked[0].match_score > ranked[1].match_score


def test_barcode_override_allows_disagreeing_series_to_rank(tmp_path, monkeypatch) -> None:
    engine, _api_root = _engine(tmp_path, monkeypatch)
    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    barcode = "012345678905"
    with Session(engine) as session:
        legacy_iss, legacy_ser, pub = _add_issue(session, publisher="Marvel", series="Marvel Legacy", issue="1")
        _add_issue(session, publisher="Marvel", series="Falcon", issue="1")
        session.add(
            CatalogUpc(
                issue_id=int(legacy_iss.id),
                upc=barcode,
                normalized_upc=barcode,
                source="test",
                confidence=Decimal("1.0"),
            )
        )
        session.add(
            PhotoImportSession(id=1, user_id=1, session_token="tok", expires_at=expires, capture_mode="single_comic")
        )
        session.add(
            PhotoImportImage(
                id=1,
                session_id=1,
                user_id=1,
                storage_path="x.jpg",
                mime_type="image/jpeg",
                file_size=1,
            )
        )
        det = PhotoImportDetectedBook(
            session_id=1,
            image_id=1,
            user_id=1,
            recognition_mode="vision_first",
            ai_series="Falcon",
            ai_issue_number="1",
            ai_publisher="Marvel",
            ai_visible_title_text="Falcon",
            ai_barcode=barcode,
        )
        session.add(det)
        session.commit()
        det_id = int(det.id)

        refresh_candidates_for_detection(session, detected_book_id=det_id)
        top = session.exec(
            select(PhotoImportCandidate)
            .where(PhotoImportCandidate.detected_book_id == det_id)
            .order_by(PhotoImportCandidate.rank.asc())
        ).first()
        assert top is not None
        assert top.series == legacy_ser.name
        read = detection_to_read(session, session.get(PhotoImportDetectedBook, det_id))
        assert read.catalog_verification_status == "disagrees"
        assert read.catalog_verification_label == "Marvel Legacy #1"
        assert "Barcode" in (read.catalog_disagreement_reason or "")


def test_detection_read_shows_verified_when_top_matches_vision(tmp_path, monkeypatch) -> None:
    engine, _api_root = _engine(tmp_path, monkeypatch)
    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        _add_issue(session, publisher="Marvel", series="Falcon", issue="1")
        session.add(
            PhotoImportSession(id=2, user_id=1, session_token="tok2", expires_at=expires, capture_mode="single_comic")
        )
        session.add(
            PhotoImportImage(id=2, session_id=2, user_id=1, storage_path="y.jpg", mime_type="image/jpeg", file_size=1)
        )
        det = PhotoImportDetectedBook(
            session_id=2,
            image_id=2,
            user_id=1,
            recognition_mode="vision_first",
            ai_series="Falcon",
            ai_issue_number="1",
        )
        session.add(det)
        session.commit()
        refresh_candidates_for_detection(session, detected_book_id=int(det.id))
        read = detection_to_read(session, session.get(PhotoImportDetectedBook, int(det.id)))
        assert read.vision_identification_label == "Falcon #1"
        assert read.catalog_verification_status == "verified"
        assert read.catalog_verification_label == "Falcon #1"


def test_leading_the_series_matches_vision_authority() -> None:
    assert normalize_series_name("The Falcon") == normalize_series_name("Falcon")
    assert normalize_series_name("The New Avengers") == normalize_series_name("New Avengers")
    assert normalize_series_name("The Defenders") == normalize_series_name("Defenders")

    falcon_iss = CatalogIssue(id=1, series_id=1, publisher_id=1, issue_number="1", normalized_issue_number="1")
    the_falcon_ser = CatalogSeries(id=1, name="The Falcon", normalized_name="the falcon", publisher_id=1)
    pub = CatalogPublisher(id=1, name="Marvel", normalized_name="marvel")
    row = ScoredCatalogRow(
        falcon_iss,
        the_falcon_ser,
        pub,
        70.0,
        "Exact series and issue",
        "exact_series_issue",
    )
    det = _vision_det(ai_series="Falcon")
    assert _apply_vision_candidate_authority(det, [row])[0].vision_authority_adjustment == VISION_EXACT_MATCH_BOOST


def test_detection_read_verified_with_catalog_the_prefix(tmp_path, monkeypatch) -> None:
    engine, _api_root = _engine(tmp_path, monkeypatch)
    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        _add_issue(session, publisher="Marvel", series="The Falcon", issue="1")
        session.add(
            PhotoImportSession(id=3, user_id=1, session_token="tok3", expires_at=expires, capture_mode="single_comic")
        )
        session.add(
            PhotoImportImage(id=3, session_id=3, user_id=1, storage_path="z.jpg", mime_type="image/jpeg", file_size=1)
        )
        det = PhotoImportDetectedBook(
            session_id=3,
            image_id=3,
            user_id=1,
            recognition_mode="vision_first",
            ai_series="Falcon",
            ai_issue_number="1",
        )
        session.add(det)
        session.commit()
        refresh_candidates_for_detection(session, detected_book_id=int(det.id))
        read = detection_to_read(session, session.get(PhotoImportDetectedBook, int(det.id)))
        assert read.vision_identification_label == "Falcon #1"
        assert read.catalog_verification_status == "verified"
        assert read.catalog_verification_label == "The Falcon #1"
