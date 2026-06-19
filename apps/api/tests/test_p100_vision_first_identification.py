"""P100-22 vision-first identification + catalog verification."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.photo_import import (
    CAPTURE_MODE_SINGLE_COMIC,
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportImage,
    PhotoImportSession,
)
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.photo_import_ai_recognition_service import run_ai_recognition_for_image
from app.services.photo_import_candidate_service import refresh_candidates_for_detection
from app.services.photo_import_vision_identification_service import (
    parse_vision_identification,
    vision_identification_to_book,
)


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


def _make_image(api_root, image_id: int) -> str:
    src = api_root / "data" / "photo_import" / f"{image_id}.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (600, 900), color=(120, 30, 30)).save(src, format="JPEG")
    return str(src.relative_to(api_root)).replace("\\", "/")


def _add_issue(session: Session, *, publisher: str, series: str, issue: str) -> CatalogIssue:
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
    return iss


def _vision_payload(**overrides) -> dict:
    base = {
        "publisher": "Marvel",
        "series_title": "Falcon",
        "issue_number": "1",
        "issue_title": "",
        "cover_date": "",
        "publication_year": "1983",
        "barcode_text": "",
        "visible_logo_text": "Falcon",
        "visible_issue_box_text": "1",
        "visible_cover_text": "",
        "confidence": 0.9,
        "uncertainty_reason": "",
        "top_identification_reasons": ["Logo reads Falcon", "Issue box shows 1"],
        "possible_alternates": [],
    }
    base.update(overrides)
    return base


def _run_single_comic(engine, *, session_id: int, image_id: int, rel_path: str, payload: dict, det_id: int):
    import app.services.photo_import_ai_recognition_service as ai_mod

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(ai_mod, "_call_openai_vision_json", return_value=payload):
        with Session(engine) as session:
            session.add(
                PhotoImportSession(
                    id=session_id,
                    user_id=1,
                    session_token=f"tok-{session_id}",
                    expires_at=expires,
                    capture_mode=CAPTURE_MODE_SINGLE_COMIC,
                )
            )
            session.add(
                PhotoImportImage(
                    id=image_id,
                    session_id=session_id,
                    user_id=1,
                    storage_path=rel_path,
                    mime_type="image/jpeg",
                    file_size=1,
                )
            )
            session.commit()
            run_ai_recognition_for_image(session, image_id=image_id)


def test_vision_identification_to_book_keeps_numeric_issue() -> None:
    ident = parse_vision_identification(_vision_payload(issue_number="1", issue_title="The Initiative"))
    book = vision_identification_to_book(ident)
    assert book["issue_number_guess"] == "1"
    assert "Initiative" in (book.get("subtitle_guess") or "")
    assert book["recognition_mode"] == "vision_first"


def test_vision_subtitle_in_issue_field_is_sanitized() -> None:
    ident = parse_vision_identification(_vision_payload(issue_number="The Initiative", issue_title=""))
    book = vision_identification_to_book(ident)
    assert book["issue_number_guess"] is None
    assert "Initiative" in (book.get("subtitle_guess") or "")


def test_falcon_vision_maps_to_falcon_issue_one(tmp_path, monkeypatch) -> None:
    engine, api_root = _engine(tmp_path, monkeypatch)
    rel = _make_image(api_root, 10)
    with Session(engine) as session:
        _add_issue(session, publisher="Marvel", series="Falcon", issue="1")
        session.commit()

    _run_single_comic(engine, session_id=1, image_id=10, rel_path=rel, payload=_vision_payload(), det_id=0)

    with Session(engine) as session:
        det = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 10)).one()
        assert det.recognition_mode == "vision_first"
        assert det.ai_series == "Falcon"
        assert det.ai_issue_number == "1"
        refresh_candidates_for_detection(session, detected_book_id=int(det.id))
        cands = session.exec(
            select(PhotoImportCandidate).where(PhotoImportCandidate.detected_book_id == det.id)
        ).all()
        assert cands
        assert cands[0].series == "Falcon"
        assert cands[0].issue_number == "1"


def test_ambiguous_x_returns_multiple_families(tmp_path, monkeypatch) -> None:
    engine, api_root = _engine(tmp_path, monkeypatch)
    rel = _make_image(api_root, 20)
    with Session(engine) as session:
        _add_issue(session, publisher="Marvel", series="X-Men", issue="1")
        _add_issue(session, publisher="Marvel", series="X-Factor", issue="1")
        session.commit()

    payload = _vision_payload(
        series_title="X",
        confidence=0.4,
        uncertainty_reason="Trade dress ambiguous",
        possible_alternates=["X-Men", "X-Factor"],
    )
    _run_single_comic(engine, session_id=2, image_id=20, rel_path=rel, payload=payload, det_id=0)

    with Session(engine) as session:
        det = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 20)).one()
        refresh_candidates_for_detection(session, detected_book_id=int(det.id))
        cands = session.exec(
            select(PhotoImportCandidate).where(PhotoImportCandidate.detected_book_id == det.id)
        ).all()
        series_names = {c.series for c in cands}
        assert "X-Factor" in series_names
        assert len(series_names) >= 2


def test_vision_failure_falls_back_to_ocr(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_ai_recognition_service as ai_mod

    engine, api_root = _engine(tmp_path, monkeypatch)
    rel = _make_image(api_root, 30)
    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)

    ocr_payload = {
        "books": [
            {
                "bbox": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.7},
                "series_guess": "Spawn",
                "issue_number_guess": "1",
                "confidence": 0.8,
            }
        ]
    }
    with mock.patch.object(ai_mod, "_call_openai_vision_json", side_effect=RuntimeError("vision down")):
        with mock.patch.object(ai_mod, "_call_openai_vision", return_value=ocr_payload):
            with Session(engine) as session:
                session.add(
                    PhotoImportSession(
                        id=3,
                        user_id=1,
                        session_token="tok-3",
                        expires_at=expires,
                        capture_mode=CAPTURE_MODE_SINGLE_COMIC,
                    )
                )
                session.add(
                    PhotoImportImage(
                        id=30,
                        session_id=3,
                        user_id=1,
                        storage_path=rel,
                        mime_type="image/jpeg",
                        file_size=1,
                    )
                )
                session.commit()
                run_ai_recognition_for_image(session, image_id=30)
                rows = session.exec(
                    select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 30)
                ).all()
                assert len(rows) == 1
                assert rows[0].recognition_mode == "ocr_fallback"
                assert rows[0].ai_series == "Spawn"


def test_hallucinated_issue_has_no_candidate_and_no_autoselect(tmp_path, monkeypatch) -> None:
    engine, api_root = _engine(tmp_path, monkeypatch)
    rel = _make_image(api_root, 40)
    with Session(engine) as session:
        _add_issue(session, publisher="Marvel", series="Falcon", issue="1")
        session.commit()

    payload = _vision_payload(
        series_title="Totally Made Up Series",
        issue_number="7",
        confidence=0.99,
        visible_logo_text="Totally Made Up Series",
        visible_issue_box_text="7",
    )
    _run_single_comic(engine, session_id=4, image_id=40, rel_path=rel, payload=payload, det_id=0)

    with Session(engine) as session:
        det = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 40)).one()
        refresh_candidates_for_detection(session, detected_book_id=int(det.id))
        session.refresh(det)
        assert det.candidate_count == 0
        assert det.selected_catalog_issue_id is None


def test_barcode_overrides_weak_vision(tmp_path, monkeypatch) -> None:
    engine, api_root = _engine(tmp_path, monkeypatch)
    rel = _make_image(api_root, 50)
    barcode = "012345678905"
    with Session(engine) as session:
        iss = _add_issue(session, publisher="Marvel", series="Daredevil", issue="181")
        session.add(
            CatalogUpc(
                issue_id=int(iss.id),
                upc=barcode,
                normalized_upc=barcode,
                source="test",
                confidence=Decimal("1.0"),
            )
        )
        session.commit()
        barcode_issue_id = int(iss.id)

    payload = _vision_payload(
        series_title="Unclear",
        issue_number=None,
        confidence=0.15,
        uncertainty_reason="Cover damaged",
        barcode_text=barcode,
    )
    _run_single_comic(engine, session_id=5, image_id=50, rel_path=rel, payload=payload, det_id=0)

    with Session(engine) as session:
        det = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 50)).one()
        assert det.ai_barcode == barcode
        refresh_candidates_for_detection(session, detected_book_id=int(det.id))
        session.refresh(det)
        cands = session.exec(
            select(PhotoImportCandidate)
            .where(PhotoImportCandidate.detected_book_id == det.id)
            .order_by(PhotoImportCandidate.rank.asc())
        ).all()
        assert cands
        assert cands[0].catalog_issue_id == barcode_issue_id
        assert (cands[0].score_breakdown or {}).get("barcode_score") == 100.0
        assert det.selected_catalog_issue_id == barcode_issue_id
