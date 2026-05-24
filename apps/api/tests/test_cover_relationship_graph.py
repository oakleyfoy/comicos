import test_cover_image_match_candidates as mcc
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import CoverImage, InventoryCopy, MetadataAudit


def test_cover_relationship_graph_includes_approved_edges(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-approved@example.com")
    headers = mcc.auth_headers(token)
    shared_image = mcc.make_png_bytes(color=(50, 50, 200))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text=shared_text
    )
    _, target_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text=shared_text
    )
    mcc._prepare_cover_signals(client, token, source_cover_id)
    mcc._prepare_cover_signals(client, token, target_cover_id)
    gen = client.post(f"/cover-images/{source_cover_id}/generate-match-candidates", headers=headers)
    assert gen.status_code == 200
    combined = mcc._candidate_by_type(gen.json(), "combined_similarity")
    decision = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "source_match_candidate_id": combined["id"],
            "decision_type": "approved_link",
            "relationship_type": "same_cover",
            "decision_reason": "Test approved edge.",
        },
    )
    assert decision.status_code == 200

    r1 = client.get(f"/cover-images/{source_cover_id}/relationship-graph", headers=headers)
    r2 = client.get(f"/cover-relationship-graph?cover_image_id={source_cover_id}", headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    body1 = r1.json()
    body2 = r2.json()
    assert body1 == body2
    assert len(body1["edges"]) == 1
    edge = body1["edges"][0]
    assert edge["decision_type"] == "approved_link"
    assert edge["display_lane"] == "strong"
    assert edge["source_cover_image_id"] == source_cover_id
    assert edge["candidate_cover_image_id"] == target_cover_id
    node_ids_sorted = sorted(n["cover_image_id"] for n in body1["nodes"])
    assert node_ids_sorted == sorted([source_cover_id, target_cover_id])


def test_cover_relationship_graph_rejected_unrelated_blocked_lane(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-rejected@example.com")
    headers = mcc.auth_headers(token)
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(100, 20, 140)),
        raw_text=shared_text,
    )
    _, target_cover_id = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(100, 20, 140)),
        raw_text=shared_text,
    )
    mcc._prepare_cover_signals(client, token, source_cover_id)
    mcc._prepare_cover_signals(client, token, target_cover_id)
    gen = client.post(f"/cover-images/{source_cover_id}/generate-match-candidates", headers=headers)
    assert gen.status_code == 200
    combined = mcc._candidate_by_type(gen.json(), "combined_similarity")
    assert (
        client.post(
            "/cover-link-decisions",
            headers=headers,
            json={
                "source_cover_image_id": source_cover_id,
                "candidate_cover_image_id": target_cover_id,
                "source_match_candidate_id": combined["id"],
                "decision_type": "rejected_link",
                "relationship_type": "unrelated",
                "decision_reason": "not the same listing",
            },
        ).status_code
        == 200
    )

    resp = client.get(f"/cover-images/{source_cover_id}/relationship-graph", headers=headers)
    assert resp.status_code == 200
    edge = resp.json()["edges"][0]
    assert edge["decision_type"] == "rejected_link"
    assert edge["display_lane"] == "blocked"


def test_cover_relationship_graph_excludes_superseded_and_keeps_latest(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-super@example.com")
    headers = mcc.auth_headers(token)
    shared_image = mcc.make_png_bytes(color=(40, 130, 140))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text=shared_text
    )
    _, target_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text=shared_text
    )

    assert (
        client.post(
            "/cover-link-decisions",
            headers=headers,
            json={
                "source_cover_image_id": source_cover_id,
                "candidate_cover_image_id": target_cover_id,
                "decision_type": "needs_review",
                "relationship_type": "same_issue",
            },
        ).status_code
        == 200
    )
    second = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "decision_type": "approved_link",
            "relationship_type": "same_cover",
        },
    )
    assert second.status_code == 200
    gid = second.json()["id"]

    graph_resp = client.get(f"/cover-images/{source_cover_id}/relationship-graph", headers=headers)
    graph = graph_resp.json()
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["decision_id"] == gid
    assert graph["edges"][0]["decision_type"] == "approved_link"


def test_cover_relationship_graph_excludes_reverted(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-revert@example.com")
    headers = mcc.auth_headers(token)
    shared_image = mcc.make_png_bytes(color=(110, 60, 80))
    shared_text = "INVINCIBLE #1 IMAGE UPC 123456789012"
    _, source_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text=shared_text
    )
    _, target_cover_id = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text=shared_text
    )
    mcc._prepare_cover_signals(client, token, source_cover_id)
    mcc._prepare_cover_signals(client, token, target_cover_id)
    gen_resp = client.post(
        f"/cover-images/{source_cover_id}/generate-match-candidates",
        headers=headers,
    )
    combined = mcc._candidate_by_type(gen_resp.json(), "combined_similarity")
    created = client.post(
        "/cover-link-decisions",
        headers=headers,
        json={
            "source_cover_image_id": source_cover_id,
            "candidate_cover_image_id": target_cover_id,
            "source_match_candidate_id": combined["id"],
            "decision_type": "approved_link",
            "relationship_type": "duplicate_scan",
        },
    )
    assert created.status_code == 200
    did = created.json()["id"]
    assert client.post(f"/cover-link-decisions/{did}/revert", headers=headers).status_code == 200

    graph_resp = client.get(f"/cover-images/{source_cover_id}/relationship-graph", headers=headers)
    graph = graph_resp.json()
    assert graph["edges"] == []


def test_cover_relationship_graph_one_hop_no_transitive_inference(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-transitive@example.com")
    headers = mcc.auth_headers(token)

    _, cover_a = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(20, 200, 40)),
        raw_text="X #1 PUB-U",
    )
    _, cover_b = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(210, 20, 210)),
        raw_text="X #2 PUB-U",
    )
    _, cover_c = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(color=(10, 10, 10)),
        raw_text="X #3 PUB-U",
    )

    assert (
        client.post(
            "/cover-link-decisions",
            headers=headers,
            json={
                "source_cover_image_id": cover_a,
                "candidate_cover_image_id": cover_b,
                "decision_type": "approved_link",
                "relationship_type": "same_issue",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/cover-link-decisions",
            headers=headers,
            json={
                "source_cover_image_id": cover_a,
                "candidate_cover_image_id": cover_c,
                "decision_type": "approved_link",
                "relationship_type": "variant_family",
            },
        ).status_code
        == 200
    )

    graph_a = client.get(f"/cover-images/{cover_a}/relationship-graph", headers=headers).json()
    assert len(graph_a["nodes"]) == 3
    assert len(graph_a["edges"]) == 2
    endpoints = {
        (e["source_cover_image_id"], e["candidate_cover_image_id"]) for e in graph_a["edges"]
    }
    assert endpoints == {(cover_a, cover_b), (cover_a, cover_c)}

    graph_b = client.get(f"/cover-images/{cover_b}/relationship-graph", headers=headers).json()
    assert len(graph_b["nodes"]) == 2
    assert len(graph_b["edges"]) == 1


def test_cover_relationship_graph_list_recent_endpoint(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-recent@example.com")
    headers = mcc.auth_headers(token)
    shared_image = mcc.make_png_bytes()
    _, s = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text="X #1 Pub"
    )
    _, t = mcc._bootstrap_processed_cover(
        client, session, monkeypatch, token=token, image_bytes=shared_image, raw_text="X #1 Pub"
    )
    assert (
        client.post(
            "/cover-link-decisions",
            headers=headers,
            json={
                "source_cover_image_id": s,
                "candidate_cover_image_id": t,
                "decision_type": "approved_link",
                "relationship_type": "same_cover",
            },
        ).status_code
        == 200
    )

    recent = client.get("/cover-link-decisions/recent", headers=headers)
    assert recent.status_code == 200
    assert isinstance(recent.json(), list)
    assert any(row["source_cover_image_id"] == s for row in recent.json())


def test_cover_relationship_graph_does_not_mutate_inventory_identity(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-mutation@example.com")
    headers = mcc.auth_headers(token)
    inv_id = mcc._inventory_copy_id_for_new_order(client, token)
    cid = mcc._upload_inventory_cover(client, token, inv_id, mcc.make_png_bytes())

    before_inv = session.get(InventoryCopy, inv_id)
    assert before_inv is not None

    before_cover = session.get(CoverImage, cid)
    assert before_cover is not None

    snapshot_identity = before_inv.metadata_identity_key

    before_audit_count = len(session.exec(select(MetadataAudit)).all())

    resp = client.get(f"/cover-images/{cid}/relationship-graph", headers=headers)
    assert resp.status_code == 200

    after_audit_count = len(session.exec(select(MetadataAudit)).all())
    assert after_audit_count == before_audit_count

    session.expire_all()
    after_inv = session.get(InventoryCopy, inv_id)
    cover_after = session.get(CoverImage, cid)
    assert after_inv is not None and cover_after is not None
    assert after_inv.metadata_identity_key == snapshot_identity
    assert cover_after.canonical_series_id == before_cover.canonical_series_id
    assert cover_after.sha256_hash == before_cover.sha256_hash


def test_cover_relationship_graph_deterministic_json(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = mcc.register_and_login(client, "graph-deterministic@example.com")
    headers = mcc.auth_headers(token)
    _, a = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(),
        raw_text="D #1 P",
    )
    _, b = mcc._bootstrap_processed_cover(
        client,
        session,
        monkeypatch,
        token=token,
        image_bytes=mcc.make_png_bytes(),
        raw_text="D #1 P",
    )
    assert (
        client.post(
            "/cover-link-decisions",
            headers=headers,
            json={
                "source_cover_image_id": a,
                "candidate_cover_image_id": b,
                "decision_type": "approved_link",
                "relationship_type": "duplicate_scan",
            },
        ).status_code
        == 200
    )
    g1 = client.get(f"/cover-images/{a}/relationship-graph", headers=headers).json()
    g2 = client.get(f"/cover-images/{a}/relationship-graph", headers=headers).json()
    assert g1 == g2
