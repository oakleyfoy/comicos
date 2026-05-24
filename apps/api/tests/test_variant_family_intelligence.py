"""Variant-family intelligence (P32-06) — deterministic clustering visibility."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.models import CoverImageFingerprint, InventoryCopy


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    resp = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_order_payload(quantity: int = 1) -> dict:
    return {
        "retailer": "Whatnot",
        "order_date": "2026-05-23",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
        "items": [
            {
                "title": "VariantFamilyIntel",
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


def insert_vf_candidate(
    session: Session,
    *,
    source: int,
    candidate: int,
    ctype: str,
    matched: dict[str, object],
    hard: dict[str, object],
    grouping_type: str,
    grouping_key: str,
    version_slug: str,
) -> None:
    from app.models import CoverImageMatchCandidate

    row = CoverImageMatchCandidate(
        source_cover_image_id=source,
        candidate_cover_image_id=candidate,
        candidate_type=ctype,
        confidence_bucket="high",
        deterministic_score=0.9,
        normalized_confidence_score=0.9,
        extraction_version=f"vf-intel-test-{version_slug}",
        ranking_score=0.8,
        matched_signals=matched,
        hard_match_flags_json=hard,
        weak_signal_flags_json={},
        ranking_reason_json={},
        grouping_type=grouping_type,
        grouping_key=grouping_key,
    )
    session.add(row)
    session.commit()


def test_probable_variant_family_match_candidate_surfaces(
    client: TestClient,
    session: Session,
) -> None:
    tok = register_and_login(client, "vf-probable@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((40, 50, 60)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((70, 80, 90)))
    insert_vf_candidate(
        session,
        source=c_a,
        candidate=c_b,
        ctype="combined_similarity",
        matched={
            "phash_similarity": 0.55,
            "ahash_similarity": 0.0,
            "dhash_similarity": 0.0,
            "barcode_matches": [],
        },
        hard={
            "ocr_title_exact_match": True,
            "ocr_issue_number_exact_match": True,
            "ocr_publisher_exact_match": True,
        },
        grouping_type="probable_variant_family",
        grouping_key="probable_variant_family:vf_test_digest",
        version_slug="a",
    )
    focal = client.get(f"/cover-images/{c_a}/variant-family-candidates", headers=hdr).json()
    peers = focal["variant_peers"]
    peer_ids = [p["peer_cover_image_id"] for p in peers]
    assert peer_ids == sorted(peer_ids)
    needle = next(p for p in peers if p["peer_cover_image_id"] == c_b)
    assert needle["classification"] == "probable"
    assert needle["evidences"]["probable_variant_family_group"] is True
    assert needle["evidences"]["publisher_exact_pairwise"] is True


def test_near_identical_fingerprint_variant_family_candidate_skipped(
    client: TestClient,
    session: Session,
) -> None:
    tok = register_and_login(client, "vf-near-id@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((1, 2, 3)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((9, 8, 7)))
    insert_vf_candidate(
        session,
        source=c_a,
        candidate=c_b,
        ctype="combined_similarity",
        matched={"phash_similarity": 0.99, "ahash_similarity": 0.99, "dhash_similarity": 0.99},
        hard={
            "ocr_title_exact_match": True,
            "ocr_issue_number_exact_match": True,
            "ocr_publisher_exact_match": False,
        },
        grouping_type="probable_variant_family",
        grouping_key="probable_variant_family:near",
        version_slug="b",
    )
    focal = client.get(f"/cover-images/{c_a}/variant-family-candidates", headers=hdr).json()
    assert c_b not in {p["peer_cover_image_id"] for p in focal["variant_peers"]}


def test_barcode_similarity_without_ocr_anchor_skipped(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "vf-bconly@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((11, 12, 13)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((21, 22, 23)))
    insert_vf_candidate(
        session,
        source=c_a,
        candidate=c_b,
        ctype="barcode_similarity",
        matched={"barcode_matches": ["123450987612"], "phash_similarity": 0.1},
        hard={
            "ocr_title_exact_match": False,
            "ocr_issue_number_exact_match": False,
        },
        grouping_type="probable_variant_family",
        grouping_key="probable_variant_family:bc",
        version_slug="c",
    )
    focal = client.get(f"/cover-images/{c_a}/variant-family-candidates", headers=hdr).json()
    assert focal["variant_peers"] == []


def test_human_variant_family_classification_confirmed(client: TestClient) -> None:
    tok = register_and_login(client, "vf-human@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((3, 3, 3)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((9, 9, 9)))
    reply = client.post(
        "/cover-link-decisions",
        headers=hdr,
        json={
            "source_cover_image_id": c_a,
            "candidate_cover_image_id": c_b,
            "source_match_candidate_id": None,
            "decision_type": "approved_link",
            "relationship_type": "variant_family",
            "decision_reason": "reviewed variants",
        },
    )
    assert reply.status_code == 200
    focal = client.get(f"/cover-images/{c_a}/variant-family-candidates", headers=hdr).json()
    needle = next(p for p in focal["variant_peers"] if p["peer_cover_image_id"] == c_b)
    assert needle["classification"] == "confirmed"
    assert needle["evidences"]["human_variant_family"] is True


def test_duplicate_scan_suppresses_variant_family_candidate(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "vf-dup-scan@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((5, 5, 6)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((6, 6, 5)))
    insert_vf_candidate(
        session,
        source=c_a,
        candidate=c_b,
        ctype="combined_similarity",
        matched={"phash_similarity": 0.62, "ahash_similarity": 0.0, "dhash_similarity": 0.0},
        hard={
            "ocr_title_exact_match": True,
            "ocr_issue_number_exact_match": True,
            "ocr_publisher_exact_match": False,
        },
        grouping_type="probable_variant_family",
        grouping_key="probable_variant_family:dup-scan-vf",
        version_slug="d",
    )

    dup = client.post(
        "/cover-link-decisions",
        headers=hdr,
        json={
            "source_cover_image_id": c_a,
            "candidate_cover_image_id": c_b,
            "source_match_candidate_id": None,
            "decision_type": "approved_link",
            "relationship_type": "duplicate_scan",
            "decision_reason": "dup",
        },
    )
    assert dup.status_code == 200

    focal_before = client.get(f"/cover-images/{c_a}/variant-family-candidates", headers=hdr).json()
    peer_ids_before = [p["peer_cover_image_id"] for p in focal_before["variant_peers"]]
    assert c_b not in peer_ids_before


def test_unrelated_human_decision_suppresses_technical_variant_signals(
    client: TestClient,
    session: Session,
) -> None:
    tok = register_and_login(client, "vf-unrel@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((55, 12, 4)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((54, 11, 3)))
    insert_vf_candidate(
        session,
        source=c_a,
        candidate=c_b,
        ctype="combined_similarity",
        matched={"phash_similarity": 0.71, "ahash_similarity": 0.0, "dhash_similarity": 0.0},
        hard={
            "ocr_title_exact_match": True,
            "ocr_issue_number_exact_match": True,
            "ocr_publisher_exact_match": False,
        },
        grouping_type="probable_variant_family",
        grouping_key="probable_variant_family:unrel-test",
        version_slug="e",
    )

    unr = client.post(
        "/cover-link-decisions",
        headers=hdr,
        json={
            "source_cover_image_id": c_a,
            "candidate_cover_image_id": c_b,
            "source_match_candidate_id": None,
            "decision_type": "rejected_link",
            "relationship_type": "unrelated",
            "decision_reason": "not related",
        },
    )
    assert unr.status_code == 200
    focal = client.get(f"/cover-images/{c_a}/variant-family-candidates", headers=hdr).json()
    assert c_b not in {p["peer_cover_image_id"] for p in focal["variant_peers"]}
    suppressed = focal["suppressed_pairs_touching_focal"]
    assert any(s["right_cover_image_id"] == c_b or s["left_cover_image_id"] == c_b for s in suppressed)


def test_cluster_listing_ordering_is_stable(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "vf-order@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=3)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((90, 0, 0)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((0, 90, 0)))
    c_c = upload_inventory_cover(client, tok, inv_ids[2], png((0, 0, 90)))

    gid = "vf-order-group"
    for src, cand, slug in [(c_a, c_b, "ab"), (c_b, c_c, "bc")]:
        insert_vf_candidate(
            session,
            source=src,
            candidate=cand,
            ctype="combined_similarity",
            matched={"phash_similarity": 0.72, "ahash_similarity": 0.0, "dhash_similarity": 0.0},
            hard={
                "ocr_title_exact_match": True,
                "ocr_issue_number_exact_match": True,
                "ocr_publisher_exact_match": False,
            },
            grouping_type="probable_variant_family",
            grouping_key=gid,
            version_slug=slug,
        )

    listing = client.get("/variant-family-clusters", headers=hdr).json()
    keys = [c["cluster_key"] for c in listing["clusters"]]
    assert keys == sorted(keys)
    trio = next(c for c in listing["clusters"] if set(c["cover_image_ids"]) == {c_a, c_b, c_c})
    assert trio["cover_image_ids"] == sorted(trio["cover_image_ids"])


def test_metadata_identity_divergent_fingerprints_surface(
    client: TestClient,
    session: Session,
) -> None:
    tok = register_and_login(client, "vf-meta-id@example.com")
    hdr = auth_headers(tok)
    inv_ids = order_inventory_copy_ids(client, tok, quantity=2)
    c_a = upload_inventory_cover(client, tok, inv_ids[0], png((128, 0, 0)))
    c_b = upload_inventory_cover(client, tok, inv_ids[1], png((128, 1, 0)))

    now = datetime.now(timezone.utc)
    for cid, fv in [(c_a, "0000000000000000"), (c_b, "fff0000000000000")]:
        session.add(
            CoverImageFingerprint(
                cover_image_id=cid,
                fingerprint_type="phash",
                fingerprint_value=fv,
                derivative_type="medium",
                image_width=400,
                image_height=640,
                image_sha256="0" * 64 if fv.startswith("000") else "f" * 64,
                extraction_version="vf-meta-test",
                created_at=now,
                updated_at=now,
            )
        )

    ia = session.get(InventoryCopy, inv_ids[0])
    ib = session.get(InventoryCopy, inv_ids[1])
    assert ia is not None and ib is not None
    ia.metadata_identity_key = "shared-deterministic-vf-key"
    ib.metadata_identity_key = "shared-deterministic-vf-key"
    session.add(ia)
    session.add(ib)
    session.commit()

    focal = client.get(f"/cover-images/{c_a}/variant-family-candidates", headers=hdr).json()
    needle = next(p for p in focal["variant_peers"] if p["peer_cover_image_id"] == c_b)
    assert needle["evidences"]["metadata_identity_normalized"] is True
    assert needle["evidences"]["fingerprint_divergent_signal"] is True
