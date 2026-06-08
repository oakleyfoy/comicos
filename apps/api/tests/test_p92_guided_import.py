from __future__ import annotations

from app.schemas.ai import ParseOrderResponse
from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.imports import DraftImportRead
from app.services.p92_guided_import_service import build_guided_import_review


def test_guided_review_splits_exceptions() -> None:
    payload = ParseOrderResponse.model_validate(
        {
            "retailer": "Test Shop",
            "order_date": "2026-01-01",
            "items": [
                {
                    "publisher": "Marvel",
                    "title": "Spider-Man",
                    "issue_number": "1",
                    "quantity": 1,
                    "raw_item_price": "4.99",
                    "catalog_match_matched": True,
                    "has_cover_image": True,
                },
                {
                    "publisher": "Image",
                    "title": "Unknown",
                    "issue_number": "1",
                    "quantity": 1,
                    "raw_item_price": "3.99",
                    "metadata_review_required": True,
                    "has_cover_image": False,
                },
            ],
            "warnings": [],
        }
    )
    draft_read = DraftImportRead(
        id=1,
        raw_text="x",
        parsed_payload_json=payload,
        confidence_score=Decimal("0.90"),
        status="draft",
        order_id=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cover_image_count=0,
    )
    review = build_guided_import_review(draft_read)
    assert review.auto_matched_count == 1
    assert review.exception_count == 1
    assert review.exceptions[0].item_index == 1
