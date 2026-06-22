from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    ComicIssue,
    CoverImage,
    CoverImageFingerprint,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    CoverImageOcrReconciliationWarning,
    CoverRelationshipConflict,
    InventoryCopy,
    User,
    Variant,
)
from app.schemas.relationship_conflicts import (
    CoverRelationshipConflictActionResponse,
    CoverRelationshipConflictDetectResponse,
    CoverRelationshipConflictListResponse,
    CoverRelationshipConflictRead,
    RelationshipConflictStatus,
)
from app.services.cover_link_decisions import cover_link_pair_key, get_cover_or_404, owner_can_access_cover
from app.services.duplicate_scan_intelligence import owner_cover_scope
from app.services.metadata_audits import record_metadata_audit


ACTIVE_SUGGESTION_STATES = {"pending", "approved"}
PAIR_RELATIONSHIP_SIGNALS = {
    "duplicate_scan",
    "same_cover",
    "same_issue",
    "variant_family",
    "unrelated",
}
GROUPING_TO_SIGNAL = {
    "probable_duplicate_scan": "duplicate_scan",
    "probable_same_cover": "same_cover",
    "probable_same_issue": "same_issue",
    "probable_variant_family": "variant_family",
}
SEVERITY_BY_TYPE = {
    "duplicate_scan_vs_variant_family": "warning",
    "same_cover_vs_variant_family": "critical",
    "same_issue_vs_unrelated": "critical",
    "approved_link_vs_rejected_link": "critical",
    "canonical_suggestion_mismatch": "warning",
    "duplicate_scan_different_canonical_issue": "warning",
    "variant_family_same_fingerprint": "warning",
    "relationship_cycle_warning": "info",
    "stale_confidence_after_decision": "info",
    "preorder_not_in_hand_reconciliation_warning": "info",
}


@dataclass
class ConflictSpec:
    conflict_type: str
    severity: str
    source_cover_image_id: int | None
    related_cover_image_id: int | None
    link_decision_id: int | None
    match_candidate_id: int | None
    canonical_issue_suggestion_id: int | None
    conflict_key: str
    evidence_json: dict[str, object]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _pair_tuple(left_id: int, right_id: int) -> tuple[int, int]:
    left, right = int(left_id), int(right_id)
    return (left, right) if left < right else (right, left)


def _stable_digest(values: list[int]) -> str:
    payload = "|".join(str(value) for value in sorted(values)).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:24]


def _serialize_conflict(row: CoverRelationshipConflict) -> CoverRelationshipConflictRead:
    if row.id is None:
        raise ValueError("relationship conflict row must be flushed before serialization")
    return CoverRelationshipConflictRead(
        id=row.id,
        conflict_type=row.conflict_type,  # type: ignore[arg-type]
        severity=row.severity,  # type: ignore[arg-type]
        source_cover_image_id=row.source_cover_image_id,
        related_cover_image_id=row.related_cover_image_id,
        link_decision_id=row.link_decision_id,
        match_candidate_id=row.match_candidate_id,
        canonical_issue_suggestion_id=row.canonical_issue_suggestion_id,
        conflict_key=row.conflict_key,
        status=row.status,  # type: ignore[arg-type]
        evidence_json=dict(row.evidence_json or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
        acknowledged_at=row.acknowledged_at,
        dismissed_at=row.dismissed_at,
        resolved_at=row.resolved_at,
    )


def _conflict_snapshot(row: CoverRelationshipConflict) -> dict[str, object]:
    return _serialize_conflict(row).model_dump(mode="json")


def _summary_counts(rows: list[CoverRelationshipConflict]) -> dict[str, int]:
    return {
        "total_count": len(rows),
        "open_count": sum(1 for row in rows if row.status == "open"),
        "acknowledged_count": sum(1 for row in rows if row.status == "acknowledged"),
        "dismissed_count": sum(1 for row in rows if row.status == "dismissed"),
        "resolved_count": sum(1 for row in rows if row.status == "resolved"),
    }


def _normalize_reason(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def get_relationship_conflict_or_404(session: Session, conflict_id: int) -> CoverRelationshipConflict:
    row = session.get(CoverRelationshipConflict, conflict_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Relationship conflict not found")
    return row


def _owner_scope_or_401(session: Session, current_user: User) -> frozenset[int]:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return owner_cover_scope(session, user_id=current_user.id)


def _owner_can_access_conflict(
    session: Session,
    *,
    row: CoverRelationshipConflict,
    current_user: User,
    scope: frozenset[int],
) -> bool:
    for cover_id in [row.source_cover_image_id, row.related_cover_image_id]:
        if cover_id is None:
            continue
        if cover_id not in scope:
            return False
        cover = session.get(CoverImage, cover_id)
        if cover is None or not owner_can_access_cover(session, cover=cover, current_user=current_user):
            return False
    return True


def _target_token_for_suggestion(row: CanonicalIssueLinkSuggestion) -> str | None:
    if row.canonical_issue_id is not None:
        return f"issue:{int(row.canonical_issue_id)}"
    if row.suggested_metadata_identity_key:
        return f"identity:{row.suggested_metadata_identity_key}"
    return None


def _cover_inventory_issue_tokens(
    session: Session,
    *,
    cover_ids: set[int],
) -> dict[int, set[str]]:
    if not cover_ids:
        return {}
    rows = session.exec(
        select(CoverImage.id, InventoryCopy.catalog_issue_id)
        .join(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .where(
            CoverImage.id.in_(sorted(cover_ids)),
            InventoryCopy.catalog_issue_id.is_not(None),
        )
    ).all()
    out: dict[int, set[str]] = defaultdict(set)
    for cover_id, issue_id in rows:
        if issue_id is not None:
            out[int(cover_id)].add(f"issue:{int(issue_id)}")
    return dict(out)


def _exact_fingerprint_map(
    session: Session,
    *,
    cover_ids: set[int],
) -> dict[int, set[tuple[str, str, str]]]:
    if not cover_ids:
        return {}
    rows = session.exec(
        select(CoverImageFingerprint)
        .where(CoverImageFingerprint.cover_image_id.in_(sorted(cover_ids)))
        .order_by(CoverImageFingerprint.cover_image_id.asc(), CoverImageFingerprint.id.asc())
    ).all()
    out: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
    for row in rows:
        if row.cover_image_id is None:
            continue
        out[int(row.cover_image_id)].add(
            (str(row.fingerprint_type), str(row.derivative_type), str(row.fingerprint_value))
        )
    return dict(out)


def _cover_map(
    session: Session,
    *,
    cover_ids: set[int],
) -> dict[int, CoverImage]:
    if not cover_ids:
        return {}
    rows = session.exec(select(CoverImage).where(CoverImage.id.in_(sorted(cover_ids)))).all()
    return {int(row.id): row for row in rows if row.id is not None}


def _active_decision_rows(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> list[CoverImageLinkDecision]:
    rows = session.exec(
        select(CoverImageLinkDecision)
        .where(CoverImageLinkDecision.decision_state == "active")
        .order_by(CoverImageLinkDecision.id.asc())
    ).all()
    if scope is None:
        return list(rows)
    return [
        row
        for row in rows
        if int(row.source_cover_image_id) in scope and int(row.candidate_cover_image_id) in scope
    ]


def _active_match_candidate_rows(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> list[CoverImageMatchCandidate]:
    rows = session.exec(
        select(CoverImageMatchCandidate)
        .where(CoverImageMatchCandidate.dismissed_at.is_(None))  # type: ignore[union-attr]
        .order_by(CoverImageMatchCandidate.id.asc())
    ).all()
    if scope is None:
        return list(rows)
    return [
        row
        for row in rows
        if int(row.source_cover_image_id) in scope and int(row.candidate_cover_image_id) in scope
    ]


def _active_canonical_suggestion_rows(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> list[CanonicalIssueLinkSuggestion]:
    rows = session.exec(
        select(CanonicalIssueLinkSuggestion)
        .where(CanonicalIssueLinkSuggestion.review_state.in_(tuple(sorted(ACTIVE_SUGGESTION_STATES))))
        .order_by(CanonicalIssueLinkSuggestion.id.asc())
    ).all()
    if scope is None:
        return list(rows)
    return [row for row in rows if int(row.cover_image_id) in scope]


def _open_reconciliation_warning_rows(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> list[CoverImageOcrReconciliationWarning]:
    rows = session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(CoverImageOcrReconciliationWarning.status == "open")
        .order_by(CoverImageOcrReconciliationWarning.id.asc())
    ).all()
    if scope is None:
        return list(rows)
    return [row for row in rows if int(row.cover_image_id) in scope]


def _build_pair_signal_maps(
    *,
    decision_rows: list[CoverImageLinkDecision],
    match_rows: list[CoverImageMatchCandidate],
) -> tuple[
    dict[tuple[int, int], list[CoverImageLinkDecision]],
    dict[tuple[int, int], list[CoverImageMatchCandidate]],
    dict[tuple[int, int], set[str]],
]:
    decisions_by_pair: dict[tuple[int, int], list[CoverImageLinkDecision]] = defaultdict(list)
    matches_by_pair: dict[tuple[int, int], list[CoverImageMatchCandidate]] = defaultdict(list)
    signals_by_pair: dict[tuple[int, int], set[str]] = defaultdict(set)

    for row in decision_rows:
        pair = _pair_tuple(row.source_cover_image_id, row.candidate_cover_image_id)
        decisions_by_pair[pair].append(row)
        if row.decision_type == "approved_link" and row.relationship_type in PAIR_RELATIONSHIP_SIGNALS:
            signals_by_pair[pair].add(str(row.relationship_type))
        if row.decision_type == "rejected_link" and row.relationship_type == "unrelated":
            signals_by_pair[pair].add("unrelated")

    for row in match_rows:
        pair = _pair_tuple(row.source_cover_image_id, row.candidate_cover_image_id)
        matches_by_pair[pair].append(row)
        if row.grouping_type in GROUPING_TO_SIGNAL:
            signals_by_pair[pair].add(GROUPING_TO_SIGNAL[str(row.grouping_type)])

    return dict(decisions_by_pair), dict(matches_by_pair), dict(signals_by_pair)


def _approved_link_graph_specs(
    *,
    decisions_by_pair: dict[tuple[int, int], list[CoverImageLinkDecision]],
) -> list[ConflictSpec]:
    adjacency: dict[int, set[int]] = defaultdict(set)
    edge_ids_by_pair: dict[tuple[int, int], list[int]] = defaultdict(list)
    rels_by_pair: dict[tuple[int, int], set[str]] = defaultdict(set)
    for pair, rows in decisions_by_pair.items():
        approved_rows = [row for row in rows if row.decision_type == "approved_link" and row.relationship_type != "unrelated"]
        if not approved_rows:
            continue
        left, right = pair
        adjacency[left].add(right)
        adjacency[right].add(left)
        edge_ids_by_pair[pair] = [int(row.id) for row in approved_rows if row.id is not None]
        rels_by_pair[pair] = {str(row.relationship_type) for row in approved_rows}

    seen: set[int] = set()
    specs: list[ConflictSpec] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        stack = [start]
        component_nodes: set[int] = set()
        while stack:
            node = stack.pop()
            if node in component_nodes:
                continue
            component_nodes.add(node)
            seen.add(node)
            stack.extend(sorted(adjacency[node] - component_nodes))
        component_pairs = [
            pair
            for pair in sorted(edge_ids_by_pair)
            if pair[0] in component_nodes and pair[1] in component_nodes
        ]
        if len(component_nodes) < 3 or len(component_pairs) < len(component_nodes):
            continue
        node_ids = sorted(component_nodes)
        edge_ids = sorted({edge_id for pair in component_pairs for edge_id in edge_ids_by_pair[pair]})
        relationship_types = sorted({rel for pair in component_pairs for rel in rels_by_pair[pair]})
        specs.append(
            ConflictSpec(
                conflict_type="relationship_cycle_warning",
                severity=SEVERITY_BY_TYPE["relationship_cycle_warning"],
                source_cover_image_id=node_ids[0],
                related_cover_image_id=node_ids[-1],
                link_decision_id=edge_ids[0] if edge_ids else None,
                match_candidate_id=None,
                canonical_issue_suggestion_id=None,
                conflict_key=f"relationship_cycle_warning:{_stable_digest(node_ids)}",
                evidence_json={
                    "cycle_cover_image_ids": node_ids,
                    "decision_ids": edge_ids,
                    "relationship_types": relationship_types,
                },
            )
        )
    return specs


def _build_conflict_specs(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> list[ConflictSpec]:
    decision_rows = _active_decision_rows(session, scope=scope)
    match_rows = _active_match_candidate_rows(session, scope=scope)
    suggestion_rows = _active_canonical_suggestion_rows(session, scope=scope)
    warning_rows = _open_reconciliation_warning_rows(session, scope=scope)
    decisions_by_pair, matches_by_pair, signals_by_pair = _build_pair_signal_maps(
        decision_rows=decision_rows,
        match_rows=match_rows,
    )

    all_cover_ids: set[int] = set()
    for left_id, right_id in signals_by_pair:
        all_cover_ids.add(int(left_id))
        all_cover_ids.add(int(right_id))
    for row in suggestion_rows:
        all_cover_ids.add(int(row.cover_image_id))
    for row in warning_rows:
        all_cover_ids.add(int(row.cover_image_id))
    covers_by_id = _cover_map(session, cover_ids=all_cover_ids)
    fingerprint_by_cover = _exact_fingerprint_map(session, cover_ids=all_cover_ids)
    inventory_targets = _cover_inventory_issue_tokens(session, cover_ids=all_cover_ids)

    suggestion_targets: dict[int, set[str]] = defaultdict(set)
    suggestion_ids_by_cover: dict[int, list[int]] = defaultdict(list)
    for row in suggestion_rows:
        token = _target_token_for_suggestion(row)
        if token is None:
            continue
        suggestion_targets[int(row.cover_image_id)].add(token)
        if row.id is not None:
            suggestion_ids_by_cover[int(row.cover_image_id)].append(int(row.id))
    cover_targets = {
        cover_id: set(tokens) | inventory_targets.get(cover_id, set())
        for cover_id, tokens in suggestion_targets.items()
    }
    for cover_id, inventory_tokens in inventory_targets.items():
        cover_targets.setdefault(cover_id, set()).update(inventory_tokens)

    specs: list[ConflictSpec] = []
    for pair in sorted(signals_by_pair):
        left_id, right_id = pair
        signals = signals_by_pair[pair]
        decision_ids = sorted(
            row.id for row in decisions_by_pair.get(pair, []) if row.id is not None
        )
        match_ids = sorted(row.id for row in matches_by_pair.get(pair, []) if row.id is not None)
        link_decision_id = decision_ids[0] if decision_ids else None
        match_candidate_id = match_ids[0] if match_ids else None
        evidence_base = {
            "pair_key": cover_link_pair_key(left_id, right_id),
            "signals": sorted(signals),
            "decision_ids": decision_ids,
            "match_candidate_ids": match_ids,
        }

        if "duplicate_scan" in signals and "variant_family" in signals:
            specs.append(
                ConflictSpec(
                    conflict_type="duplicate_scan_vs_variant_family",
                    severity=SEVERITY_BY_TYPE["duplicate_scan_vs_variant_family"],
                    source_cover_image_id=left_id,
                    related_cover_image_id=right_id,
                    link_decision_id=link_decision_id,
                    match_candidate_id=match_candidate_id,
                    canonical_issue_suggestion_id=None,
                    conflict_key=f"duplicate_scan_vs_variant_family:{left_id}:{right_id}",
                    evidence_json=evidence_base,
                )
            )

        if "same_cover" in signals and "variant_family" in signals:
            specs.append(
                ConflictSpec(
                    conflict_type="same_cover_vs_variant_family",
                    severity=SEVERITY_BY_TYPE["same_cover_vs_variant_family"],
                    source_cover_image_id=left_id,
                    related_cover_image_id=right_id,
                    link_decision_id=link_decision_id,
                    match_candidate_id=match_candidate_id,
                    canonical_issue_suggestion_id=None,
                    conflict_key=f"same_cover_vs_variant_family:{left_id}:{right_id}",
                    evidence_json=evidence_base,
                )
            )

        if "same_issue" in signals and "unrelated" in signals:
            specs.append(
                ConflictSpec(
                    conflict_type="same_issue_vs_unrelated",
                    severity=SEVERITY_BY_TYPE["same_issue_vs_unrelated"],
                    source_cover_image_id=left_id,
                    related_cover_image_id=right_id,
                    link_decision_id=link_decision_id,
                    match_candidate_id=match_candidate_id,
                    canonical_issue_suggestion_id=None,
                    conflict_key=f"same_issue_vs_unrelated:{left_id}:{right_id}",
                    evidence_json=evidence_base,
                )
            )

        pair_decisions = decisions_by_pair.get(pair, [])
        if any(row.decision_type == "approved_link" for row in pair_decisions) and any(
            row.decision_type == "rejected_link" for row in pair_decisions
        ):
            specs.append(
                ConflictSpec(
                    conflict_type="approved_link_vs_rejected_link",
                    severity=SEVERITY_BY_TYPE["approved_link_vs_rejected_link"],
                    source_cover_image_id=left_id,
                    related_cover_image_id=right_id,
                    link_decision_id=link_decision_id,
                    match_candidate_id=match_candidate_id,
                    canonical_issue_suggestion_id=None,
                    conflict_key=f"approved_link_vs_rejected_link:{left_id}:{right_id}",
                    evidence_json=evidence_base,
                )
            )

        left_suggestion_targets = suggestion_targets.get(left_id, set())
        right_suggestion_targets = suggestion_targets.get(right_id, set())
        left_targets = cover_targets.get(left_id, set())
        right_targets = cover_targets.get(right_id, set())
        suggestion_id = (
            min([*suggestion_ids_by_cover.get(left_id, []), *suggestion_ids_by_cover.get(right_id, [])])
            if suggestion_ids_by_cover.get(left_id) or suggestion_ids_by_cover.get(right_id)
            else None
        )
        mismatch_evidence = {
            **evidence_base,
            "source_suggestion_targets": sorted(left_suggestion_targets),
            "related_suggestion_targets": sorted(right_suggestion_targets),
            "source_targets": sorted(left_targets),
            "related_targets": sorted(right_targets),
        }
        suggestion_targets_disagree = (
            bool(left_suggestion_targets)
            and bool(right_suggestion_targets)
            and left_suggestion_targets.isdisjoint(right_suggestion_targets)
        )
        if suggestion_targets_disagree or (left_targets and right_targets and left_targets.isdisjoint(right_targets)):
            if signals.intersection({"same_cover", "same_issue", "duplicate_scan", "variant_family"}):
                specs.append(
                    ConflictSpec(
                        conflict_type="canonical_suggestion_mismatch",
                        severity=SEVERITY_BY_TYPE["canonical_suggestion_mismatch"],
                        source_cover_image_id=left_id,
                        related_cover_image_id=right_id,
                        link_decision_id=link_decision_id,
                        match_candidate_id=match_candidate_id,
                        canonical_issue_suggestion_id=suggestion_id,
                        conflict_key=f"canonical_suggestion_mismatch:{left_id}:{right_id}",
                        evidence_json=mismatch_evidence,
                    )
                )
            if "duplicate_scan" in signals:
                specs.append(
                    ConflictSpec(
                        conflict_type="duplicate_scan_different_canonical_issue",
                        severity=SEVERITY_BY_TYPE["duplicate_scan_different_canonical_issue"],
                        source_cover_image_id=left_id,
                        related_cover_image_id=right_id,
                        link_decision_id=link_decision_id,
                        match_candidate_id=match_candidate_id,
                        canonical_issue_suggestion_id=suggestion_id,
                        conflict_key=f"duplicate_scan_different_canonical_issue:{left_id}:{right_id}",
                        evidence_json=mismatch_evidence,
                    )
                )

        if "variant_family" in signals:
            cover_left = covers_by_id.get(left_id)
            cover_right = covers_by_id.get(right_id)
            shared_fingerprints = sorted(
                f"{fp_type}:{deriv_type}"
                for fp_type, deriv_type, value in fingerprint_by_cover.get(left_id, set())
                if (fp_type, deriv_type, value) in fingerprint_by_cover.get(right_id, set())
            )
            sha256_exact = (
                cover_left is not None
                and cover_right is not None
                and bool(cover_left.sha256_hash)
                and cover_left.sha256_hash == cover_right.sha256_hash
            )
            if sha256_exact or shared_fingerprints:
                specs.append(
                    ConflictSpec(
                        conflict_type="variant_family_same_fingerprint",
                        severity=SEVERITY_BY_TYPE["variant_family_same_fingerprint"],
                        source_cover_image_id=left_id,
                        related_cover_image_id=right_id,
                        link_decision_id=link_decision_id,
                        match_candidate_id=match_candidate_id,
                        canonical_issue_suggestion_id=suggestion_id,
                        conflict_key=f"variant_family_same_fingerprint:{left_id}:{right_id}",
                        evidence_json={
                            **evidence_base,
                            "sha256_exact_match": sha256_exact,
                            "shared_fingerprint_slots": shared_fingerprints,
                        },
                    )
                )

    specs.extend(_approved_link_graph_specs(decisions_by_pair=decisions_by_pair))

    referenced_match_ids = sorted(
        {
            int(row.source_match_candidate_id)
            for row in decision_rows
            if row.source_match_candidate_id is not None
        }
    )
    candidate_by_id: dict[int, CoverImageMatchCandidate] = {}
    if referenced_match_ids:
        candidate_rows = session.exec(
            select(CoverImageMatchCandidate).where(CoverImageMatchCandidate.id.in_(referenced_match_ids))
        ).all()
        candidate_by_id = {int(row.id): row for row in candidate_rows if row.id is not None}
    for row in decision_rows:
        if row.id is None or row.source_match_candidate_id is None:
            continue
        candidate = candidate_by_id.get(int(row.source_match_candidate_id))
        if candidate is None:
            continue
        if candidate.dismissed_at is None and candidate.updated_at <= row.updated_at:
            continue
        specs.append(
            ConflictSpec(
                conflict_type="stale_confidence_after_decision",
                severity=SEVERITY_BY_TYPE["stale_confidence_after_decision"],
                source_cover_image_id=int(row.source_cover_image_id),
                related_cover_image_id=int(row.candidate_cover_image_id),
                link_decision_id=int(row.id),
                match_candidate_id=int(candidate.id) if candidate.id is not None else None,
                canonical_issue_suggestion_id=None,
                conflict_key=f"stale_confidence_after_decision:{int(row.id)}",
                evidence_json={
                    "decision_updated_at": row.updated_at.isoformat(),
                    "match_candidate_updated_at": candidate.updated_at.isoformat(),
                    "match_candidate_dismissed_at": (
                        candidate.dismissed_at.isoformat() if candidate.dismissed_at is not None else None
                    ),
                    "confidence_bucket": candidate.confidence_bucket,
                    "grouping_type": candidate.grouping_type,
                },
            )
        )

    inventory_ids = {
        int(row.inventory_copy_id)
        for row in warning_rows
        if row.inventory_copy_id is not None
    }
    inventory_by_id: dict[int, InventoryCopy] = {}
    if inventory_ids:
        inventory_rows = session.exec(
            select(InventoryCopy).where(InventoryCopy.id.in_(sorted(inventory_ids)))
        ).all()
        inventory_by_id = {int(row.id): row for row in inventory_rows if row.id is not None}
    for row in warning_rows:
        if row.inventory_copy_id is None or row.id is None:
            continue
        inventory = inventory_by_id.get(int(row.inventory_copy_id))
        if inventory is None or inventory.order_status == "received":
            continue
        specs.append(
            ConflictSpec(
                conflict_type="preorder_not_in_hand_reconciliation_warning",
                severity=SEVERITY_BY_TYPE["preorder_not_in_hand_reconciliation_warning"],
                source_cover_image_id=int(row.cover_image_id),
                related_cover_image_id=None,
                link_decision_id=None,
                match_candidate_id=None,
                canonical_issue_suggestion_id=None,
                conflict_key=f"preorder_not_in_hand_reconciliation_warning:{int(row.id)}",
                evidence_json={
                    "ocr_reconciliation_warning_id": int(row.id),
                    "inventory_copy_id": int(row.inventory_copy_id),
                    "order_status": inventory.order_status,
                    "release_status": inventory.release_status,
                    "warning_type": row.warning_type,
                    "warning_message": row.message,
                },
            )
        )

    deduped: dict[str, ConflictSpec] = {}
    for spec in sorted(specs, key=lambda item: item.conflict_key):
        deduped[spec.conflict_key] = spec
    return list(deduped.values())


def _existing_conflict_rows(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> list[CoverRelationshipConflict]:
    stmt = select(CoverRelationshipConflict).order_by(CoverRelationshipConflict.id.asc())
    rows = session.exec(stmt).all()
    if scope is None:
        return list(rows)
    return [
        row
        for row in rows
        if (
            (row.source_cover_image_id is None or row.source_cover_image_id in scope)
            and (row.related_cover_image_id is None or row.related_cover_image_id in scope)
        )
    ]


def _persist_conflict_specs(
    session: Session,
    *,
    specs: list[ConflictSpec],
    scope: frozenset[int] | None,
    actor_user_id: int | None,
) -> list[CoverRelationshipConflict]:
    existing_rows = _existing_conflict_rows(session, scope=scope)
    existing_by_key = {row.conflict_key: row for row in existing_rows}
    desired_keys = {spec.conflict_key for spec in specs}
    now = utc_now()

    for spec in specs:
        row = existing_by_key.get(spec.conflict_key)
        if row is None:
            row = CoverRelationshipConflict(
                conflict_type=spec.conflict_type,
                severity=spec.severity,
                source_cover_image_id=spec.source_cover_image_id,
                related_cover_image_id=spec.related_cover_image_id,
                link_decision_id=spec.link_decision_id,
                match_candidate_id=spec.match_candidate_id,
                canonical_issue_suggestion_id=spec.canonical_issue_suggestion_id,
                conflict_key=spec.conflict_key,
                status="open",
                evidence_json=spec.evidence_json,
                created_at=now,
                updated_at=now,
                acknowledged_at=None,
                dismissed_at=None,
                resolved_at=None,
            )
            session.add(row)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="relationship_conflict",
                entity_id=row.id or -1,
                action="relationship_conflict_created",
                before_snapshot=None,
                after_snapshot=_conflict_snapshot(row),
                actor_user_id=actor_user_id,
            )
            existing_by_key[spec.conflict_key] = row
            continue

        before = _conflict_snapshot(row)
        row.conflict_type = spec.conflict_type
        row.severity = spec.severity
        row.source_cover_image_id = spec.source_cover_image_id
        row.related_cover_image_id = spec.related_cover_image_id
        row.link_decision_id = spec.link_decision_id
        row.match_candidate_id = spec.match_candidate_id
        row.canonical_issue_suggestion_id = spec.canonical_issue_suggestion_id
        row.evidence_json = spec.evidence_json
        row.updated_at = now
        if row.status == "resolved":
            row.status = "open"
            row.resolved_at = None
        session.add(row)
        if before != _conflict_snapshot(row):
            record_metadata_audit(
                session,
                entity_type="relationship_conflict",
                entity_id=row.id or -1,
                action="relationship_conflict_re_detected",
                before_snapshot=before,
                after_snapshot=_conflict_snapshot(row),
                actor_user_id=actor_user_id,
            )

    for row in existing_rows:
        if row.conflict_key in desired_keys or row.status == "resolved":
            continue
        before = _conflict_snapshot(row)
        row.status = "resolved"
        row.resolved_at = now
        row.updated_at = now
        session.add(row)
        record_metadata_audit(
            session,
            entity_type="relationship_conflict",
            entity_id=row.id or -1,
            action="relationship_conflict_resolved",
            before_snapshot=before,
            after_snapshot=_conflict_snapshot(row),
            actor_user_id=actor_user_id,
        )

    session.commit()
    present_rows = [
        row
        for row in _existing_conflict_rows(session, scope=scope)
        if row.conflict_key in desired_keys
    ]
    return sorted(present_rows, key=lambda row: (row.severity, row.conflict_type, row.conflict_key))


def _detect_and_persist(
    session: Session,
    *,
    scope: frozenset[int] | None,
    actor_user_id: int | None,
) -> CoverRelationshipConflictDetectResponse:
    specs = _build_conflict_specs(session, scope=scope)
    rows = _persist_conflict_specs(session, specs=specs, scope=scope, actor_user_id=actor_user_id)
    counts = _summary_counts(rows)
    return CoverRelationshipConflictDetectResponse(
        detected_count=len(rows),
        open_count=counts["open_count"],
        acknowledged_count=counts["acknowledged_count"],
        dismissed_count=counts["dismissed_count"],
        resolved_count=counts["resolved_count"],
        conflicts=[_serialize_conflict(row) for row in rows],
    )


def detect_relationship_conflicts_for_owner(
    session: Session,
    *,
    current_user: User,
) -> CoverRelationshipConflictDetectResponse:
    scope = _owner_scope_or_401(session, current_user)
    return _detect_and_persist(session, scope=scope, actor_user_id=current_user.id)


def detect_relationship_conflicts_for_ops(
    session: Session,
    *,
    actor_user_id: int | None,
) -> CoverRelationshipConflictDetectResponse:
    return _detect_and_persist(session, scope=None, actor_user_id=actor_user_id)


def _list_conflicts_from_rows(
    rows: list[CoverRelationshipConflict],
    *,
    severity: str,
    status: str,
    conflict_type: str,
) -> CoverRelationshipConflictListResponse:
    filtered = rows
    if severity != "all":
        filtered = [row for row in filtered if row.severity == severity]
    if status != "all":
        filtered = [row for row in filtered if row.status == status]
    if conflict_type != "all":
        filtered = [row for row in filtered if row.conflict_type == conflict_type]
    counts = _summary_counts(filtered)
    return CoverRelationshipConflictListResponse(
        conflicts=[_serialize_conflict(row) for row in filtered],
        severity=severity,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        conflict_type=conflict_type,  # type: ignore[arg-type]
        total_count=counts["total_count"],
        open_count=counts["open_count"],
        acknowledged_count=counts["acknowledged_count"],
        dismissed_count=counts["dismissed_count"],
        resolved_count=counts["resolved_count"],
    )


def list_relationship_conflicts_for_owner(
    session: Session,
    *,
    current_user: User,
    severity: str = "all",
    status: str = "all",
    conflict_type: str = "all",
) -> CoverRelationshipConflictListResponse:
    scope = _owner_scope_or_401(session, current_user)
    rows = [
        row
        for row in _existing_conflict_rows(session, scope=scope)
        if _owner_can_access_conflict(session, row=row, current_user=current_user, scope=scope)
    ]
    rows.sort(key=lambda row: (row.status, row.severity, row.conflict_type, row.conflict_key))
    return _list_conflicts_from_rows(rows, severity=severity, status=status, conflict_type=conflict_type)


def list_relationship_conflicts_for_ops(
    session: Session,
    *,
    severity: str = "all",
    status: str = "all",
    conflict_type: str = "all",
) -> CoverRelationshipConflictListResponse:
    rows = _existing_conflict_rows(session, scope=None)
    rows.sort(key=lambda row: (row.status, row.severity, row.conflict_type, row.conflict_key))
    return _list_conflicts_from_rows(rows, severity=severity, status=status, conflict_type=conflict_type)


def list_relationship_conflicts_for_cover_owner(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User,
    severity: str = "all",
    status: str = "all",
    conflict_type: str = "all",
) -> CoverRelationshipConflictListResponse:
    cover = get_cover_or_404(session, cover_image_id)
    if not owner_can_access_cover(session, cover=cover, current_user=current_user):
        raise HTTPException(status_code=404, detail="Cover image not found")
    scope = _owner_scope_or_401(session, current_user)
    rows = [
        row
        for row in _existing_conflict_rows(session, scope=scope)
        if cover_image_id in {row.source_cover_image_id, row.related_cover_image_id}
        and _owner_can_access_conflict(session, row=row, current_user=current_user, scope=scope)
    ]
    rows.sort(key=lambda row: (row.status, row.severity, row.conflict_type, row.conflict_key))
    return _list_conflicts_from_rows(rows, severity=severity, status=status, conflict_type=conflict_type)


def list_relationship_conflicts_for_cover_ops(
    session: Session,
    *,
    cover_image_id: int,
    severity: str = "all",
    status: str = "all",
    conflict_type: str = "all",
) -> CoverRelationshipConflictListResponse:
    get_cover_or_404(session, cover_image_id)
    rows = [
        row
        for row in _existing_conflict_rows(session, scope=None)
        if cover_image_id in {row.source_cover_image_id, row.related_cover_image_id}
    ]
    rows.sort(key=lambda row: (row.status, row.severity, row.conflict_type, row.conflict_key))
    return _list_conflicts_from_rows(rows, severity=severity, status=status, conflict_type=conflict_type)


def _set_conflict_status(
    session: Session,
    *,
    row: CoverRelationshipConflict,
    status_value: RelationshipConflictStatus,
    actor_user_id: int | None,
    reason: str | None,
) -> CoverRelationshipConflictActionResponse:
    before = _conflict_snapshot(row)
    if row.status == status_value:
        return CoverRelationshipConflictActionResponse(conflict=_serialize_conflict(row))
    now = utc_now()
    row.status = status_value
    row.updated_at = now
    if status_value == "acknowledged":
        row.acknowledged_at = now
    elif status_value == "dismissed":
        row.dismissed_at = now
    elif status_value == "resolved":
        row.resolved_at = now
    elif status_value == "open":
        row.resolved_at = None
    session.add(row)
    record_metadata_audit(
        session,
        entity_type="relationship_conflict",
        entity_id=row.id or -1,
        action=f"relationship_conflict_{status_value}",
        before_snapshot=before,
        after_snapshot=_conflict_snapshot(row),
        actor_user_id=actor_user_id,
        reason=reason,
    )
    session.commit()
    session.refresh(row)
    return CoverRelationshipConflictActionResponse(conflict=_serialize_conflict(row))


def acknowledge_relationship_conflict_for_owner(
    session: Session,
    *,
    conflict_id: int,
    current_user: User,
    reason: str | None,
) -> CoverRelationshipConflictActionResponse:
    row = get_relationship_conflict_or_404(session, conflict_id)
    scope = _owner_scope_or_401(session, current_user)
    if not _owner_can_access_conflict(session, row=row, current_user=current_user, scope=scope):
        raise HTTPException(status_code=404, detail="Relationship conflict not found")
    return _set_conflict_status(
        session,
        row=row,
        status_value="acknowledged",
        actor_user_id=current_user.id,
        reason=_normalize_reason(reason),
    )


def dismiss_relationship_conflict_for_owner(
    session: Session,
    *,
    conflict_id: int,
    current_user: User,
    reason: str | None,
) -> CoverRelationshipConflictActionResponse:
    row = get_relationship_conflict_or_404(session, conflict_id)
    scope = _owner_scope_or_401(session, current_user)
    if not _owner_can_access_conflict(session, row=row, current_user=current_user, scope=scope):
        raise HTTPException(status_code=404, detail="Relationship conflict not found")
    return _set_conflict_status(
        session,
        row=row,
        status_value="dismissed",
        actor_user_id=current_user.id,
        reason=_normalize_reason(reason),
    )


def resolve_relationship_conflict_for_owner(
    session: Session,
    *,
    conflict_id: int,
    current_user: User,
    reason: str | None,
) -> CoverRelationshipConflictActionResponse:
    row = get_relationship_conflict_or_404(session, conflict_id)
    scope = _owner_scope_or_401(session, current_user)
    if not _owner_can_access_conflict(session, row=row, current_user=current_user, scope=scope):
        raise HTTPException(status_code=404, detail="Relationship conflict not found")
    return _set_conflict_status(
        session,
        row=row,
        status_value="resolved",
        actor_user_id=current_user.id,
        reason=_normalize_reason(reason),
    )


def acknowledge_relationship_conflict_for_ops(
    session: Session,
    *,
    conflict_id: int,
    actor_user_id: int | None,
    reason: str | None,
) -> CoverRelationshipConflictActionResponse:
    row = get_relationship_conflict_or_404(session, conflict_id)
    return _set_conflict_status(
        session,
        row=row,
        status_value="acknowledged",
        actor_user_id=actor_user_id,
        reason=_normalize_reason(reason),
    )


def dismiss_relationship_conflict_for_ops(
    session: Session,
    *,
    conflict_id: int,
    actor_user_id: int | None,
    reason: str | None,
) -> CoverRelationshipConflictActionResponse:
    row = get_relationship_conflict_or_404(session, conflict_id)
    return _set_conflict_status(
        session,
        row=row,
        status_value="dismissed",
        actor_user_id=actor_user_id,
        reason=_normalize_reason(reason),
    )


def resolve_relationship_conflict_for_ops(
    session: Session,
    *,
    conflict_id: int,
    actor_user_id: int | None,
    reason: str | None,
) -> CoverRelationshipConflictActionResponse:
    row = get_relationship_conflict_or_404(session, conflict_id)
    return _set_conflict_status(
        session,
        row=row,
        status_value="resolved",
        actor_user_id=actor_user_id,
        reason=_normalize_reason(reason),
    )
