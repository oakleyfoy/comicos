from __future__ import annotations

from sqlmodel import Session, select

from app.models.lunar_feed import LunarFeedRun
from app.schemas.lunar_feed import LunarCredentialStatusRead, LunarFeedDashboardRead, LunarFeedRunRead
from app.services.lunar_credentials import get_credential_status


def build_lunar_feed_dashboard(session: Session, *, owner_user_id: int) -> LunarFeedDashboardRead:
    status = get_credential_status()
    last = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.created_at.desc(), LunarFeedRun.id.desc())
    ).first()
    return LunarFeedDashboardRead(
        credential_status=LunarCredentialStatusRead(
            credential_available=status.credential_available,
            username_masked=status.username_masked,
        ),
        last_run=LunarFeedRunRead.model_validate(last) if last else None,
    )
