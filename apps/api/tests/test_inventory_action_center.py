from fastapi.testclient import TestClient
from sqlmodel import Session, select

import test_inventory as inv
import test_relationship_conflicts as rc
from app.models import CoverRelationshipConflict, InventoryCopy


def _open_conflict(session: Session, *, a: int, b: int) -> None:
    session.add(
        CoverRelationshipConflict(
            conflict_type="canonical_suggestion_mismatch",
            severity="critical",
            source_cover_image_id=a,
            related_cover_image_id=b,
            link_decision_id=None,
            match_candidate_id=None,
            canonical_issue_suggestion_id=None,
            conflict_key=f"iac-test-{a}-{b}",
            status="open",
            evidence_json={"signals": ["iac-test"]},
        )
    )
    session.commit()


def test_action_center_conflict_stable_order_and_preorder_calendar(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "iac-surface@example.com")
    _src_inv, cid_a = rc._create_cover(
        client,
        token,
        title="Action Source",
        issue_number="1",
        color=(30, 120, 200),
    )
    _dst_inv, cid_b = rc._create_cover(
        client,
        token,
        title="Action Dst",
        issue_number="1",
        color=(50, 140, 220),
    )
    _open_conflict(session, a=cid_a, b=cid_b)

    body = client.get("/inventory-action-center", headers=inv.auth_headers(token)).json()
    cats = sorted({item["action_category"] for item in body["actions"]})
    assert "review_relationship_conflict" in cats
    prio_index = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_copy = sorted(
        body["actions"],
        key=lambda a: (
            prio_index[a["priority"]],
            a["action_category"],
            a["publisher"],
            a["title"],
            a["issue_number"],
            a["inventory_copy_id"],
            a["action_key"],
        ),
    )
    assert body["actions"] == sorted_copy

    preorder_token = inv.register_and_login(client, "iac-preorder@example.com")
    inv.create_order(
        client,
        preorder_token,
        items=[
            {
                "title": "Preorder Cal",
                "publisher": "TestPub",
                "issue_number": "88",
                "cover_name": "Cover Z",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 3.25,
                "release_status": "not_released_yet",
                "order_status": "ordered",
            }
        ],
    )
    preorder_body = client.get("/inventory-action-center", headers=inv.auth_headers(preorder_token)).json()
    preorder_cats = {item["action_category"] for item in preorder_body["actions"]}
    assert "update_preorder_metadata" in preorder_cats


def test_action_center_inventory_list_has_attachment_stub(
    client: TestClient,
) -> None:
    token = inv.register_and_login(client, "iac-list@example.com")
    inv.create_order(client, token)
    listing = client.get("/inventory?page=1&page_size=10", headers=inv.auth_headers(token)).json()
    assert listing["total"] >= 1
    for row in listing["items"]:
        ac = row.get("inventory_action_center")
        assert ac is not None
        assert "action_keys" in ac
        assert "urgent_lane" in ac


def test_action_center_priority_filter(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "iac-filter@example.com")
    _, cid_a = rc._create_cover(client, token, title="Crit", issue_number="10", color=(20, 20, 220))
    _, cid_b = rc._create_cover(client, token, title="Crit", issue_number="11", color=(40, 40, 220))
    _open_conflict(session, a=cid_a, b=cid_b)

    filtered = client.get(
        "/inventory-action-center",
        headers=inv.auth_headers(token),
        params={"priority": "critical"},
    ).json()
    assert all(item["priority"] == "critical" for item in filtered["actions"])


def test_action_center_reads_preserve_inventory_core_fields(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "iac-mutation@example.com")
    inv_id, cid_a = rc._create_cover(client, token, title="Mute", issue_number="20", color=(110, 10, 10))
    _, cid_b = rc._create_cover(client, token, title="Mute", issue_number="21", color=(120, 20, 20))
    _open_conflict(session, a=cid_a, b=cid_b)

    ic = session.get(InventoryCopy, inv_id)
    assert ic is not None
    before = (
        ic.release_status,
        ic.order_status,
        str(ic.acquisition_cost),
        ic.release_year,
    )

    client.get("/inventory-action-center", headers=inv.auth_headers(token))
    client.get("/inventory-action-center/summary", headers=inv.auth_headers(token))

    ic2 = session.get(InventoryCopy, inv_id)
    assert ic2 is not None
    after = (
        ic2.release_status,
        ic2.order_status,
        str(ic2.acquisition_cost),
        ic2.release_year,
    )
    assert after == before
