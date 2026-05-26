"""P38-01 portfolio registry deterministic behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, PortfolioExposureEvidence, PortfolioItem
from test_inventory import auth_headers, create_order, register_and_login


def _create_portfolio(client: TestClient, token: str, *, replay_key: str | None = None) -> dict:
    payload = {
        "name": "Core collection",
        "description": "test",
        "portfolio_type": "personal_collection",
        "replay_key": replay_key,
    }
    rsp = client.post("/portfolios", headers=auth_headers(token), json=payload)
    assert rsp.status_code in {200, 201}, rsp.text
    return rsp.json()


def test_portfolio_create_replay_safe(client: TestClient) -> None:
    token = register_and_login(client, "portfolio-replay@example.com")
    first = _create_portfolio(client, token, replay_key="pf-replay-1")
    second = _create_portfolio(client, token, replay_key="pf-replay-1")
    assert first["id"] == second["id"]
    assert first["name"] == second["name"]


def test_portfolio_item_active_uniqueness_and_soft_remove(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "portfolio-items@example.com")
    create_order(client, token)
    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    assert inv_rsp.status_code == 200, inv_rsp.text
    inv_id = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    pf = _create_portfolio(client, token, replay_key=None)
    pid = int(pf["id"])

    add = client.post(
        f"/portfolios/{pid}/items",
        headers=auth_headers(token),
        json={"inventory_item_id": inv_id, "allocation_role": "core_holding"},
    )
    assert add.status_code == 201, add.text
    dup = client.post(
        f"/portfolios/{pid}/items",
        headers=auth_headers(token),
        json={"inventory_item_id": inv_id, "allocation_role": "duplicate"},
    )
    assert dup.status_code == 409, dup.text

    items = client.get(f"/portfolios/{pid}/items", headers=auth_headers(token))
    assert items.status_code == 200
    body = items.json()
    assert body["total_items"] == 1
    item_id = int(body["items"][0]["id"])

    rem = client.post(f"/portfolios/{pid}/items/{item_id}/remove", headers=auth_headers(token))
    assert rem.status_code == 200, rem.text
    assert rem.json()["removed_at"] is not None

    rows = session.exec(select(PortfolioItem).where(PortfolioItem.id == item_id)).all()
    assert len(rows) == 1
    assert rows[0].removed_at is not None


def test_archive_portfolio(client: TestClient) -> None:
    token = register_and_login(client, "portfolio-archive@example.com")
    pf = _create_portfolio(client, token, replay_key="pf-arch-1")
    pid = int(pf["id"])
    rsp = client.post(f"/portfolios/{pid}/archive", headers=auth_headers(token))
    assert rsp.status_code == 200, rsp.text
    assert rsp.json()["status"] == "ARCHIVED"


def test_exposure_and_allocation_deterministic_replay_and_checksum(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "portfolio-engine@example.com")
    create_order(client, token)
    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    assert inv_rsp.status_code == 200, inv_rsp.text
    inv_pk = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv = session.get(InventoryCopy, inv_pk)
    assert inv is not None
    before_fmv = inv.current_fmv

    body = {"portfolio_id": None, "replay_key": "engine-replay-1"}
    r1 = client.post("/portfolio-exposures/generate", headers=auth_headers(token), json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/portfolio-exposures/generate", headers=auth_headers(token), json=body)
    assert r2.status_code == 200, r2.text
    assert r1.json()["generation_batch_checksum"] == r2.json()["generation_batch_checksum"]
    assert r1.json()["snapshots"] == r2.json()["snapshots"]

    a1 = client.post("/portfolio-allocations/generate", headers=auth_headers(token), json=body)
    assert a1.status_code == 201, a1.text
    a2 = client.post("/portfolio-allocations/generate", headers=auth_headers(token), json=body)
    assert a2.status_code == 200, a2.text
    assert a1.json()["allocation"]["checksum"] == a2.json()["allocation"]["checksum"]

    inv2 = session.get(InventoryCopy, inv.id)
    assert inv2 is not None
    assert inv2.current_fmv == before_fmv

    ev = session.exec(select(PortfolioExposureEvidence)).all()
    assert len(ev) >= 1


def test_ops_list_scoped(client: TestClient) -> None:
    token = register_and_login(client, "portfolio-ops@example.com")
    _create_portfolio(client, token, replay_key="ops-pf-1")
    headers = auth_headers(token)
    portfolios = client.get("/ops/portfolios", headers=headers)
    assert portfolios.status_code == 200, portfolios.text
    exposures = client.get("/ops/portfolio-exposures", headers=headers)
    assert exposures.status_code == 200, exposures.text


def test_stable_list_ordering_owner(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "portfolio-order@example.com")
    for idx in range(3):
        client.post(
            "/portfolios",
            headers=auth_headers(token),
            json={"name": f"P{idx}", "portfolio_type": "watchlist"},
        )
    lst = client.get("/portfolios", headers=auth_headers(token))
    assert lst.status_code == 200
    ids = [row["id"] for row in lst.json()["items"]]
    assert ids == sorted(ids)
