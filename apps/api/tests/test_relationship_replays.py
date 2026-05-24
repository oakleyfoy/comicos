from fastapi.testclient import TestClient
from sqlmodel import Session, select

import test_inventory as inv
import test_ops_admin as ops
import test_relationship_conflicts as conflict_helpers
from app.core.config import get_settings
from app.models import CoverRelationshipConflict, InventoryCopy, MetadataAudit, RelationshipReplayItem


def test_relationship_replay_run_creation_orders_items_deterministically(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-replay-create@example.com")
    _, cover_b = conflict_helpers._create_cover(client, token, title="Invincible", issue_number="2", color=(20, 20, 180))
    _, cover_a = conflict_helpers._create_cover(client, token, title="Invincible", issue_number="1", color=(10, 10, 200))

    response = client.post(
        "/relationship-replays",
        headers=inv.auth_headers(token),
        json={"replay_type": "link_decisions", "cover_image_ids": [cover_b, 999999, cover_a, cover_a]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["total_items"] == 2
    assert [item["cover_image_id"] for item in payload["items"]] == sorted([cover_a, cover_b])
    assert payload["status"] == "pending"

    audits = session.exec(
        select(MetadataAudit)
        .where(MetadataAudit.entity_type == "relationship_replay_run")
        .order_by(MetadataAudit.id.asc())
    ).all()
    assert any(audit.action == "relationship_replay_run_created" for audit in audits)


def test_relationship_replay_detects_unchanged_link_decisions(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-replay-unchanged@example.com")
    _, source_cover_id = conflict_helpers._create_cover(client, token, title="Saga", issue_number="1", color=(100, 50, 50))
    _, candidate_cover_id = conflict_helpers._create_cover(client, token, title="Saga", issue_number="1", color=(120, 60, 60))
    conflict_helpers._insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="approved_link",
        relationship_type="same_issue",
    )

    create = client.post(
        "/relationship-replays",
        headers=inv.auth_headers(token),
        json={"replay_type": "link_decisions", "cover_image_ids": [source_cover_id]},
    )
    assert create.status_code == 201
    replay_id = create.json()["id"]

    start = client.post(f"/relationship-replays/{replay_id}/start", headers=inv.auth_headers(token))
    assert start.status_code == 200
    payload = start.json()
    assert payload["status"] == "completed"
    assert payload["changed_items"] == 0
    assert payload["unchanged_items"] == 1
    assert payload["items"][0]["diff_summary_json"]["status"] == "unchanged"


def test_relationship_replay_detects_changed_link_decisions(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-replay-changed@example.com")
    _, source_cover_id = conflict_helpers._create_cover(client, token, title="Hellboy", issue_number="1", color=(40, 90, 90))
    _, candidate_cover_id = conflict_helpers._create_cover(client, token, title="Hellboy", issue_number="1", color=(50, 100, 100))
    conflict_helpers._insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="approved_link",
        relationship_type="same_issue",
    )

    create = client.post(
        "/relationship-replays",
        headers=inv.auth_headers(token),
        json={"replay_type": "link_decisions", "cover_image_ids": [source_cover_id]},
    )
    assert create.status_code == 201
    replay_id = create.json()["id"]

    _, extra_cover_id = conflict_helpers._create_cover(client, token, title="Hellboy", issue_number="1", color=(60, 110, 110))
    conflict_helpers._insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=extra_cover_id,
        decision_type="approved_link",
        relationship_type="same_issue",
    )

    start = client.post(f"/relationship-replays/{replay_id}/start", headers=inv.auth_headers(token))
    assert start.status_code == 200
    payload = start.json()
    assert payload["status"] == "completed_with_changes"
    assert payload["changed_items"] == 1
    assert payload["items"][0]["status"] == "changed"
    diff = payload["items"][0]["diff_summary_json"]
    assert diff["status"] == "changed"
    assert diff["added"] >= 1


def test_relationship_replay_isolates_failed_items(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-replay-failed-item@example.com")
    _, accessible_cover_id = conflict_helpers._create_cover(client, token, title="Spawn", issue_number="1", color=(120, 40, 40))
    create = client.post(
        "/relationship-replays",
        headers=inv.auth_headers(token),
        json={"replay_type": "relationship_graph", "cover_image_ids": [accessible_cover_id]},
    )
    assert create.status_code == 201
    replay_id = create.json()["id"]
    item_id = create.json()["items"][0]["id"]

    item = session.get(RelationshipReplayItem, item_id)
    assert item is not None
    item.cover_image_id = 999999
    item.relationship_key = "cover:999999"
    session.add(item)
    session.commit()

    start = client.post(f"/relationship-replays/{replay_id}/start", headers=inv.auth_headers(token))
    assert start.status_code == 200
    payload = start.json()
    assert payload["failed_items"] == 1
    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["last_error"] is not None


def test_relationship_replay_cancel_marks_pending_items_cancelled(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-replay-cancel@example.com")
    _, cover_id = conflict_helpers._create_cover(client, token, title="Batman", issue_number="1", color=(70, 70, 170))
    create = client.post(
        "/relationship-replays",
        headers=inv.auth_headers(token),
        json={"replay_type": "relationship_graph", "cover_image_ids": [cover_id]},
    )
    assert create.status_code == 201
    replay_id = create.json()["id"]

    cancelled = client.post(f"/relationship-replays/{replay_id}/cancel", headers=inv.auth_headers(token))
    assert cancelled.status_code == 200
    payload = cancelled.json()
    assert payload["status"] == "cancelled"
    assert payload["items"][0]["status"] == "cancelled"


def test_relationship_replay_compact_diff_and_audit_rows(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-replay-audits@example.com")
    _, source_cover_id = conflict_helpers._create_cover(client, token, title="Monstress", issue_number="1", color=(60, 20, 90))
    _, candidate_cover_id = conflict_helpers._create_cover(client, token, title="Monstress", issue_number="1", color=(70, 30, 100))
    conflict_helpers._insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="approved_link",
        relationship_type="same_issue",
    )
    create = client.post(
        "/relationship-replays",
        headers=inv.auth_headers(token),
        json={"replay_type": "link_decisions", "cover_image_ids": [source_cover_id]},
    )
    replay_id = create.json()["id"]
    client.post(f"/relationship-replays/{replay_id}/start", headers=inv.auth_headers(token))

    run_actions = [
        row.action
        for row in session.exec(
            select(MetadataAudit)
            .where(MetadataAudit.entity_type == "relationship_replay_run")
            .order_by(MetadataAudit.id.asc())
        ).all()
    ]
    item_actions = [
        row.action
        for row in session.exec(
            select(MetadataAudit)
            .where(MetadataAudit.entity_type == "relationship_replay_item")
            .order_by(MetadataAudit.id.asc())
        ).all()
    ]
    assert "relationship_replay_run_created" in run_actions
    assert "relationship_replay_run_started" in run_actions
    assert any(action in {"relationship_replay_run_completed", "relationship_replay_run_completed_with_changes"} for action in run_actions)
    assert any(action in {"relationship_replay_item_changed", "relationship_replay_item_unchanged"} for action in item_actions)

    replay_item = session.exec(select(RelationshipReplayItem).order_by(RelationshipReplayItem.id.desc())).first()
    assert replay_item is not None
    dumped = str(replay_item.diff_summary_json)
    assert len(dumped) < 4000


def test_relationship_replay_does_not_mutate_decisions_inventory_or_conflicts(
    client: TestClient,
    session: Session,
) -> None:
    token = inv.register_and_login(client, "relationship-replay-no-mutation@example.com")
    inventory_copy_id, source_cover_id = conflict_helpers._create_cover(client, token, title="Dept. H", issue_number="1", color=(40, 140, 140))
    _, candidate_cover_id = conflict_helpers._create_cover(client, token, title="Dept. H", issue_number="1", color=(50, 150, 150))
    approved = conflict_helpers._insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="approved_link",
        relationship_type="same_issue",
    )
    conflict_helpers._insert_link_decision(
        session,
        source_cover_id=source_cover_id,
        candidate_cover_id=candidate_cover_id,
        decision_type="rejected_link",
        relationship_type="unrelated",
    )
    detect = client.post("/relationship-conflicts/detect", headers=inv.auth_headers(token))
    assert detect.status_code == 200
    conflict_id = next(row["id"] for row in detect.json()["conflicts"] if row["conflict_type"] == "approved_link_vs_rejected_link")

    inventory_copy = session.get(InventoryCopy, inventory_copy_id)
    conflict_row = session.get(CoverRelationshipConflict, conflict_id)
    assert inventory_copy is not None
    assert conflict_row is not None
    before_identity = inventory_copy.metadata_identity_key
    before_decision_state = approved.decision_state
    before_conflict_status = conflict_row.status

    create = client.post(
        "/relationship-replays",
        headers=inv.auth_headers(token),
        json={"replay_type": "full_relationship_pipeline", "cover_image_ids": [source_cover_id]},
    )
    assert create.status_code == 201
    replay_id = create.json()["id"]
    start = client.post(f"/relationship-replays/{replay_id}/start", headers=inv.auth_headers(token))
    assert start.status_code == 200

    session.refresh(inventory_copy)
    session.refresh(approved)
    session.refresh(conflict_row)
    assert inventory_copy.metadata_identity_key == before_identity
    assert approved.decision_state == before_decision_state
    assert conflict_row.status == before_conflict_status


def test_ops_relationship_replay_endpoints_work(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-relationship-replay@example.com")
    get_settings.cache_clear()
    token = ops.register_and_login(client, "ops-relationship-replay@example.com")
    _, cover_id = conflict_helpers._create_cover(client, token, title="X-Men", issue_number="1", color=(80, 80, 180))

    created = client.post(
        "/ops/relationship-replays",
        headers=ops.auth_headers(token),
        json={"replay_type": "relationship_graph", "cover_image_ids": [cover_id]},
    )
    assert created.status_code == 201
    replay_id = created.json()["id"]

    listed = client.get("/ops/relationship-replays", headers=ops.auth_headers(token))
    assert listed.status_code == 200
    assert any(row["id"] == replay_id for row in listed.json())

    detail = client.get(f"/ops/relationship-replays/{replay_id}", headers=ops.auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["id"] == replay_id

    started = client.post(f"/ops/relationship-replays/{replay_id}/start", headers=ops.auth_headers(token))
    assert started.status_code == 200
    assert started.json()["status"] in {"completed", "completed_with_changes"}
