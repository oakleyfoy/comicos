"""P38-02 duplicate & consolidation intelligence deterministic behavior."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy
from test_inventory import auth_headers, create_order, register_and_login


def test_duplicate_cluster_deterministic_replay_and_no_fmv_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "dup-replay@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 4.5,
            },
        ],
    )

    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    assert inv_rsp.status_code == 200, inv_rsp.text
    pk = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv = session.get(InventoryCopy, pk)
    assert inv is not None
    before_fmv = inv.current_fmv

    body = {"replay_key": "dup-replay-key-1", "snapshot_date": str(date(2026, 5, 27))}
    g1 = client.post("/duplicate-clusters/generate", headers=auth_headers(token), json=body)
    assert g1.status_code in {200, 201}, g1.text
    g2 = client.post("/duplicate-clusters/generate", headers=auth_headers(token), json=body)
    assert g2.status_code == 200, g2.text
    assert g1.json()["generation_batch_checksum"] == g2.json()["generation_batch_checksum"]

    clusters = sorted(g1.json()["clusters"], key=lambda r: r["cluster_key"])
    ct = sorted({str(c["cluster_type"]) for c in clusters})
    assert "exact_issue" in ct or "variant_family" in ct

    inv_after = session.get(InventoryCopy, pk)
    assert inv_after is not None
    assert inv_after.current_fmv == before_fmv


def test_duplicate_cluster_stable_order(client: TestClient) -> None:
    token = register_and_login(client, "dup-order@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "2",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 4.5,
            },
        ],
    )
    body = {"replay_key": "dup-order-rk", "snapshot_date": str(date(2026, 5, 27))}
    r1 = client.post("/duplicate-clusters/generate", headers=auth_headers(token), json=body)
    r2 = client.post("/duplicate-clusters/generate", headers=auth_headers(token), json=body)
    assert r1.json()["clusters"] == r2.json()["clusters"]


def test_duplicate_ops_list(client: TestClient) -> None:
    token = register_and_login(client, "dup-ops@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "3",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 4.5,
            },
        ],
    )
    client.post(
        "/duplicate-clusters/generate",
        headers=auth_headers(token),
        json={"replay_key": "dup-ops-rk", "snapshot_date": str(date(2026, 5, 27))},
    )
    headers = auth_headers(token)
    clusters = client.get("/ops/duplicate-clusters", headers=headers)
    assert clusters.status_code == 200, clusters.text
    items = client.get("/ops/duplicate-cluster-items", headers=headers)
    assert items.status_code == 200, items.text
    recos = client.get("/ops/duplicate-consolidation-recommendations", headers=headers)
    assert recos.status_code == 200, recos.text
    hist = client.get("/ops/duplicate-history", headers=headers)
    assert hist.status_code == 200, hist.text


def test_duplicate_supersedes_prior_recommendations(client: TestClient, session: Session) -> None:
    from app.models import DuplicateConsolidationRecommendation

    token = register_and_login(client, "dup-super@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "4",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 4.5,
            },
        ],
    )
    h = auth_headers(token)
    client.post("/duplicate-clusters/generate", headers=h, json={"replay_key": "k1", "snapshot_date": str(date(2026, 5, 20))})
    client.post("/duplicate-clusters/generate", headers=h, json={"replay_key": "k2", "snapshot_date": str(date(2026, 5, 21))})
    active = session.exec(select(DuplicateConsolidationRecommendation).where(DuplicateConsolidationRecommendation.recommendation_status == "ACTIVE")).all()
    superseded = session.exec(
        select(DuplicateConsolidationRecommendation).where(DuplicateConsolidationRecommendation.recommendation_status == "SUPERSEDED")
    ).all()
    assert len(active) >= 1
    assert len(superseded) >= 1
