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

    def _raise_buy(*args, **kwargs):
        raise AssertionError("marketplace acquisition must not run on collector home")

    monkeypatch.setattr(collector_home_service, "_COLLECTOR_HOME_ENABLE_ACQUISITION_SECTIONS", True)
    monkeypatch.setattr(collector_home_service, "list_acquisition_opportunities", _raise_buy)

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

    def _raise_budget(*args, **kwargs):
        raise AssertionError("budget dependency must not run on collector home")

    monkeypatch.setattr(collector_home_service, "load_personalization_context", _raise_budget)

    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["budget_status"]["status"] == "SKIPPED"


def test_collector_home_skips_sell_sections_without_sell_queue(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client, "p85-home-no-sell@example.com")

    def _should_not_run(*args, **kwargs):
        raise AssertionError("build_sell_queue must not run on collector home")

    monkeypatch.setattr(collector_home_service, "build_sell_queue", _should_not_run)

    resp = client.get("/api/v1/collector-home", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    sell = next(s for s in data["sections"] if s["key"] == "sell_alerts")
    grade = next(s for s in data["sections"] if s["key"] == "grade_alerts")
    assert sell["status"] == "SKIPPED"
    assert grade["status"] == "SKIPPED"
