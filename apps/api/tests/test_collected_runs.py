from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.collected_run import CollectedRun
from app.models.release_intelligence import ReleaseSeries
from app.services.collected_run_engine import (
    RECENT_OWNERSHIP_DAYS,
    determine_run_status,
    generate_collected_runs,
)
from app.services.collected_runs import persist_collected_runs
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _battle_beast_items(numbers: list[str]) -> list[dict]:
    return [
        {
            "title": "Battle Beast",
            "publisher": "Image",
            "issue_number": num,
            "cover_name": "Cover A",
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 1,
            "raw_item_price": 5.00,
        }
        for num in numbers
    ]


def _absolute_batman_items(numbers: list[str]) -> list[dict]:
    return [
        {
            "title": "Absolute Batman",
            "publisher": "DC",
            "issue_number": num,
            "cover_name": "Cover A",
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 1,
            "raw_item_price": 5.00,
        }
        for num in numbers
    ]


def test_run_grouping_and_latest_issue(client: TestClient, session: Session) -> None:
    email = "cr-group@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items([str(n) for n in range(1, 16)]))
    create_order(client, token, items=_absolute_batman_items([str(n) for n in range(1, 21)]))

    runs = generate_collected_runs(session, owner_user_id=owner_id)
    by_series = {r.series_name: r for r in runs}
    assert by_series["Battle Beast"].total_owned_issues == 15
    assert by_series["Battle Beast"].latest_owned_issue == "15"
    assert by_series["Absolute Batman"].total_owned_issues == 20
    assert by_series["Absolute Batman"].latest_owned_issue == "20"


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "cr-a@example.com")
    token_b = register_and_login(client, "cr-b@example.com")
    create_order(client, token_a, items=_battle_beast_items(["1", "2", "3"]))
    client.get("/api/v1/collected-runs/latest", headers=auth_headers(token_a))
    b_list = client.get("/api/v1/collected-runs", headers=auth_headers(token_b))
    assert b_list.status_code == 200
    assert b_list.json()["data"]["items"] == []


def test_status_active_for_recent_inventory(client: TestClient, session: Session) -> None:
    email = "cr-active@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "3"]))
    runs = generate_collected_runs(session, owner_user_id=owner_id)
    assert len(runs) == 1
    assert runs[0].run_status == "ACTIVE"


def test_status_complete_for_ended_release_series(client: TestClient, session: Session) -> None:
    email = "cr-complete@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "3"]))
    session.add(
        ReleaseSeries(
            owner_user_id=owner_id,
            publisher="Image",
            series_name="Battle Beast",
            series_type="LIMITED",
            status="ENDED",
        )
    )
    session.commit()
    runs = generate_collected_runs(session, owner_user_id=owner_id)
    assert runs[0].run_status == "COMPLETE"


def test_status_inactive_for_stale_ownership(client: TestClient, session: Session) -> None:
    email = "cr-inactive@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2"]))
    stale = datetime.now(timezone.utc) - timedelta(days=RECENT_OWNERSHIP_DAYS + 30)
    for copy in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all():
        copy.received_at = stale
        copy.created_at = stale
        session.add(copy)
    session.commit()
    runs = generate_collected_runs(session, owner_user_id=owner_id)
    assert runs[0].run_status == "INACTIVE"


def test_determine_run_status_rules() -> None:
    now = datetime(2026, 5, 30, tzinfo=timezone.utc)
    recent = now - timedelta(days=30)
    old = now - timedelta(days=400)
    assert (
        determine_run_status(
            release_status=None,
            series_status="probable_ongoing_series",
            last_activity_at=recent,
            total_owned_issues=3,
            now=now,
        )
        == "ACTIVE"
    )
    assert (
        determine_run_status(
            release_status=None,
            series_status="probable_ongoing_series",
            last_activity_at=old,
            total_owned_issues=3,
            now=now,
        )
        == "INACTIVE"
    )
    assert (
        determine_run_status(
            release_status="ENDED",
            series_status="probable_ongoing_series",
            last_activity_at=recent,
            total_owned_issues=3,
            now=now,
        )
        == "COMPLETE"
    )


def test_persist_idempotent_and_api(client: TestClient, session: Session) -> None:
    email = "cr-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    first = persist_collected_runs(session, owner_user_id=owner_id)
    assert first == 1
    second = persist_collected_runs(session, owner_user_id=owner_id)
    assert second == 0
    rows = session.exec(select(CollectedRun).where(CollectedRun.owner_user_id == owner_id)).all()
    assert len(rows) == 1

    latest = client.get("/api/v1/collected-runs/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    item = latest.json()["data"]["items"][0]
    assert item["series_name"] == "Battle Beast"
    assert item["latest_owned_issue"] == "5"
    assert item["total_owned_issues"] == 4

    summary = client.get("/api/v1/collected-runs/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert summary.json()["data"]["total_runs"] == 1
