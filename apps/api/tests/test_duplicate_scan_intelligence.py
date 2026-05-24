"""Duplicate scan intelligence (P32-05) — read-only deterministic clustering visibility."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.core.config import get_settings
from app.models import CoverImage, CoverImageMatchCandidate


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    resp = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_order_payload(quantity: int = 1) -> dict:
    return {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
        "items": [
            {
                "title": "DupScanIntel",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": quantity,
                "raw_item_price": 5.0,
            }
        ],
    }


def order_inventory_copy_ids(client: TestClient, token: str, *, quantity: int) -> list[int]:
    resp = client.post("/orders", json=build_order_payload(quantity=quantity), headers=auth_headers(token))
    assert resp.status_code == 201
    detail = client.get(f"/orders/{resp.json()['order_id']}", headers=auth_headers(token))
    assert detail.status_code == 200
    return detail.json()["items"][0]["inventory_copy_ids"]


def upload_inventory_cover(client: TestClient, token: str, inv_id: int, body: bytes) -> int:
    resp = client.post(
        f"/inventory/{inv_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", body, "image/png")},
        data={"source_type": "upload"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def png(rgb: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (80, 120), color=rgb)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def insert_match_candidate(
    session: Session,
    *,
    source: int,
    candidate: int,
    ctype: str,
    matched: dict[str, object],
    grouping_type: str | None,
    grouping_key: str | None,
    version_slug: str,
) -> None:
    row = CoverImageMatchCandidate(
        source_cover_image_id=source,
        candidate_cover_image_id=candidate,
        candidate_type=ctype,
        confidence_bucket="high",
        deterministic_score=0.9,
        normalized_confidence_score=0.9,
        extraction_version=f"dup-intel-test-{version_slug}",
        ranking_score=0.8,
        matched_signals=matched,
        hard_match_flags_json={},
        weak_signal_flags_json={},
        ranking_reason_json={},
        grouping_type=grouping_type,
        grouping_key=grouping_key,
    )
    session.add(row)
    session.commit()


def test_sha256_duplicate_pair_surfaces_via_candidate_endpoint(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "sha256-scan@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((10, 20, 30)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((90, 10, 5)))

    blob_a = session.get(CoverImage, c_a)
    blob_b = session.get(CoverImage, c_b)
    assert blob_a is not None and blob_b is not None
    shared_digest = "a" * 64
    blob_a.sha256_hash = shared_digest
    blob_b.sha256_hash = shared_digest
    session.add(blob_a)
    session.add(blob_b)
    session.commit()

    focal = client.get(f"/cover-images/{c_a}/duplicate-scan-candidates", headers=hdr).json()

    peers = focal["duplicate_peers"]
    peer_ids = [p["peer_cover_image_id"] for p in peers]
    assert peer_ids == sorted(peer_ids)

    needle = next(p for p in peers if p["peer_cover_image_id"] == c_b)
    assert needle["evidences"]["sha256_exact_match"] is True


def test_fingerprint_similarity_duplicate_probe(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "fp-scan@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((1, 2, 3)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((55, 44, 33)))

    insert_match_candidate(
        session,
        source=c_a,
        candidate=c_b,
        ctype="fingerprint_similarity",
        matched={
            "phash_similarity": 0.95,
            "ahash_similarity": 0.0,
            "dhash_similarity": 0.0,
        },
        grouping_type=None,
        grouping_key=None,
        version_slug="fp-strong",
    )

    focal = client.get(f"/cover-images/{c_a}/duplicate-scan-candidates", headers=hdr).json()


    needle = next(p for p in focal["duplicate_peers"] if p["peer_cover_image_id"] == c_b)
    assert needle["evidences"]["fingerprint_similarity_probable"] is True


def test_barcode_similarity_weak_fingerprint_skipped(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "bc-only-scan@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((3, 3, 3)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((4, 5, 6)))



    insert_match_candidate(
        session,
        source=c_a,
        candidate=c_b,

        ctype="barcode_similarity",
        matched={"barcode_matches": ["123450987612"], "phash_similarity": 0.05},
        grouping_type=None,
        grouping_key=None,
        version_slug="bc-no-fp",

    )


    focal_payload = client.get(f"/cover-images/{c_a}/duplicate-scan-candidates", headers=hdr).json()


    peers = focal_payload["duplicate_peers"]


    peer_ids_bc = [p["peer_cover_image_id"] for p in peers]


    assert c_b not in peer_ids_bc




def test_human_duplicate_scan_classification_confirmed(client: TestClient) -> None:
    tok = register_and_login(client, "human-dup-scan@example.com")


    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((7, 8, 9)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((11, 12, 13)))






    reply = client.post(
        "/cover-link-decisions",
        headers=hdr,
        json={
            "source_cover_image_id": c_a,
            "candidate_cover_image_id": c_b,
            "source_match_candidate_id": None,
            "decision_type": "approved_link",
            "relationship_type": "duplicate_scan",
        },

    )


    assert reply.status_code == 200

    focal = client.get(f"/cover-images/{c_a}/duplicate-scan-candidates", headers=hdr).json()



    needle = next(p for p in focal["duplicate_peers"] if p["peer_cover_image_id"] == c_b)



    assert needle["classification"] == "confirmed"


    assert needle["evidences"]["human_duplicate_scan_confirmed"] is True




def test_unrelated_link_suppresses_fingerprint_duplicate_suggestion(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "reject-scan@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_src = upload_inventory_cover(client, tok, inv_ids[0], png((21, 22, 23)))
    c_tgt = upload_inventory_cover(client, tok, inv_ids[1], png((61, 62, 63)))






    insert_match_candidate(
        session,
        source=c_src,
        candidate=c_tgt,

        ctype="fingerprint_similarity",
        matched={"phash_similarity": 0.95},

        grouping_type=None,
        grouping_key=None,
        version_slug="fp-strong-reject",
    )



    rep_unrel = client.post(
        "/cover-link-decisions",
        headers=hdr,
        json={
            "source_cover_image_id": c_src,
            "candidate_cover_image_id": c_tgt,
            "source_match_candidate_id": None,
            "decision_type": "rejected_link",
            "relationship_type": "unrelated",
        },

    )


    assert rep_unrel.status_code == 200


    focal = client.get(f"/cover-images/{c_src}/duplicate-scan-candidates", headers=hdr).json()







    peers_reject = focal["duplicate_peers"]


    assert not any(p["peer_cover_image_id"] == c_tgt for p in peers_reject)


    suppressed = focal["suppressed_pairs_touching_focal"]

    suppressed_keys = sorted((s["pair_key"], s["suppressed_signal_labels"]) for s in suppressed)

    assert any("fingerprint_similarity_probable" in labels for (_, labels) in suppressed_keys)



def test_duplicate_peers_sorted_deterministic(client: TestClient, session: Session) -> None:


    tok = register_and_login(client, "ordering-scan@example.com")

    hdr = auth_headers(tok)
    inv_bundle = order_inventory_copy_ids(client, tok, quantity=3)
    c_hub = upload_inventory_cover(client, tok, inv_bundle[0], png((250, 0, 0)))
    leaf_a_pack = upload_inventory_cover(client, tok, inv_bundle[1], png((0, 250, 0)))
    leaf_z_pack = upload_inventory_cover(client, tok, inv_bundle[2], png((0, 0, 250)))



    for peer_pack, slug_pack in [(leaf_z_pack, "zp"), (leaf_a_pack, "ap")]:
        insert_match_candidate(
            session,
            source=c_hub,
            candidate=peer_pack,
            ctype="fingerprint_similarity",
            matched={"phash_similarity": 0.95},
            grouping_type=None,
            grouping_key=None,
            version_slug=slug_pack,
        )



    payload_cluster = client.get(f"/cover-images/{c_hub}/duplicate-scan-candidates", headers=hdr).json()



    extracted_ids_ordered = [p["peer_cover_image_id"] for p in payload_cluster["duplicate_peers"]]



    assert extracted_ids_ordered == sorted(extracted_ids_ordered)


def test_cross_owner_sha256_collision_not_leaked_other_tenant_cover(client: TestClient, session: Session) -> None:
    alice_tok_bundle = register_and_login(client, "alice-dup-scan@example.com")
    alice_hdr_pack = auth_headers(alice_tok_bundle)
    bob_pack_tok_bundle = register_and_login(client, "bob-dup-scan@example.com")
    bob_pack_hdr_bundle = auth_headers(bob_pack_tok_bundle)

    inv_bundle_alice_piece = order_inventory_copy_ids(client, alice_tok_bundle, quantity=1)
    inv_piece_bob_side = order_inventory_copy_ids(client, bob_pack_tok_bundle, quantity=1)







    alice_cover_piece = upload_inventory_cover(client, alice_tok_bundle, inv_bundle_alice_piece[0], png((9, 9, 9)))

    bob_piece_cover_sheet = upload_inventory_cover(
        client, bob_pack_tok_bundle, inv_piece_bob_side[0], png((220, 10, 10))
    )


    row_alice_piece = session.get(CoverImage, alice_cover_piece)
    row_piece_bob = session.get(CoverImage, bob_piece_cover_sheet)



    digest_collide = "d" * 64

    assert row_alice_piece is not None and row_piece_bob is not None
    row_alice_piece.sha256_hash = digest_collide





    row_piece_bob.sha256_hash = digest_collide

    session.add(row_alice_piece)

    session.add(row_piece_bob)

    session.commit()



    payload_alice_piece = client.get(
        f"/cover-images/{alice_cover_piece}/duplicate-scan-candidates", headers=alice_hdr_pack
    ).json()






    alice_peer_ids_piece = [p["peer_cover_image_id"] for p in payload_alice_piece["duplicate_peers"]]



    assert bob_piece_cover_sheet not in alice_peer_ids_piece



def test_ops_duplicate_scan_dashboard_suppressed_bucket(client: TestClient, session: Session, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-scan@example.com")
    get_settings.cache_clear()


    hdr_ops_pack = auth_headers(register_and_login(client, "ops-scan@example.com"))

    tok_owner_pack_bundle = register_and_login(client, "owner-ops-scan@example.com")


    hdr_owner_pack = auth_headers(tok_owner_pack_bundle)

    inv_piece_ops = order_inventory_copy_ids(client, tok_owner_pack_bundle, quantity=2)
    focal_ops_pack = upload_inventory_cover(client, tok_owner_pack_bundle, inv_piece_ops[0], png((5, 5, 5)))
    cand_ops_piece = upload_inventory_cover(client, tok_owner_pack_bundle, inv_piece_ops[1], png((80, 1, 1)))






    insert_match_candidate(
        session,
        source=focal_ops_pack,
        candidate=cand_ops_piece,

        ctype="fingerprint_similarity",
        matched={"phash_similarity": 0.95},
        grouping_type=None,

        grouping_key=None,
        version_slug="fp-ops suppressed",
    )



    rej_decision_ops_piece = client.post(
        "/cover-link-decisions",
        headers=hdr_owner_pack,

        json={
            "source_cover_image_id": focal_ops_pack,

            "candidate_cover_image_id": cand_ops_piece,
            "source_match_candidate_id": None,
            "decision_type": "rejected_link",
            "relationship_type": "unrelated",
        },
    )


    assert rej_decision_ops_piece.status_code == 200

    suppressed_dashboard = client.get(
        "/ops/duplicate-scan-clusters?classification_filter=suppressed", headers=hdr_ops_pack




    )


    assert suppressed_dashboard.status_code == 200
    suppressed_json_pack = suppressed_dashboard.json()






    listed_suppressed_piece = suppressed_json_pack["suppressed_pairs"]


    grouped_pair_keys_piece = sorted(s["pair_key"] for s in listed_suppressed_piece)


    assert grouped_pair_keys_piece




    assert suppressed_json_pack["clusters"] == []

