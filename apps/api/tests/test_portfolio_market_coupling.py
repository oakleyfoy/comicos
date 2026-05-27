from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.models import (
    InventoryCopy,
    MarketAcquisitionScore,
    MarketAcquisitionSignal,
    Portfolio,
    PortfolioItem,
    PortfolioMarketCouplingEdge,
    PortfolioMarketCouplingEvidence,
    PortfolioMarketCouplingHistory,
    PortfolioMarketCouplingSnapshot,
    User,
)
from test_inventory import auth_headers, register_and_login
from test_market_scoring import _run_ingestion_and_normalization, _seed_issue_and_context


def _seed_active_portfolio_for_copy(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> None:
    pf = Portfolio(
        owner_user_id=owner_user_id,
        name="Seed Coupling Portfolio",
        portfolio_type="COLLECTION",
        status="ACTIVE",
        replay_key="pm-couple-seed",
    )
    session.add(pf)
    session.flush()
    session.add(
        PortfolioItem(
            portfolio_id=int(pf.id or 0),
            inventory_item_id=inventory_copy_id,
            allocation_role="CORE",
        ),
    )
    session.commit()


def test_portfolio_market_coupling_deterministic_replay_and_stable_edges(
    client: TestClient,
    session: Session,
) -> None:
    tok = register_and_login(client, "pm-couple-det@example.com")
    oid = int(session.exec(select(User.id).where(User.email == "pm-couple-det@example.com")).one())
    _run_ingestion_and_normalization(client, tok)
    _seed_issue_and_context(session, owner_user_id=oid)

    ic_id = session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == oid)).first()
    assert ic_id is not None
    inventory_copy_id = int(ic_id[0] if isinstance(ic_id, tuple) else ic_id)
    _seed_active_portfolio_for_copy(session, owner_user_id=oid, inventory_copy_id=inventory_copy_id)

    score_run = client.post("/market-scoring/run", headers=auth_headers(tok), json={})
    assert score_run.status_code == 200, score_run.text
    signal_run = client.post("/market-signals/generate", headers=auth_headers(tok), json={})
    assert signal_run.status_code == 200, signal_run.text
    opp_run = client.post("/market-opportunities/generate", headers=auth_headers(tok), json={})
    assert opp_run.status_code == 200, opp_run.text

    scores_before = len(session.exec(select(MarketAcquisitionScore)).all())
    signals_before = len(session.exec(select(MarketAcquisitionSignal)).all())

    gen1 = client.post("/market-portfolio-coupling/generate", headers=auth_headers(tok), json={})
    assert gen1.status_code == 200, gen1.text
    b1 = gen1.json()
    assert b1["replayed"] is False
    snap_id = int(b1["snapshot"]["id"])
    chk1 = b1["snapshot"]["snapshot_checksum"]

    edges1_resp = client.get("/market-portfolio-coupling/edges", headers=auth_headers(tok))
    assert edges1_resp.status_code == 200
    ids1 = [row["market_candidate_id"] for row in edges1_resp.json()["items"]]

    gen2 = client.post("/market-portfolio-coupling/generate", headers=auth_headers(tok), json={})
    assert gen2.status_code == 200, gen2.text
    b2 = gen2.json()
    assert b2["replayed"] is True
    assert b2["snapshot"]["id"] == snap_id
    assert b2["snapshot"]["snapshot_checksum"] == chk1

    hist = session.exec(
        select(PortfolioMarketCouplingHistory).where(PortfolioMarketCouplingHistory.owner_user_id == oid),
    ).all()
    assert len(hist) == 1

    ev_rows = session.exec(
        select(PortfolioMarketCouplingEvidence).where(
            PortfolioMarketCouplingEvidence.portfolio_market_coupling_snapshot_id == snap_id,
        ),
    ).all()
    assert len(ev_rows) == 6

    assert len(session.exec(select(MarketAcquisitionScore)).all()) == scores_before
    assert len(session.exec(select(MarketAcquisitionSignal)).all()) == signals_before

    edges_db = session.exec(
        select(PortfolioMarketCouplingEdge).where(
            PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id == snap_id,
        ).order_by(col(PortfolioMarketCouplingEdge.id).asc()),
    ).all()
    types_order = [(e.market_normalized_candidate_id, e.coupling_type, e.coupling_score) for e in edges_db]

    edges2_resp = client.get("/market-portfolio-coupling/edges", headers=auth_headers(tok))
    assert edges2_resp.status_code == 200
    ids2 = [row["market_candidate_id"] for row in edges2_resp.json()["items"]]
    assert ids1 == ids2
    detail = client.get(f"/market-portfolio-coupling/{snap_id}", headers=auth_headers(tok))
    assert detail.status_code == 200, detail.text
    d_edges = [(e["market_candidate_id"], e["coupling_type"], e["coupling_score"]) for e in detail.json()["edges"]]
    assert d_edges == types_order


def test_portfolio_market_coupling_owner_ops_isolation(monkeypatch, client: TestClient, session: Session) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "pm-couple-ops@example.com")

    tok_owner = register_and_login(client, "pm-couple-own@example.com")
    tok_peer = register_and_login(client, "pm-couple-peer@example.com")
    tok_ops = register_and_login(client, "pm-couple-ops@example.com")

    oid = int(session.exec(select(User.id).where(User.email == "pm-couple-own@example.com")).one())
    _run_ingestion_and_normalization(client, tok_owner)
    _seed_issue_and_context(session, owner_user_id=oid)
    ic_row = session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == oid)).first()
    cid = int(ic_row[0] if isinstance(ic_row, tuple) else ic_row)
    _seed_active_portfolio_for_copy(session, owner_user_id=oid, inventory_copy_id=cid)

    assert client.post("/market-scoring/run", headers=auth_headers(tok_owner), json={}).status_code == 200
    assert client.post("/market-signals/generate", headers=auth_headers(tok_owner), json={}).status_code == 200
    assert client.post("/market-opportunities/generate", headers=auth_headers(tok_owner), json={}).status_code == 200
    assert client.post("/market-portfolio-coupling/generate", headers=auth_headers(tok_owner), json={}).status_code == 200

    snap_rows = session.exec(select(PortfolioMarketCouplingSnapshot).where(PortfolioMarketCouplingSnapshot.owner_user_id == oid)).all()
    coup_id = int(snap_rows[0].id or 0)

    peer_detail = client.get(f"/market-portfolio-coupling/{coup_id}", headers=auth_headers(tok_peer))
    assert peer_detail.status_code == 404

    ops_list = client.get(f"/ops/market-portfolio-coupling?owner_user_id={oid}", headers=auth_headers(tok_ops))
    assert ops_list.status_code == 200
    hits = [int(it["id"]) for it in ops_list.json().get("items", [])]
    assert coup_id in hits
