from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.models import ScanImage, ScanIngestionBatch, ScanUploadSession, User
from app.services.condition_intelligence import create_scan_analysis
from app.services.scan_quality_agent import analyze_scan_quality, evaluate_resolution
from sqlmodel import select
from test_inventory import register_and_login


def _seed_scan_image(session: Session, *, owner_user_id: int) -> ScanImage:
    upload = ScanUploadSession(
        owner_user_id=owner_user_id,
        upload_source="test",
        session_checksum="ci-session-1",
    )
    session.add(upload)
    session.commit()
    session.refresh(upload)
    batch = ScanIngestionBatch(
        owner_user_id=owner_user_id,
        upload_session_id=int(upload.id),
        source_type="test",
        batch_status="COMPLETED",
        ingestion_checksum="ci-batch-1",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    image = ScanImage(
        owner_user_id=owner_user_id,
        ingestion_batch_id=int(batch.id),
        sequence_index=1,
        original_filename="front.jpg",
        storage_path="/tmp/front.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1024,
        sha256_checksum="ci" + "a" * 61,
        width=2400,
        height=3600,
        dpi_x=600,
        dpi_y=600,
        processing_status="INGESTED",
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def test_scan_quality_agent_generates_assessment(client: TestClient) -> None:
    email = "scan-quality@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        image = _seed_scan_image(session, owner_user_id=owner_user_id)
        analysis_read = create_scan_analysis(session, owner_user_id=owner_user_id, front_image_id=int(image.id))
        from app.models.condition_intelligence import ScanAnalysis

        analysis = session.get(ScanAnalysis, analysis_read.id)
        assert analysis is not None
        result = analyze_scan_quality(session, analysis=analysis)
        assert result.quality_status in {"PASS", "WARNING", "FAIL"}
        assert result.image_quality_score >= 0
        assert evaluate_resolution(image) >= 35.0
