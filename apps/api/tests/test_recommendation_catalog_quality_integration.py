from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models import User
from app.services.unified_collector_intelligence import (
    generate_unified_collector_recommendations,
    list_latest_unified_collector_recommendations,
)
from test_inventory import register_and_login


def test_forward_catalog_excludes_trade_paperback(client: TestClient, session: Session) -> None:
    register_and_login(client, "fwd-quality@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "fwd-quality@example.com")).one().id or 0)
    today = date.today()
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Dead Head",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    session.add(
        ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid="fwd-dead-head-tp",
            series_id=int(series.id or 0),
            issue_number="TP",
            title="Dead Head TP",
            release_status="SCHEDULED",
            foc_date=today + timedelta(days=21),
            release_date=today + timedelta(days=45),
            cover_price=4.99,
        )
    )
    good_series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="Quality Forward",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(good_series)
    session.commit()
    session.refresh(good_series)
    session.add(
        ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid="fwd-quality-good",
            series_id=int(good_series.id or 0),
            issue_number="1",
            title="Quality Forward 1",
            release_status="SCHEDULED",
            foc_date=today + timedelta(days=14),
            release_date=today + timedelta(days=35),
            cover_price=4.99,
        )
    )
    session.commit()

    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id, limit=100)
    titles = {i.title for i in items}
    assert any("Quality Forward" in t for t in titles)
    assert not any("Dead Head" in t for t in titles)


def test_forward_catalog_excludes_kick_ass_compendium_tp(client: TestClient, session: Session) -> None:
    register_and_login(client, "fwd-kickass@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "fwd-kickass@example.com")).one().id or 0)
    today = date.today()
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Kick-Ass Compendium TP",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    session.add(
        ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid="fwd-kickass-tp",
            series_id=int(series.id or 0),
            issue_number="TP",
            title="Kick-Ass Compendium TP",
            release_status="SCHEDULED",
            foc_date=today + timedelta(days=21),
            release_date=today + timedelta(days=45),
            cover_price=19.99,
        )
    )
    session.commit()

    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id, limit=100)
    titles = {i.title for i in items}
    assert not any("Kick-Ass Compendium" in t for t in titles)
