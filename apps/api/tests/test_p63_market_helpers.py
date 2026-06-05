"""Shared P63 test helpers."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.want_list import WantList, WantListItem
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from test_inventory import auth_headers, create_order, register_and_login


def owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def seed_p63_owner(client: TestClient, session: Session, email: str) -> int:
    token = register_and_login(client, email)
    oid = owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Market Test Series",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 10.00,
            }
        ],
    )
    for copy in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == oid)).all():
        copy.current_fmv = Decimal("25.00")
        session.add(copy)
    wl = WantList(owner_user_id=oid, name="Test Want", description="")
    session.add(wl)
    session.commit()
    session.refresh(wl)
    session.add(
        WantListItem(
            want_list_id=int(wl.id or 0),
            owner_user_id=oid,
            publisher="Marvel",
            series_name="Missing Run",
            issue_number="99",
            priority="HIGH",
            status="WANTED",
        )
    )
    series = ReleaseSeries(
        owner_user_id=oid,
        publisher="Marvel",
        series_name="Missing Run",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    foc = date.today() + timedelta(days=14)
    session.add(
        ReleaseIssue(
            owner_user_id=oid,
            release_uuid=f"p63-{email}",
            series_id=int(series.id or 0),
            issue_number="99",
            title="Missing Run #99",
            release_status="SCHEDULED",
            foc_date=foc,
            release_date=foc + timedelta(days=14),
        )
    )
    session.commit()
    return oid


def auth(token: str) -> dict[str, str]:
    return auth_headers(token)
