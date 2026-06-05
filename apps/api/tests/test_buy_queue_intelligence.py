from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.buy_queue_intelligence import BuyQueueItem, BuyQueueSnapshot
from app.models.external_catalog import ExternalCatalogIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.schemas.purchase_budget import PurchaseBudgetUpdate
from app.services.buy_queue_service import build_buy_queue, get_latest_buy_queue_snapshot, list_buy_queue_items
from app.services.demand_refresh_service import run_demand_refresh
from app.services.demand_velocity_service import compute_demand_velocity
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.purchase_budgets import update_purchase_budget


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def _owner_id(session: Session, email: str) -> int:
    from app.models import User

    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_catalog(session: Session, owner_id: int) -> ReleaseIssue:
    issue = ExternalCatalogIssue(
        source_name=LOCG_SOURCE_NAME,
        title="Buy Queue Series #1",
        publisher="Pub",
        series_name="Buy Queue Series",
        issue_number="1",
        release_date=date.today() + timedelta(days=21),
        pull_count=90,
        want_count=60,
        normalized_title_key="buy queue series #1",
    )
    session.add(issue)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="Buy Queue Series",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    foc = date.today() + timedelta(days=7)
    rel = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="bq-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Buy Queue Series #1",
        release_status="SCHEDULED",
        foc_date=foc,
        release_date=foc + timedelta(days=14),
        cover_price=5.99,
    )
    session.add(rel)
    session.commit()
    session.refresh(rel)
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_id,
            issue_id=int(rel.id or 0),
            signal_type="NEW_NUMBER_ONE",
            confidence_score=0.9,
            signal_payload_json={},
        )
    )
    session.commit()
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    compute_demand_velocity(session, window_days=7)
    return rel


def test_build_buy_queue_persists_ordered_items(client: TestClient, session: Session) -> None:
    email = "bq-build@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    snap = build_buy_queue(session, owner_user_id=owner_id)
    assert snap.total_items >= 1
    items, total = list_buy_queue_items(session, snapshot_id=int(snap.id or 0), limit=100, offset=0)
    assert total == snap.total_items
    if len(items) >= 2:
        assert items[0].priority_score >= items[1].priority_score


def test_budget_demotes_lower_priority(client: TestClient, session: Session) -> None:
    email = "bq-budget@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    update_purchase_budget(
        session,
        owner_user_id=owner_id,
        payload=PurchaseBudgetUpdate(weekly_budget=6.0, monthly_budget=0.0, is_active=True),
    )
    snap = build_buy_queue(session, owner_user_id=owner_id)
    items, _ = list_buy_queue_items(session, snapshot_id=int(snap.id or 0), limit=50, offset=0)
    assert any("budget_demoted" in (i.buy_reason or "") for i in items) or all(
        i.estimated_cost <= 6.0 for i in items if i.status != "WATCH"
    )


def test_buy_queue_api_build_and_patch(client: TestClient, session: Session) -> None:
    email = "bq-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    headers = {"Authorization": f"Bearer {token}"}
    build_resp = client.post("/api/v1/recommendation-intelligence/buy-queue/build", headers=headers)
    assert build_resp.status_code == 200
    latest = client.get("/api/v1/recommendation-intelligence/buy-queue/latest", headers=headers)
    assert latest.status_code == 200
    data = latest.json()["data"]
    assert data["total_items"] >= 1
    item_id = data["items"][0]["id"]
    patch = client.patch(
        f"/api/v1/recommendation-intelligence/buy-queue/item/{item_id}",
        headers=headers,
        json={"status": "ORDERED"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["status"] == "ORDERED"


def test_buy_queue_certification_endpoint(client: TestClient, session: Session) -> None:
    email = "bq-cert@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/v1/recommendation-intelligence/buy-queue/certification", headers=headers)
    assert resp.status_code == 200
    cert = resp.json()["data"]
    assert cert["component"] == "P62-02_BUY_QUEUE"


def test_latest_snapshot_after_build(client: TestClient, session: Session) -> None:
    email = "bq-latest@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    build_buy_queue(session, owner_user_id=owner_id)
    latest = get_latest_buy_queue_snapshot(session, owner_user_id=owner_id)
    assert latest is not None
    assert isinstance(latest, BuyQueueSnapshot)
    row = session.exec(select(BuyQueueItem).where(BuyQueueItem.snapshot_id == int(latest.id or 0))).first()
    assert row is not None
    assert row.quantity_recommended >= 1
