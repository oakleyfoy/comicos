from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import InventoryCopy, MarketForecast, Order, ScanImage, ScanIngestionBatch, ScanUploadSession, User
from app.models.data_integrity import DataIntegrityCheck, DataIntegrityIssue
from app.models.marketplace_listing import MarketplaceListing
from app.services.data_integrity import run_integrity_check
from test_inventory import register_and_login


def _seed_integrity_violations(session: Session, *, owner_user_id: int) -> None:
    upload_session = ScanUploadSession(
        owner_user_id=owner_user_id,
        upload_source="scanner",
        session_checksum="upload-checksum-1",
        total_files=1,
        successful_files=0,
        failed_files=1,
    )
    session.add(upload_session)
    session.flush()

    batch = ScanIngestionBatch(
        owner_user_id=owner_user_id,
        upload_session_id=int(upload_session.id or 0),
        source_type="scanner",
        batch_status="failed",
        image_count=1,
        failed_count=1,
        ingestion_checksum="batch-checksum-1",
    )
    session.add(batch)
    session.flush()

    session.add(
        InventoryCopy(
            user_id=owner_user_id,
            order_item_id=1,
            variant_id=1,
            copy_number=1,
            acquisition_cost="-9.99",
            release_status="unknown",
            order_status="ordered",
            grade_status="raw",
            hold_status="hold",
        )
    )
    session.add(
        Order(
            user_id=owner_user_id,
            retailer="Test Retailer",
            order_date=date(2026, 5, 30),
            shipping_amount="2.00",
            tax_amount="1.00",
            total_amount="1.00",
        )
    )
    session.add(
        MarketplaceListing(
            owner_id=owner_user_id,
            listing_title="Integrity Listing",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price="-3.50",
            quantity=1,
            status="draft",
        )
    )
    session.add(
        ScanImage(
            owner_user_id=owner_user_id,
            ingestion_batch_id=int(batch.id or 0),
            sequence_index=0,
            original_filename="bad-scan.png",
            storage_path="/tmp/bad-scan.png",
            mime_type="image/png",
            file_size_bytes=0,
            sha256_checksum="a" * 64,
            processing_status="failed",
            is_duplicate=False,
        )
    )
    session.add(
        MarketForecast(
            owner_user_id=owner_user_id,
            forecast_type="PRICE_FORECAST",
            asset_type="inventory_copy",
            asset_id=1,
            forecast_horizon_days=0,
            forecast_value=19.5,
            confidence_score=1.2,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()


def test_run_integrity_check_creates_check_and_issues_without_repair(client: TestClient) -> None:
    token = register_and_login(client, "integrity-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "integrity-owner@example.com")).one()
        owner_user_id = int(owner.id or 0)
        _seed_integrity_violations(session, owner_user_id=owner_user_id)

        listing_count_before = len(session.exec(select(MarketplaceListing).where(MarketplaceListing.owner_id == owner_user_id)).all())
        forecast_count_before = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all())

        detail = run_integrity_check(session, owner_user_id=owner_user_id)

        listing_count_after = len(session.exec(select(MarketplaceListing).where(MarketplaceListing.owner_id == owner_user_id)).all())
        forecast_count_after = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all())
        checks = session.exec(select(DataIntegrityCheck).where(DataIntegrityCheck.owner_user_id == owner_user_id)).all()
        issues = session.exec(
            select(DataIntegrityIssue).where(DataIntegrityIssue.check_id == int(detail.check.id))
        ).all()

    assert token
    assert detail.check.check_status == "WARNING"
    assert detail.check.summary_json["issue_count"] == len(detail.issues)
    assert len(detail.issues) >= 4
    assert len(checks) == 1
    assert len(issues) == len(detail.issues)
    assert listing_count_before == listing_count_after
    assert forecast_count_before == forecast_count_after
