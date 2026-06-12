from __future__ import annotations

from decimal import Decimal

from app.models import DraftImport, User
from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse
from app.services.retailer_draft_import_prep import prepare_draft_import_for_retailer_confirm


def test_prepare_draft_import_fills_missing_publisher_and_issue(session) -> None:
    user = User(email="prep@example.com", password_hash="hash")
    session.add(user)
    session.commit()
    session.refresh(user)

    draft = DraftImport(
        user_id=int(user.id),
        raw_text="retailer order",
        parsed_payload_json=ParseOrderResponse(
            retailer="Midtown Comics",
            order_date=None,
            source_type="retailer_account",
            items=[
                AiDraftOrderItem(
                    title="Batman Gargoyle Of Gotham #4",
                    publisher=None,
                    issue_number=None,
                    quantity=1,
                    raw_item_price=Decimal("5.99"),
                    retailer_order_number="4272232",
                )
            ],
        ).model_dump(mode="json"),
        confidence_score=Decimal("1.0"),
        status="draft",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    prepare_draft_import_for_retailer_confirm(session, draft)
    payload = ParseOrderResponse.model_validate(draft.parsed_payload_json)
    assert payload.items[0].publisher == "Unknown Publisher"
    assert payload.items[0].issue_number == "4"
