from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

import app.services.collector_home_service as collector_home_service
from app.services.collector_home_service import build_collector_home
from test_inventory import auth_headers, register_and_login


def test_collector_home_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-home@example.com")
    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "headline" in data
    assert len(data["sections"]) >= 8
    assert "budget_status" in data


def test_collector_home_empty_inventory_hint(client: TestClient, session: Session) -> None:
    register_and_login(client, "p85-home-empty@example.com")
    from sqlmodel import select
    from app.models import User

    owner_id = int(session.exec(select(User).where(User.email == "p85-home-empty@example.com")).one().id or 0)
    home = build_collector_home(session, owner_user_id=owner_id)
    assert home.headline


def test_collector_home_returns_200_without_calling_acquisition(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "p85-home-fail-buy@example.com")

    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    buy = next(s for s in data["sections"] if s["key"] == "buy_alerts")
    assert buy["status"] == "SKIPPED"
    assert buy["items"] == []
    deals = next(s for s in data["sections"] if s["key"] == "marketplace_deals")
    assert deals["status"] == "SKIPPED"
    assert "headline" in data


def test_collector_home_returns_200_without_calling_budget_dependency(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client, "p85-home-fail-budget@example.com")

    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["budget_status"]["status"] == "SKIPPED"


def test_collector_home_uses_cached_foc_snapshot_only(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-home-foc-cache@example.com")
    from sqlmodel import select
    from app.models import User
    from app.models.p74_foc_purchase import P74FocAlert, P74FocRecommendationSnapshot

    owner_id = int(session.exec(select(User).where(User.email == "p85-home-foc-cache@example.com")).one().id or 0)
    snap = P74FocRecommendationSnapshot(
        owner_user_id=owner_id,
        snapshot_date=__import__("datetime").date.today(),
        foc_this_week=1,
        foc_next_week=2,
        foc_within_30_days=3,
    )
    session.add(snap)
    session.flush()
    session.add(
        P74FocAlert(
            owner_user_id=owner_id,
            snapshot_id=int(snap.id or 0),
            release_issue_id=1,
            alert_type="FOC_THIS_WEEK",
            title="Cached FOC alert",
            message="Cached only",
            priority_score=99,
        )
    )
    session.commit()

    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    foc = next(s for s in resp.json()["data"]["sections"] if s["key"] == "foc_alerts")
    assert foc["status"] == "OK"
    assert foc["items"][0]["title"] == "Cached FOC alert"


def test_collector_home_skips_sell_sections_without_sell_queue(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client, "p85-home-no-sell@example.com")

    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    sell = next(s for s in data["sections"] if s["key"] == "sell_alerts")
    grade = next(s for s in data["sections"] if s["key"] == "grade_alerts")
    assert sell["status"] == "SKIPPED"
    assert grade["status"] == "SKIPPED"


def test_collector_home_sections_include_indicator_fields(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-home-indicators@example.com")
    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    for section in resp.json()["data"]["sections"]:
        assert "indicator_status" in section
        assert section["indicator_status"] in {"HAS_ITEMS", "EMPTY", "STALE", "UNKNOWN", "ERROR", None}


def test_collector_home_foc_indicator_has_items_with_cached_alerts(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-home-foc-ind@example.com")
    from sqlmodel import select
    from app.models import User
    from app.models.p74_foc_purchase import P74FocAlert, P74FocRecommendationSnapshot

    owner_id = int(session.exec(select(User).where(User.email == "p85-home-foc-ind@example.com")).one().id or 0)
    snap = P74FocRecommendationSnapshot(
        owner_user_id=owner_id,
        snapshot_date=__import__("datetime").date.today(),
        foc_this_week=0,
        foc_next_week=0,
        foc_within_30_days=0,
    )
    session.add(snap)
    session.flush()
    session.add(
        P74FocAlert(
            owner_user_id=owner_id,
            snapshot_id=int(snap.id or 0),
            release_issue_id=1,
            alert_type="FOC_THIS_WEEK",
            title="Indicator FOC",
            message="Cached",
            priority_score=1,
        )
    )
    session.commit()

    foc = next(s for s in client.get("/api/v1/collector-home", headers=auth_headers(token)).json()["data"]["sections"] if s["key"] == "foc_alerts")
    assert foc["indicator_status"] == "HAS_ITEMS"
    assert foc["count"] == 1


def test_collector_home_does_not_call_build_sell_queue(client: TestClient, monkeypatch) -> None:
    token = register_and_login(client, "p85-home-no-sell-svc@example.com")

    def _fail(*_args, **_kwargs):
        raise AssertionError("build_sell_queue must not run on collector home")

    import app.services.p78_sell_queue_service as sell_svc

    monkeypatch.setattr(sell_svc, "build_sell_queue", _fail)
    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200


def test_collector_home_indicator_lookup_error_does_not_fail_home(client: TestClient, monkeypatch) -> None:
    token = register_and_login(client, "p85-home-ind-err@example.com")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("count failed")

    monkeypatch.setattr(collector_home_service, "_count_hold_sell_recommendations", _boom)
    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    sell = next(s for s in resp.json()["data"]["sections"] if s["key"] == "sell_alerts")
    assert sell["indicator_status"] == "ERROR"
