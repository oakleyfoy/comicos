from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.marketplace_acquisition import MarketplaceSource
from app.services.collection_gaps import persist_collection_gaps
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.marketplace_acquisitions import ensure_marketplace_acquisition_sources
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _manual_source_id(session: Session) -> int:
    sources = ensure_marketplace_acquisition_sources(session)
    manual = next(s for s in sources if s.source_type == "MANUAL")
    return int(manual.id or 0)


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


def test_source_seeding_idempotent(client: TestClient, session: Session) -> None:
    first = ensure_marketplace_acquisition_sources(session)
    second = ensure_marketplace_acquisition_sources(session)
    assert len(first) == len(second) == 6
    types = {s.source_type for s in second}
    assert types == {"EBAY", "WHATNOT", "MYCOMICSHOP", "COMICLINK", "COMICCONNECT", "MANUAL"}


def test_create_manual_candidate(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "mac-create@example.com")
    manual_id = _manual_source_id(session)
    resp = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token),
        json={
            "marketplace_source_id": manual_id,
            "title": "Battle Beast #3",
            "publisher": "Image",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "asking_price": 12.0,
            "shipping_price": 3.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_price"] == 15.0
    assert data["source_type"] == "MANUAL"


def test_exact_match_and_buy_below_target(client: TestClient, session: Session) -> None:
    email = "mac-buy@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    from decimal import Decimal
    from app.models import InventoryCopy

    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal("25.00")
        session.add(copy)
    session.commit()
    persist_collection_gaps(session, owner_user_id=owner_id)
    persist_acquisition_opportunities(session, owner_user_id=owner_id)
    manual_id = _manual_source_id(session)
    created = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token),
        json={
            "marketplace_source_id": manual_id,
            "title": "Battle Beast #3",
            "publisher": "Image",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "total_price": 10.0,
        },
    )
    cand_id = created.json()["data"]["id"]
    evaluated = client.post(f"/api/v1/marketplace-acquisitions/{cand_id}/evaluate", headers=auth_headers(token))
    assert evaluated.status_code == 200
    body = evaluated.json()["data"]
    assert body["acquisition_opportunity_id"] is not None
    assert body["match_confidence"] >= 0.85
    assert body["recommendation"] == "BUY"


def test_unmatched_watch(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "mac-watch@example.com")
    manual_id = _manual_source_id(session)
    created = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token),
        json={
            "marketplace_source_id": manual_id,
            "title": "Unknown Comic #99",
            "series_name": "Unknown Comic",
            "issue_number": "99",
        },
    )
    cand_id = created.json()["data"]["id"]
    evaluated = client.post(f"/api/v1/marketplace-acquisitions/{cand_id}/evaluate", headers=auth_headers(token))
    body = evaluated.json()["data"]
    assert body["match_confidence"] == 0.0
    assert body["recommendation"] == "WATCH"


def test_pass_above_fmv(client: TestClient, session: Session) -> None:
    email = "mac-pass@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    from decimal import Decimal
    from app.models import InventoryCopy

    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal("25.00")
        session.add(copy)
    session.commit()
    persist_collection_gaps(session, owner_user_id=owner_id)
    persist_acquisition_opportunities(session, owner_user_id=owner_id)
    manual_id = _manual_source_id(session)
    created = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token),
        json={
            "marketplace_source_id": manual_id,
            "title": "Battle Beast #3",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "total_price": 30.0,
        },
    )
    cand_id = created.json()["data"]["id"]
    evaluated = client.post(f"/api/v1/marketplace-acquisitions/{cand_id}/evaluate", headers=auth_headers(token))
    assert evaluated.json()["data"]["recommendation"] == "PASS"


def test_update_status_and_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "mac-a@example.com")
    token_b = register_and_login(client, "mac-b@example.com")
    manual_id = _manual_source_id(session)
    created = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token_a),
        json={"marketplace_source_id": manual_id, "title": "Test Book #1", "series_name": "Test Book", "issue_number": "1"},
    )
    cand_id = created.json()["data"]["id"]
    patched = client.patch(
        f"/api/v1/marketplace-acquisitions/{cand_id}",
        headers=auth_headers(token_a),
        json={"status": "REVIEWED"},
    )
    assert patched.json()["data"]["status"] == "REVIEWED"
    forbidden = client.get(f"/api/v1/marketplace-acquisitions/{cand_id}", headers=auth_headers(token_b))
    assert forbidden.status_code == 404
