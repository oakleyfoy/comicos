from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import CoverImage, RelationshipReplayItem, RelationshipReplayRun, User
from app.schemas.relationship_replays import (
    RelationshipReplayCreatePayload,
    RelationshipReplayItemRead,
    RelationshipReplayRunRead,
)
from app.services.canonical_issue_link_suggestions import (
    _build_suggestion_specs,
    generate_canonical_issue_suggestions_for_ops,
    list_canonical_issue_suggestions_for_cover_ops,
    list_canonical_issue_suggestions_for_cover_owner,
)
from app.services.cover_link_decisions import (
    get_cover_or_404,
    list_cover_link_decisions_for_ops,
    list_cover_link_decisions_for_owner,
    owner_can_access_cover,
)
from app.services.cover_relationship_graph import (
    build_cover_relationship_graph,
    get_cover_relationship_graph_for_ops,
    get_cover_relationship_graph_for_owner,
)
from app.services.duplicate_scan_intelligence import (
    duplicate_scan_candidates_for_cover_owner,
    duplicate_scan_candidates_for_ops,
    owner_cover_scope,
)
from app.services.metadata_audits import record_metadata_audit
from app.services.relationship_conflicts import (
    _build_conflict_specs,
    list_relationship_conflicts_for_cover_ops,
    list_relationship_conflicts_for_cover_owner,
)
from app.services.variant_family_intelligence import (
    variant_family_candidates_for_cover_owner,
    variant_family_candidates_for_ops,
)

RELATIONSHIP_REPLAY_VERSION = "relationship-replay-v1"
DIFF_MAX_CHARS = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def relationship_replay_item_entity_to_read(row: RelationshipReplayItem) -> RelationshipReplayItemRead:
    if row.id is None:
        raise ValueError("relationship replay item must be flushed before serialization")
    return RelationshipReplayItemRead(
        id=row.id,
        replay_run_id=row.replay_run_id,
        cover_image_id=row.cover_image_id,
        relationship_key=row.relationship_key,
        status=row.status,  # type: ignore[arg-type]
        previous_snapshot_json=row.previous_snapshot_json or {},
        replay_snapshot_json=row.replay_snapshot_json or {},
        diff_summary_json=row.diff_summary_json or {},
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def relationship_replay_run_entity_to_read(session: Session, row: RelationshipReplayRun) -> RelationshipReplayRunRead:
    if row.id is None:
        raise ValueError("relationship replay run must be flushed before serialization")
    items = session.exec(
        select(RelationshipReplayItem)
        .where(RelationshipReplayItem.replay_run_id == row.id)
        .order_by(RelationshipReplayItem.relationship_key.asc(), RelationshipReplayItem.id.asc())
    ).all()
    return RelationshipReplayRunRead(
        id=row.id,
        replay_type=row.replay_type,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
        total_items=row.total_items,
        changed_items=row.changed_items,
        unchanged_items=row.unchanged_items,
        failed_items=row.failed_items,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_by=row.created_by,
        replay_version=row.replay_version,
        items=[relationship_replay_item_entity_to_read(item) for item in items],
    )


def _run_snapshot_public(row: RelationshipReplayRun) -> dict[str, object]:
    return {
        "replay_type": row.replay_type,
        "status": row.status,
        "total_items": row.total_items,
        "changed_items": row.changed_items,
        "unchanged_items": row.unchanged_items,
        "failed_items": row.failed_items,
        "replay_version": row.replay_version,
    }


def _json_digest(value: object) -> str:
    dumped = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(dumped.encode("utf-8")).hexdigest()


def _list_diff(previous_items: list[dict[str, object]], replay_items: list[dict[str, object]]) -> dict[str, object]:
    prev_by_key = {str(item["key"]): item for item in previous_items}
    next_by_key = {str(item["key"]): item for item in replay_items}
    added = sorted(key for key in next_by_key if key not in prev_by_key)
    removed = sorted(key for key in prev_by_key if key not in next_by_key)
    changed: list[dict[str, object]] = []
    unchanged = 0
    for key in sorted(set(prev_by_key) & set(next_by_key)):
        if prev_by_key[key] == next_by_key[key]:
            unchanged += 1
            continue
        changed_fields = sorted(
            field
            for field in set(prev_by_key[key]) | set(next_by_key[key])
            if prev_by_key[key].get(field) != next_by_key[key].get(field)
        )
        changed.append({"key": key, "fields": changed_fields[:10]})
    return {
        "status": "unchanged" if not added and not removed and not changed else "changed",
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "unchanged": unchanged,
        "added_keys": added[:20],
        "removed_keys": removed[:20],
        "changed_keys": changed[:20],
    }


def _flat_diff(previous_snapshot: dict[str, object], replay_snapshot: dict[str, object]) -> dict[str, object]:
    changed_fields = sorted(
        field
        for field in set(previous_snapshot) | set(replay_snapshot)
        if previous_snapshot.get(field) != replay_snapshot.get(field)
    )
    return {
        "status": "unchanged" if not changed_fields else "changed",
        "changed_fields": changed_fields[:20],
    }


def _pipeline_diff(previous_snapshot: dict[str, object], replay_snapshot: dict[str, object]) -> dict[str, object]:
    prev_components = dict(previous_snapshot.get("components") or {})
    next_components = dict(replay_snapshot.get("components") or {})
    changed_components: list[dict[str, object]] = []
    unchanged = 0
    for key in sorted(set(prev_components) | set(next_components)):
        if prev_components.get(key) == next_components.get(key):
            unchanged += 1
            continue
        changed_components.append({"component": key})
    return {
        "status": "unchanged" if not changed_components else "changed",
        "changed": len(changed_components),
        "unchanged": unchanged,
        "components": changed_components[:20],
    }


def _summarize_diff(previous_snapshot: dict[str, object], replay_snapshot: dict[str, object]) -> dict[str, object]:
    shape = str(previous_snapshot.get("shape") or replay_snapshot.get("shape") or "flat")
    if shape == "list":
        return _list_diff(
            list(previous_snapshot.get("items") or []),
            list(replay_snapshot.get("items") or []),
        )
    if shape == "pipeline":
        return _pipeline_diff(previous_snapshot, replay_snapshot)
    return _flat_diff(previous_snapshot, replay_snapshot)


def _bounded_diff_summary(diff_summary: dict[str, object]) -> dict[str, object]:
    dumped = json.dumps(diff_summary, sort_keys=True, separators=(",", ":"))
    if len(dumped) <= DIFF_MAX_CHARS:
        return diff_summary
    return {
        "status": str(diff_summary.get("status") or "changed"),
        "truncated": True,
        "serialized_length": len(dumped),
        "max_chars": DIFF_MAX_CHARS,
    }


def _normalize_cover_ids(cover_image_ids: list[int]) -> list[int]:
    return sorted({int(value) for value in cover_image_ids if int(value) > 0})


def _cover_scope_for_owner(session: Session, *, current_user: User) -> list[int]:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return sorted(owner_cover_scope(session, user_id=current_user.id))


def _cover_scope_for_ops(session: Session) -> list[int]:
    return [int(value) for value in session.exec(select(CoverImage.id).order_by(CoverImage.id.asc())).all()]


def _validate_cover_ids_for_owner(session: Session, *, current_user: User, cover_ids: list[int]) -> list[int]:
    valid: list[int] = []
    for cover_id in cover_ids:
        cover = session.get(CoverImage, cover_id)
        if cover is None:
            continue
        if owner_can_access_cover(session, cover=cover, current_user=current_user):
            valid.append(cover_id)
    return sorted(set(valid))


def _validate_cover_ids_for_ops(session: Session, *, cover_ids: list[int]) -> list[int]:
    valid: list[int] = []
    for cover_id in cover_ids:
        if session.get(CoverImage, cover_id) is not None:
            valid.append(cover_id)
    return sorted(set(valid))


def _list_snapshot(items: list[dict[str, object]]) -> dict[str, object]:
    ordered = sorted(items, key=lambda item: str(item["key"]))
    return {
        "shape": "list",
        "item_count": len(ordered),
        "digest": _json_digest(ordered),
        "items": ordered,
    }


def _serialize_link_decisions_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    if current_user is None:
        rows = list_cover_link_decisions_for_ops(
            session,
            cover_image_id=cover_image_id,
            include_inactive=False,
            limit=500,
        )
    else:
        rows = list_cover_link_decisions_for_owner(
            session,
            current_user=current_user,
            cover_image_id=cover_image_id,
            include_inactive=False,
            limit=500,
        )
    items = [
        {
            "key": f"{row.pair_key}|{row.decision_type}|{row.relationship_type}",
            "decision_id": row.id,
            "pair_key": row.pair_key,
            "source_cover_image_id": row.source_cover_image_id,
            "candidate_cover_image_id": row.candidate_cover_image_id,
            "decision_type": row.decision_type,
            "relationship_type": row.relationship_type,
            "source_match_candidate_id": row.source_match_candidate_id,
        }
        for row in rows
    ]
    return _list_snapshot(items)


def _serialize_relationship_graph_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    graph = (
        get_cover_relationship_graph_for_ops(session, center_cover_image_id=cover_image_id)
        if current_user is None
        else get_cover_relationship_graph_for_owner(
            session,
            center_cover_image_id=cover_image_id,
            current_user=current_user,
        )
    )
    nodes = [
        {
            "key": f"node:{node.cover_image_id}",
            "cover_image_id": node.cover_image_id,
            "decision_summary": node.decision_summary.model_dump(mode="json"),
            "inventory_copy_id": node.inventory.inventory_copy_id if node.inventory is not None else None,
        }
        for node in graph.nodes
    ]
    edges = [
        {
            "key": f"edge:{edge.source_cover_image_id}:{edge.candidate_cover_image_id}:{edge.decision_id}",
            "source_cover_image_id": edge.source_cover_image_id,
            "candidate_cover_image_id": edge.candidate_cover_image_id,
            "relationship_type": edge.relationship_type,
            "decision_type": edge.decision_type,
            "decision_id": edge.decision_id,
            "display_lane": edge.display_lane,
        }
        for edge in graph.edges
    ]
    items = sorted([*nodes, *edges], key=lambda item: str(item["key"]))
    return _list_snapshot(items)


def _serialize_duplicate_scan_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    payload = (
        duplicate_scan_candidates_for_ops(session, cover_image_id=cover_image_id)
        if current_user is None
        else duplicate_scan_candidates_for_cover_owner(
            session,
            cover_image_id=cover_image_id,
            current_user=current_user,
        )
    )
    items: list[dict[str, object]] = []
    for cluster in payload.touching_clusters:
        items.append(
            {
                "key": f"cluster:{cluster.cluster_key}",
                "classification": cluster.classification,
                "cluster_key": cluster.cluster_key,
                "cluster_size": cluster.cluster_size,
                "cover_image_ids": cluster.cover_image_ids,
                "evidence_strength": cluster.evidence_strength,
            }
        )
    for peer in payload.duplicate_peers:
        items.append(
            {
                "key": f"peer:{peer.pair_key}",
                "pair_key": peer.pair_key,
                "peer_cover_image_id": peer.peer_cover_image_id,
                "classification": peer.classification,
                "evidence_labels": [
                    label
                    for label, enabled in peer.evidences.model_dump(mode="json").items()
                    if enabled not in (False, [], None)
                ],
            }
        )
    for suppressed in payload.suppressed_pairs_touching_focal:
        items.append(
            {
                "key": f"suppressed:{suppressed.pair_key}",
                "pair_key": suppressed.pair_key,
                "suppressed_signal_labels": suppressed.suppressed_signal_labels,
            }
        )
    return _list_snapshot(items)


def _serialize_variant_family_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    payload = (
        variant_family_candidates_for_ops(session, cover_image_id=cover_image_id)
        if current_user is None
        else variant_family_candidates_for_cover_owner(
            session,
            cover_image_id=cover_image_id,
            current_user=current_user,
        )
    )
    items: list[dict[str, object]] = []
    for cluster in payload.touching_clusters:
        items.append(
            {
                "key": f"cluster:{cluster.cluster_key}",
                "classification": cluster.classification,
                "cluster_key": cluster.cluster_key,
                "cluster_size": cluster.cluster_size,
                "cover_image_ids": cluster.cover_image_ids,
                "evidence_strength": cluster.evidence_strength,
            }
        )
    for peer in payload.variant_peers:
        items.append(
            {
                "key": f"peer:{peer.pair_key}",
                "pair_key": peer.pair_key,
                "peer_cover_image_id": peer.peer_cover_image_id,
                "classification": peer.classification,
                "evidence_labels": [
                    label
                    for label, enabled in peer.evidences.model_dump(mode="json").items()
                    if enabled not in (False, [], None)
                ],
            }
        )
    for suppressed in payload.suppressed_pairs_touching_focal:
        items.append(
            {
                "key": f"suppressed:{suppressed.pair_key}",
                "pair_key": suppressed.pair_key,
                "suppressed_signal_labels": suppressed.suppressed_signal_labels,
            }
        )
    return _list_snapshot(items)


def _serialize_persisted_canonical_suggestions_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    rows = (
        list_canonical_issue_suggestions_for_cover_ops(session, cover_image_id=cover_image_id)
        if current_user is None
        else list_canonical_issue_suggestions_for_cover_owner(
            session,
            cover_image_id=cover_image_id,
            current_user=current_user,
        )
    )
    items = [
        {
            "key": f"{row.suggestion_type}|{row.canonical_issue_id}|{row.suggested_metadata_identity_key or ''}",
            "canonical_issue_id": row.canonical_issue_id,
            "canonical_series_id": row.canonical_series_id,
            "canonical_publisher_id": row.canonical_publisher_id,
            "suggested_metadata_identity_key": row.suggested_metadata_identity_key,
            "suggestion_type": row.suggestion_type,
            "confidence_bucket": row.confidence_bucket,
            "deterministic_score": row.deterministic_score,
            "suppression_reason": row.suppression_reason,
        }
        for row in rows
    ]
    return _list_snapshot(items)


def _serialize_replayed_canonical_suggestions_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    cover = get_cover_or_404(session, cover_image_id)
    specs = _build_suggestion_specs(session, cover=cover, current_user=current_user)
    items = [
        {
            "key": f"{spec.suggestion_type}|{spec.canonical_issue_id}|{spec.suggested_metadata_identity_key or ''}",
            "canonical_issue_id": spec.canonical_issue_id,
            "canonical_series_id": spec.canonical_series_id,
            "canonical_publisher_id": spec.canonical_publisher_id,
            "suggested_metadata_identity_key": spec.suggested_metadata_identity_key,
            "suggestion_type": spec.suggestion_type,
            "confidence_bucket": spec.confidence_bucket,
            "deterministic_score": spec.deterministic_score,
            "suppression_reason": spec.suppression_reason,
        }
        for spec in specs
    ]
    return _list_snapshot(items)


def _serialize_persisted_conflicts_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    response = (
        list_relationship_conflicts_for_cover_ops(session, cover_image_id=cover_image_id)
        if current_user is None
        else list_relationship_conflicts_for_cover_owner(
            session,
            cover_image_id=cover_image_id,
            current_user=current_user,
        )
    )
    items = [
        {
            "key": row.conflict_key,
            "conflict_type": row.conflict_type,
            "severity": row.severity,
            "source_cover_image_id": row.source_cover_image_id,
            "related_cover_image_id": row.related_cover_image_id,
            "link_decision_id": row.link_decision_id,
            "match_candidate_id": row.match_candidate_id,
            "canonical_issue_suggestion_id": row.canonical_issue_suggestion_id,
        }
        for row in response.conflicts
    ]
    return _list_snapshot(items)


def _serialize_replayed_conflicts_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User | None,
) -> dict[str, object]:
    scope = None if current_user is None else frozenset(_cover_scope_for_owner(session, current_user=current_user))
    specs = [spec for spec in _build_conflict_specs(session, scope=scope) if cover_image_id in {spec.source_cover_image_id, spec.related_cover_image_id}]
    items = [
        {
            "key": spec.conflict_key,
            "conflict_type": spec.conflict_type,
            "severity": spec.severity,
            "source_cover_image_id": spec.source_cover_image_id,
            "related_cover_image_id": spec.related_cover_image_id,
            "link_decision_id": spec.link_decision_id,
            "match_candidate_id": spec.match_candidate_id,
            "canonical_issue_suggestion_id": spec.canonical_issue_suggestion_id,
        }
        for spec in specs
    ]
    return _list_snapshot(items)


def _pipeline_component(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "shape": str(snapshot.get("shape") or "flat"),
        "digest": str(snapshot.get("digest") or _json_digest(snapshot)),
        "item_count": int(snapshot.get("item_count") or len(list(snapshot.get("items") or []))),
    }


def _snapshot_for_type(
    session: Session,
    *,
    replay_type: str,
    cover_image_id: int,
    current_user: User | None,
    replay: bool,
) -> dict[str, object]:
    if replay_type == "link_decisions":
        return _serialize_link_decisions_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
    if replay_type == "relationship_graph":
        return _serialize_relationship_graph_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
    if replay_type == "duplicate_scan":
        return _serialize_duplicate_scan_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
    if replay_type == "variant_family":
        return _serialize_variant_family_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
    if replay_type == "canonical_issue_suggestions":
        return (
            _serialize_replayed_canonical_suggestions_for_cover(
                session, cover_image_id=cover_image_id, current_user=current_user
            )
            if replay
            else _serialize_persisted_canonical_suggestions_for_cover(
                session, cover_image_id=cover_image_id, current_user=current_user
            )
        )
    if replay_type == "relationship_conflicts":
        return (
            _serialize_replayed_conflicts_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
            if replay
            else _serialize_persisted_conflicts_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
        )
    if replay_type == "full_relationship_pipeline":
        link = _serialize_link_decisions_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
        graph = _serialize_relationship_graph_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
        duplicate = _serialize_duplicate_scan_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
        variant = _serialize_variant_family_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
        suggestions = (
            _serialize_replayed_canonical_suggestions_for_cover(
                session, cover_image_id=cover_image_id, current_user=current_user
            )
            if replay
            else _serialize_persisted_canonical_suggestions_for_cover(
                session, cover_image_id=cover_image_id, current_user=current_user
            )
        )
        conflicts = (
            _serialize_replayed_conflicts_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
            if replay
            else _serialize_persisted_conflicts_for_cover(session, cover_image_id=cover_image_id, current_user=current_user)
        )
        components = {
            "link_decisions": _pipeline_component(link),
            "relationship_graph": _pipeline_component(graph),
            "duplicate_scan": _pipeline_component(duplicate),
            "variant_family": _pipeline_component(variant),
            "canonical_issue_suggestions": _pipeline_component(suggestions),
            "relationship_conflicts": _pipeline_component(conflicts),
        }
        return {
            "shape": "pipeline",
            "digest": _json_digest(components),
            "components": components,
        }
    raise HTTPException(status_code=400, detail="Unsupported relationship replay type")


def _resolve_cover_ids_for_owner(
    session: Session,
    *,
    current_user: User,
    requested_cover_ids: list[int],
) -> list[int]:
    normalized = _normalize_cover_ids(requested_cover_ids)
    if normalized:
        return _validate_cover_ids_for_owner(session, current_user=current_user, cover_ids=normalized)
    return _cover_scope_for_owner(session, current_user=current_user)


def _resolve_cover_ids_for_ops(session: Session, *, requested_cover_ids: list[int]) -> list[int]:
    normalized = _normalize_cover_ids(requested_cover_ids)
    if normalized:
        return _validate_cover_ids_for_ops(session, cover_ids=normalized)
    return _cover_scope_for_ops(session)


def _create_replay_run(
    session: Session,
    *,
    actor_user_id: int | None,
    replay_type: str,
    cover_ids: list[int],
    current_user: User | None,
) -> RelationshipReplayRunRead:
    now = _now()
    run = RelationshipReplayRun(
        replay_type=replay_type,
        status="pending",
        total_items=len(cover_ids),
        changed_items=0,
        unchanged_items=0,
        failed_items=0,
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
        created_by=actor_user_id,
        replay_version=RELATIONSHIP_REPLAY_VERSION,
    )
    session.add(run)
    session.flush()
    if run.id is None:
        raise ValueError("Failed to create relationship replay run")
    for cover_id in cover_ids:
        try:
            previous_snapshot = _snapshot_for_type(
                session,
                replay_type=replay_type,
                cover_image_id=cover_id,
                current_user=current_user,
                replay=False,
            )
        except Exception as exc:
            previous_snapshot = {
                "shape": "flat",
                "baseline_error": exc.__class__.__name__,
            }
        session.add(
            RelationshipReplayItem(
                replay_run_id=run.id,
                cover_image_id=cover_id,
                relationship_key=f"cover:{cover_id}",
                status="pending",
                previous_snapshot_json=previous_snapshot,
                replay_snapshot_json={},
                diff_summary_json={},
                last_error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
        )
    session.flush()
    record_metadata_audit(
        session,
        entity_type="relationship_replay_run",
        entity_id=run.id,
        action="relationship_replay_run_created",
        before_snapshot=None,
        after_snapshot=_run_snapshot_public(run),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(run)
    return relationship_replay_run_entity_to_read(session, run)


def create_relationship_replay_run_for_owner(
    session: Session,
    *,
    current_user: User,
    payload: RelationshipReplayCreatePayload,
) -> RelationshipReplayRunRead:
    cover_ids = _resolve_cover_ids_for_owner(session, current_user=current_user, requested_cover_ids=payload.cover_image_ids)
    return _create_replay_run(
        session,
        actor_user_id=current_user.id,
        replay_type=payload.replay_type,
        cover_ids=cover_ids,
        current_user=current_user,
    )


def create_relationship_replay_run_for_ops(
    session: Session,
    *,
    actor_user_id: int | None,
    payload: RelationshipReplayCreatePayload,
) -> RelationshipReplayRunRead:
    cover_ids = _resolve_cover_ids_for_ops(session, requested_cover_ids=payload.cover_image_ids)
    return _create_replay_run(
        session,
        actor_user_id=actor_user_id,
        replay_type=payload.replay_type,
        cover_ids=cover_ids,
        current_user=None,
    )


def get_relationship_replay_run_for_owner_or_404(
    session: Session,
    *,
    current_user: User,
    replay_id: int,
) -> RelationshipReplayRun:
    run = session.get(RelationshipReplayRun, replay_id)
    if run is None or run.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Relationship replay run not found")
    return run


def get_relationship_replay_run_for_ops_or_404(session: Session, *, replay_id: int) -> RelationshipReplayRun:
    run = session.get(RelationshipReplayRun, replay_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Relationship replay run not found")
    return run


def list_relationship_replay_runs_for_owner(
    session: Session,
    *,
    current_user: User,
    limit: int = 25,
) -> list[RelationshipReplayRunRead]:
    rows = session.exec(
        select(RelationshipReplayRun)
        .where(RelationshipReplayRun.created_by == current_user.id)
        .order_by(RelationshipReplayRun.created_at.desc(), RelationshipReplayRun.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [relationship_replay_run_entity_to_read(session, row) for row in rows]


def list_relationship_replay_runs_for_ops(session: Session, *, limit: int = 25) -> list[RelationshipReplayRunRead]:
    rows = session.exec(
        select(RelationshipReplayRun)
        .order_by(RelationshipReplayRun.created_at.desc(), RelationshipReplayRun.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [relationship_replay_run_entity_to_read(session, row) for row in rows]


def get_relationship_replay_run_detail_for_owner(
    session: Session,
    *,
    current_user: User,
    replay_id: int,
) -> RelationshipReplayRunRead:
    return relationship_replay_run_entity_to_read(
        session,
        get_relationship_replay_run_for_owner_or_404(session, current_user=current_user, replay_id=replay_id),
    )


def get_relationship_replay_run_detail_for_ops(
    session: Session,
    *,
    replay_id: int,
) -> RelationshipReplayRunRead:
    return relationship_replay_run_entity_to_read(
        session,
        get_relationship_replay_run_for_ops_or_404(session, replay_id=replay_id),
    )


def _recompute_run_summary(run: RelationshipReplayRun, items: list[RelationshipReplayItem]) -> None:
    counts = Counter(item.status for item in items)
    run.total_items = len(items)
    run.changed_items = counts.get("changed", 0)
    run.unchanged_items = counts.get("unchanged", 0)
    run.failed_items = counts.get("failed", 0)
    if run.status == "cancelled":
        run.completed_at = run.completed_at or _now()
        return
    if counts.get("failed", 0) == len(items) and items:
        run.status = "failed"
    elif counts.get("changed", 0) > 0 or counts.get("failed", 0) > 0:
        run.status = "completed_with_changes"
    else:
        run.status = "completed"
    run.completed_at = _now()


def _start_replay_run(
    session: Session,
    *,
    run: RelationshipReplayRun,
    actor_user_id: int | None,
    current_user: User | None,
) -> RelationshipReplayRunRead:
    if run.id is None:
        raise HTTPException(status_code=404, detail="Relationship replay run not found")
    if run.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled relationship replay runs cannot be started")
    before = _run_snapshot_public(run)
    run.status = "running"
    run.started_at = _now()
    run.completed_at = None
    run.updated_at = _now()
    session.add(run)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="relationship_replay_run",
        entity_id=run.id,
        action="relationship_replay_run_started",
        before_snapshot=before,
        after_snapshot=_run_snapshot_public(run),
        actor_user_id=actor_user_id,
    )
    items = session.exec(
        select(RelationshipReplayItem)
        .where(RelationshipReplayItem.replay_run_id == run.id)
        .order_by(RelationshipReplayItem.relationship_key.asc(), RelationshipReplayItem.id.asc())
    ).all()
    for item in items:
        if item.status == "cancelled":
            continue
        item.status = "running"
        item.updated_at = _now()
        item.last_error = None
        session.add(item)
        session.flush()
        try:
            if item.cover_image_id is None:
                raise ValueError("relationship replay item missing cover_image_id")
            replay_snapshot = _snapshot_for_type(
                session,
                replay_type=run.replay_type,
                cover_image_id=item.cover_image_id,
                current_user=current_user,
                replay=True,
            )
            diff_summary = _bounded_diff_summary(_summarize_diff(item.previous_snapshot_json or {}, replay_snapshot))
            item.replay_snapshot_json = replay_snapshot
            item.diff_summary_json = diff_summary
            item.status = "changed" if diff_summary.get("status") == "changed" else "unchanged"
            item.completed_at = _now()
            item.updated_at = _now()
            session.add(item)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="relationship_replay_item",
                entity_id=item.id or -1,
                action=f"relationship_replay_item_{item.status}",
                before_snapshot=None,
                after_snapshot=relationship_replay_item_entity_to_read(item).model_dump(mode="json"),
                actor_user_id=actor_user_id,
            )
        except Exception as exc:
            item.replay_snapshot_json = {}
            item.diff_summary_json = {}
            item.status = "failed"
            item.last_error = f"{exc.__class__.__name__}: {exc}"[:2000]
            item.completed_at = _now()
            item.updated_at = _now()
            session.add(item)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="relationship_replay_item",
                entity_id=item.id or -1,
                action="relationship_replay_item_failed",
                before_snapshot=None,
                after_snapshot=relationship_replay_item_entity_to_read(item).model_dump(mode="json"),
                actor_user_id=actor_user_id,
            )
    refreshed_items = session.exec(
        select(RelationshipReplayItem).where(RelationshipReplayItem.replay_run_id == run.id).order_by(RelationshipReplayItem.id.asc())
    ).all()
    _recompute_run_summary(run, refreshed_items)
    run.updated_at = _now()
    session.add(run)
    session.flush()
    final_event = {
        "completed": "relationship_replay_run_completed",
        "completed_with_changes": "relationship_replay_run_completed_with_changes",
        "failed": "relationship_replay_run_failed",
    }.get(run.status)
    if final_event:
        record_metadata_audit(
            session,
            entity_type="relationship_replay_run",
            entity_id=run.id,
            action=final_event,
            before_snapshot=before,
            after_snapshot=_run_snapshot_public(run),
            actor_user_id=actor_user_id,
        )
    session.commit()
    session.refresh(run)
    return relationship_replay_run_entity_to_read(session, run)


def start_relationship_replay_run_for_owner(
    session: Session,
    *,
    current_user: User,
    replay_id: int,
) -> RelationshipReplayRunRead:
    run = get_relationship_replay_run_for_owner_or_404(session, current_user=current_user, replay_id=replay_id)
    return _start_replay_run(session, run=run, actor_user_id=current_user.id, current_user=current_user)


def start_relationship_replay_run_for_ops(
    session: Session,
    *,
    replay_id: int,
    actor_user_id: int | None,
) -> RelationshipReplayRunRead:
    run = get_relationship_replay_run_for_ops_or_404(session, replay_id=replay_id)
    return _start_replay_run(session, run=run, actor_user_id=actor_user_id, current_user=None)


def _cancel_replay_run(
    session: Session,
    *,
    run: RelationshipReplayRun,
    actor_user_id: int | None,
) -> RelationshipReplayRunRead:
    if run.id is None:
        raise HTTPException(status_code=404, detail="Relationship replay run not found")
    before = _run_snapshot_public(run)
    items = session.exec(
        select(RelationshipReplayItem).where(RelationshipReplayItem.replay_run_id == run.id).order_by(RelationshipReplayItem.id.asc())
    ).all()
    for item in items:
        if item.status == "pending":
            item.status = "cancelled"
            item.updated_at = _now()
            item.completed_at = _now()
            session.add(item)
    run.status = "cancelled"
    run.completed_at = _now()
    run.updated_at = _now()
    session.add(run)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="relationship_replay_run",
        entity_id=run.id,
        action="relationship_replay_run_cancelled",
        before_snapshot=before,
        after_snapshot=_run_snapshot_public(run),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(run)
    return relationship_replay_run_entity_to_read(session, run)


def cancel_relationship_replay_run_for_owner(
    session: Session,
    *,
    current_user: User,
    replay_id: int,
) -> RelationshipReplayRunRead:
    run = get_relationship_replay_run_for_owner_or_404(session, current_user=current_user, replay_id=replay_id)
    return _cancel_replay_run(session, run=run, actor_user_id=current_user.id)


def cancel_relationship_replay_run_for_ops(
    session: Session,
    *,
    replay_id: int,
    actor_user_id: int | None,
) -> RelationshipReplayRunRead:
    run = get_relationship_replay_run_for_ops_or_404(session, replay_id=replay_id)
    return _cancel_replay_run(session, run=run, actor_user_id=actor_user_id)
