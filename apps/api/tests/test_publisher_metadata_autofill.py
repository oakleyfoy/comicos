from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.asset_ledger import CanonicalSeries
from app.schemas.ai import ParseOrderResponse
from app.services.canonical_series import compute_series_key
from app.services.metadata_enrichment import enrich_parse_order_metadata
from app.db.session import get_engine
from app.services.publisher_metadata_autofill import resolve_blank_publisher


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _blank_publisher_item(*, title: str, issue_number: str = "1") -> ParseOrderResponse:
    return ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": Decimal("0.00"),
            "tax_amount": Decimal("0.00"),
            "items": [
                {
                    "publisher": None,
                    "title": title,
                    "issue_number": issue_number,
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        }
    )


def test_resolve_blank_publisher_from_release_catalog(client: TestClient) -> None:
    email = "pub-autofill-catalog@example.com"
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    with Session(get_engine()) as session:
        owner_user_id = _owner_id(session, email)

        series = ReleaseSeries(
            owner_user_id=owner_user_id,
            publisher="Marvel",
            series_name="Autofill Catalog Series",
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(series)
        session.commit()
        session.refresh(series)
        session.add(
            ReleaseIssue(
                owner_user_id=owner_user_id,
                release_uuid="pub-autofill-catalog-1",
                series_id=int(series.id or 0),
                issue_number="1",
                title="Autofill Catalog Series #1",
                release_status="SCHEDULED",
                release_date=date.today() + timedelta(days=7),
            )
        )
        session.commit()

        candidate = resolve_blank_publisher(
            session,
            owner_user_id=owner_user_id,
            canonical_series="Autofill Catalog Series",
            canonical_issue="1",
            raw_text="Autofill Catalog Series #1",
        )
    assert candidate is not None
    assert candidate.publisher == "Marvel"
    assert candidate.source == "metadata_catalog"
    assert candidate.confidence >= 0.84


def test_resolve_blank_publisher_from_canonical_series_registry(client: TestClient) -> None:
    with Session(get_engine()) as session:
        session.add(
            CanonicalSeries(
                canonical_title="Registry Only Title",
                canonical_publisher="Image",
                series_key=compute_series_key("Image", "Registry Only Title"),
                is_active=True,
            )
        )
        session.commit()

        candidate = resolve_blank_publisher(
            session,
            owner_user_id=None,
            canonical_series="Registry Only Title",
            canonical_issue="1",
            raw_text="Registry Only Title #1",
        )
    assert candidate is not None
    assert candidate.publisher == "Image"
    assert candidate.source == "metadata_registry"


def test_enrich_blank_publisher_sets_autofill_source(client: TestClient) -> None:
    email = "pub-autofill-enrich@example.com"
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    with Session(get_engine()) as session:
        owner_user_id = _owner_id(session, email)

        series = ReleaseSeries(
            owner_user_id=owner_user_id,
            publisher="DC",
            series_name="Autofill Enrich Series",
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(series)
        session.commit()
        session.refresh(series)
        session.add(
            ReleaseIssue(
                owner_user_id=owner_user_id,
                release_uuid="pub-autofill-enrich-1",
                series_id=int(series.id or 0),
                issue_number="1",
                title="Autofill Enrich Series #1",
                release_status="SCHEDULED",
                release_date=date.today() + timedelta(days=7),
            )
        )
        session.commit()

        enriched = enrich_parse_order_metadata(
            _blank_publisher_item(title="Autofill Enrich Series"),
            session=session,
            owner_user_id=owner_user_id,
            raw_text="Autofill Enrich Series #1",
        )
    item = enriched.items[0]
    assert item.publisher == "DC"
    assert item.metadata_autofill_source == "metadata_catalog"
    assert item.publisher_autofill_confidence is not None
    assert item.publisher_autofill_confidence >= 0.84
    assert item.metadata_review_required is False


def test_enrich_blank_publisher_title_heuristic_sets_metadata_ai(client: TestClient) -> None:
    with Session(get_engine()) as session:
        enriched = enrich_parse_order_metadata(
            _blank_publisher_item(title="Batman"),
            session=session,
            raw_text="Batman #1 preorder",
        )
    item = enriched.items[0]
    assert item.publisher == "DC"
    assert item.metadata_autofill_source == "metadata_ai"
    assert item.metadata_review_required is False
