from sqlmodel import Session, select

from app.models import User
from app.models.p92_import_line_cover import P92ImportLineCoverResolution
from app.schemas.ai import AiDraftOrderItem
from app.schemas.imports import ManualDraftImportCreate
from app.services.import_line_cover_resolution_service import persist_parse_order_line_cover_resolutions
from app.services.imports import confirm_import_for_user, create_manual_import_for_user


def test_persist_and_attach_line_cover_resolution(session: Session) -> None:
    user = User(email="cover-line@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    draft = create_manual_import_for_user(
        session,
        current_user=user,
        payload=ManualDraftImportCreate.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-06-01",
                "source_type": "manual_draft",
                "items": [
                    {
                        "publisher": "Image",
                        "title": "Star",
                        "issue_number": "1",
                        "quantity": 1,
                        "raw_item_price": "3.99",
                        "cover_source": "LOCG",
                        "cover_confidence": 0.9,
                        "variant_confidence": 0.88,
                        "cover_image_url": "https://example.com/star.jpg",
                        "has_cover_image": True,
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            }
        ),
    )
    assert draft.id is not None

    item = AiDraftOrderItem.model_validate(
        {
            "publisher": "Image",
            "title": "Star",
            "issue_number": "1",
            "quantity": 1,
            "raw_item_price": "3.99",
            "cover_source": "LOCG",
            "cover_confidence": 0.9,
            "variant_confidence": 0.88,
            "cover_image_url": "https://example.com/star.jpg",
            "cover_thumbnail_url": "https://example.com/star.jpg",
            "has_cover_image": True,
        }
    )
    persist_parse_order_line_cover_resolutions(
        session,
        owner_user_id=user.id,
        draft_import_id=draft.id,
        items=[item],
    )
    session.commit()

    row = session.exec(
        select(P92ImportLineCoverResolution).where(
            P92ImportLineCoverResolution.draft_import_id == draft.id,
            P92ImportLineCoverResolution.line_index == 0,
        )
    ).one()
    assert row.cover_url == "https://example.com/star.jpg"
    assert row.cover_source == "LOCG"

    confirm = confirm_import_for_user(session, user, draft.id)
    session.expire_all()
    row = session.get(P92ImportLineCoverResolution, row.id)
    assert row is not None
    assert row.inventory_copy_id is not None
    assert confirm.order_id > 0
