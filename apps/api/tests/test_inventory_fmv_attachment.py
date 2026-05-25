from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session
from sqlmodel import select

from app.core.config import get_settings
from app.db.session import get_engine
from app.models import CanonicalIssueLinkSuggestion, CoverImage, InventoryCopy, MarketFmvSnapshot
from app.services.inventory_fmv import build_inventory_fmv_attachment, summarize_inventory_fmv
from test_inventory import auth_headers, create_order, register_and_login


_SNAPSHOT_SEQUENCE = 0


def _next_snapshot_date() -> date:
    global _SNAPSHOT_SEQUENCE
    snapshot_date = date(2026, 5, 25) + timedelta(days=_SNAPSHOT_SEQUENCE)
    _SNAPSHOT_SEQUENCE += 1
    return snapshot_date


@pytest.fixture(autouse=True)
def _isolated_inventory_fmv_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    database_path = tmp_path / "inventory-fmv-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    engine = get_engine()
    from sqlmodel import SQLModel

    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield
    get_engine.cache_clear()
    get_settings.cache_clear()


def _row(
    *,
    inventory_copy_id: int = 1,
    metadata_identity_key: str = "Image|Invincible|1|Cover A",
    canonical_issue_id: int | None = 101,
    title: str = "Invincible",
    publisher: str = "Image",
    issue_number: str = "1",
    grade_status: str = "raw",
    order_status: str = "received",
    release_status: str = "released",
    acquisition_cost: str = "5.00",
    ownership_state: str = "in_hand",
) -> dict[str, object]:
    return {
        "inventory_copy_id": inventory_copy_id,
        "metadata_identity_key": metadata_identity_key,
        "canonical_issue_id": canonical_issue_id,
        "title": title,
        "publisher": publisher,
        "issue_number": issue_number,
        "grade_status": grade_status,
        "order_status": order_status,
        "release_status": release_status,
        "acquisition_cost": Decimal(acquisition_cost),
        "ownership_state": ownership_state,
    }


def _snapshot(
    *,
    inventory_copy_id: int = 1,
    canonical_issue_id: int | None = 101,
    metadata_identity_key: str | None = "Image|Invincible|1|Cover A",
    snapshot_scope: str = "raw",
    grading_company: str | None = None,
    normalized_grade: str | None = None,
    currency_code: str = "USD",
    estimated_fmv: str = "100.00",
    confidence_bucket: str = "high",
    liquidity_bucket: str = "high",
    volatility_bucket: str = "low",
    stale_data: bool = False,
) -> MarketFmvSnapshot:
    return MarketFmvSnapshot(
        canonical_issue_id=canonical_issue_id,
        metadata_identity_key=metadata_identity_key,
        snapshot_scope=snapshot_scope,
        grading_company=grading_company,
        normalized_grade=normalized_grade,
        currency_code=currency_code,
        snapshot_date=_next_snapshot_date(),
        comp_count=2,
        valuation_method="median_recent_sales",
        estimated_fmv=Decimal(estimated_fmv),
        confidence_bucket=confidence_bucket,
        liquidity_bucket=liquidity_bucket,
        volatility_bucket=volatility_bucket,
        stale_data=stale_data,
        evidence_json={"seeded_for_test": True},
    )


def test_raw_inventory_attaches_to_exact_raw_snapshot(session: Session) -> None:
    snapshot = _snapshot(metadata_identity_key="Image|Invincible|1|Cover A", estimated_fmv="125.00")
    session.add(snapshot)
    session.commit()

    row = _row()
    before = dict(row)

    attachment = build_inventory_fmv_attachment(session, row=row, include_detail=False)

    assert row == before
    assert attachment.valuation_scope == "raw"
    assert attachment.current_market_fmv == Decimal("125.00")
    assert attachment.fmv_snapshot_id == snapshot.id
    assert attachment.fmv_currency_code == "USD"
    assert "recommend" not in attachment.model_dump_json()


def test_graded_inventory_attaches_to_matching_grade_snapshot(session: Session) -> None:
    raw_snapshot = _snapshot(metadata_identity_key="Image|Invincible|1|Cover A", snapshot_scope="raw", estimated_fmv="90.00")
    graded_snapshot = _snapshot(
        metadata_identity_key="Image|Invincible|1|Cover A",
        snapshot_scope="graded_by_grade",
        grading_company="CGC",
        normalized_grade="9.8",
        estimated_fmv="220.00",
    )
    session.add(raw_snapshot)
    session.add(graded_snapshot)
    session.commit()

    attachment = build_inventory_fmv_attachment(
        session,
        row=_row(grade_status="graded"),
        include_detail=False,
    )

    assert attachment.valuation_scope == "graded"
    assert attachment.current_market_fmv == Decimal("220.00")
    assert attachment.fmv_snapshot_id == graded_snapshot.id


def test_canonical_issue_match_fallback_uses_approved_suggestion(session: Session) -> None:
    cover = CoverImage(
        source_type="inventory",
        storage_path="/tmp/cover.jpg",
        mime_type="image/jpeg",
        sha256_hash="a" * 64,
        inventory_copy_id=None,
    )
    session.add(cover)
    session.commit()
    session.refresh(cover)
    assert cover.id is not None

    snapshot = _snapshot(
        canonical_issue_id=42,
        metadata_identity_key=None,
        snapshot_scope="raw",
        estimated_fmv="150.00",
    )
    session.add(snapshot)
    session.add(
        CanonicalIssueLinkSuggestion(
            cover_image_id=int(cover.id),
            inventory_copy_id=1,
            canonical_issue_id=42,
            suggestion_type="exact_identity_key",
            confidence_bucket="very_high",
            deterministic_score=0.99,
            evidence_json={"seeded_for_test": True},
            review_state="approved",
            reviewed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    attachment = build_inventory_fmv_attachment(
        session,
        row=_row(metadata_identity_key="Different|Identity|Key"),
        include_detail=False,
    )

    assert attachment.current_market_fmv == Decimal("150.00")
    assert attachment.valuation_scope == "raw"
    assert attachment.valuation_evidence_json["match_reason"] == "approved_canonical_issue"


def test_preorder_cancelled_and_missing_data_scopes(session: Session) -> None:
    preorder_attachment = build_inventory_fmv_attachment(
        session,
        row=_row(order_status="preordered", release_status="not_released_yet"),
        include_detail=False,
    )
    cancelled_attachment = build_inventory_fmv_attachment(
        session,
        row=_row(order_status="cancelled", release_status="unknown", ownership_state="cancelled"),
        include_detail=False,
    )
    missing_attachment = build_inventory_fmv_attachment(
        session,
        row=_row(metadata_identity_key="Missing|Snapshot|Key", canonical_issue_id=None),
        include_detail=False,
    )

    assert preorder_attachment.valuation_scope == "preorder_pending"
    assert preorder_attachment.current_market_fmv is None
    assert cancelled_attachment.valuation_scope == "cancelled_excluded"
    assert cancelled_attachment.current_market_fmv is None
    assert missing_attachment.valuation_scope == "no_market_data"
    assert missing_attachment.current_market_fmv is None


def test_low_confidence_and_stale_snapshots_surface_distinctly(session: Session) -> None:
    low_conf_snapshot = _snapshot(
        metadata_identity_key="Image|Invincible|1|Cover A",
        estimated_fmv="75.00",
        confidence_bucket="low",
    )
    stale_snapshot = _snapshot(
        metadata_identity_key="Image|Invincible|2|Cover A",
        estimated_fmv="80.00",
        stale_data=True,
    )
    session.add(low_conf_snapshot)
    session.add(stale_snapshot)
    session.commit()

    low_conf_attachment = build_inventory_fmv_attachment(
        session,
        row=_row(inventory_copy_id=2, metadata_identity_key="Image|Invincible|1|Cover A"),
        include_detail=False,
    )
    stale_attachment = build_inventory_fmv_attachment(
        session,
        row=_row(inventory_copy_id=3, metadata_identity_key="Image|Invincible|2|Cover A"),
        include_detail=False,
    )

    assert low_conf_attachment.valuation_scope == "low_confidence"
    assert low_conf_attachment.fmv_confidence_bucket == "low"
    assert stale_attachment.fmv_stale_data is True
    assert stale_attachment.valuation_scope == "raw"


def test_portfolio_summary_separates_currencies_and_duplicate_exposure(session: Session) -> None:
    usd_snapshot_one = _snapshot(
        inventory_copy_id=1,
        metadata_identity_key="Image|Invincible|1|Cover A",
        estimated_fmv="100.00",
        currency_code="USD",
    )
    usd_snapshot_two = _snapshot(
        inventory_copy_id=2,
        metadata_identity_key="Image|Invincible|2|Cover A",
        estimated_fmv="40.00",
        currency_code="USD",
    )
    cad_snapshot = _snapshot(
        inventory_copy_id=3,
        metadata_identity_key="Image|Invincible|3|Cover A",
        estimated_fmv="75.00",
        currency_code="CAD",
    )
    session.add(usd_snapshot_one)
    session.add(usd_snapshot_two)
    session.add(cad_snapshot)
    session.commit()

    rows = [
        _row(inventory_copy_id=1, metadata_identity_key="Image|Invincible|1|Cover A"),
        _row(inventory_copy_id=2, metadata_identity_key="Image|Invincible|2|Cover A"),
        _row(inventory_copy_id=3, metadata_identity_key="Image|Invincible|3|Cover A"),
    ]
    attachments = {
        1: build_inventory_fmv_attachment(session, row=rows[0], include_detail=False),
        2: build_inventory_fmv_attachment(session, row=rows[1], include_detail=False),
        3: build_inventory_fmv_attachment(session, row=rows[2], include_detail=False),
    }
    summary = summarize_inventory_fmv(
        rows,
        attachments,
        duplicate_group_keys={1: "dup-a", 2: "dup-a", 3: None},
        scope="owner",
        scope_user_id=1,
    )

    usd = next(item for item in summary.items if item.currency_code == "USD")
    cad = next(item for item in summary.items if item.currency_code == "CAD")

    assert usd.total_active_market_value == Decimal("140.00")
    assert usd.duplicate_group_total_value == Decimal("140.00")
    assert usd.duplicate_extra_copy_value == Decimal("40.00")
    assert usd.duplicate_value_exposure == Decimal("40.00")
    assert cad.total_active_market_value == Decimal("75.00")


def test_summary_does_not_convert_between_currencies(session: Session) -> None:
    usd_snapshot = _snapshot(
        inventory_copy_id=1,
        metadata_identity_key="Image|Invincible|1|Cover A",
        estimated_fmv="100.00",
        currency_code="USD",
    )
    cad_snapshot = _snapshot(
        inventory_copy_id=2,
        metadata_identity_key="Image|Invincible|2|Cover A",
        estimated_fmv="130.00",
        currency_code="CAD",
    )
    session.add(usd_snapshot)
    session.add(cad_snapshot)
    session.commit()

    summary = summarize_inventory_fmv(
        [
            _row(inventory_copy_id=1, metadata_identity_key="Image|Invincible|1|Cover A"),
            _row(inventory_copy_id=2, metadata_identity_key="Image|Invincible|2|Cover A"),
        ],
        {
            1: build_inventory_fmv_attachment(session, row=_row(inventory_copy_id=1, metadata_identity_key="Image|Invincible|1|Cover A"), include_detail=False),
            2: build_inventory_fmv_attachment(session, row=_row(inventory_copy_id=2, metadata_identity_key="Image|Invincible|2|Cover A"), include_detail=False),
        },
        scope="owner",
        scope_user_id=1,
    )

    assert [item.currency_code for item in summary.items] == ["CAD", "USD"]
    assert next(item for item in summary.items if item.currency_code == "USD").total_active_market_value == Decimal("100.00")
    assert next(item for item in summary.items if item.currency_code == "CAD").total_active_market_value == Decimal("130.00")


def test_inventory_fmv_routes_return_attached_market_value(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "inventory-fmv-route@example.com")
    create_order(
        client,
        token,
        items=[
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
                "raw_item_price": 5.00,
            }
        ],
    )
    inventory_copy = session.exec(select(InventoryCopy).order_by(InventoryCopy.id.desc())).first()
    assert inventory_copy is not None and inventory_copy.id is not None
    snapshot = _snapshot(
        metadata_identity_key=inventory_copy.metadata_identity_key,
        estimated_fmv="175.00",
    )
    session.add(snapshot)
    session.commit()

    response = client.get("/inventory-fmv", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["current_market_fmv"] == "175.00"
    assert payload["items"][0]["valuation_scope"] == "raw"

    summary = client.get("/portfolio-value/summary", headers=auth_headers(token))
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert summary_payload["items"][0]["total_active_market_value"] == "175.00"
