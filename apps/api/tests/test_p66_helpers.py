from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.buy_queue_intelligence import BuyQueueItem
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.services.buy_queue_service import build_buy_queue
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from test_buy_queue_intelligence import _seed_catalog, register_and_login


def seed_p66_owner(client: TestClient, session: Session, email: str) -> tuple[int, str]:
    from app.models import User

    token = register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    _seed_catalog(session, owner_id)
    ext = session.exec(
        select(ExternalCatalogIssue).where(ExternalCatalogIssue.series_name == "Buy Queue Series")
    ).first()
    assert ext is not None
    session.add(
        ExternalCatalogVariant(
            external_issue_id=int(ext.id or 0),
            cover_label="A",
            variant_name="Standard Cover",
            price=5.99,
        )
    )
    session.add(
        ExternalCatalogVariant(
            external_issue_id=int(ext.id or 0),
            cover_label="B",
            variant_name="Variant B",
            price=5.99,
        )
    )
    session.add(
        ExternalCatalogVariant(
            external_issue_id=int(ext.id or 0),
            cover_label="I",
            variant_name="Foil Cover",
            price=6.64,
            ratio_value=25,
            artist="Jane Artist",
        )
    )
    session.commit()
    build_buy_queue(session, owner_user_id=owner_id)
    for row in session.exec(select(BuyQueueItem).where(BuyQueueItem.owner_user_id == owner_id)).all():
        if not row.external_catalog_issue_id:
            row.external_catalog_issue_id = int(ext.id or 0)
    session.commit()
    return owner_id, token
