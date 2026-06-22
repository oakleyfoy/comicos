"""Deterministic duplicate ownership intelligence — read-only; never mutates inventory or catalog rows."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    CoverImage,
    CoverImageLinkDecision,
    DuplicateCandidateReview,
    InventoryCopy,
    User,
)
from app.schemas.duplicate_ownership import (
    DuplicateOwnershipClassification,
    DuplicateOwnershipCopyAttachment,
    DuplicateOwnershipGroupRead,
    DuplicateOwnershipListRead,
    DuplicateOwnershipSignals,
    DuplicateOwnershipSummary,
)
from app.schemas.duplicate_scan import (
    DuplicateScanClassificationFilter,
    DuplicateScanClustersListResponse,
    DuplicateScanClusterRead,
)
from app.services.duplicate_scan_intelligence import list_duplicate_scan_clusters_for_owner
from app.services.inventory_intelligence import normalize_ownership_state


def _component_group_key(inventory_ids: list[int]) -> str:
    stable_ids = sorted({int(x) for x in inventory_ids})
    payload = "|".join(str(i) for i in stable_ids).encode("utf-8")
    return f"own_dup:{hashlib.sha1(payload).hexdigest()[:26]}"


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def add(self, x: int) -> None:
        self._parent.setdefault(int(x), int(x))

    def find(self, x: int) -> int:
        x = int(x)
        root = self._parent.setdefault(x, x)
        while root != self._parent[root]:
            self._parent[root] = self._parent[self._parent[root]]
            root = self._parent[root]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if ra < rb:
            self._parent[rb] = ra
        else:
            self._parent[ra] = rb


def _inventory_projection_rows(session: Session, *, user_id: int) -> list:
    stmt = (
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.user_id.label("owner_user_id"),
            InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
            InventoryCopy.grade_status.label("grade_status"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.received_at.label("received_at"),
            InventoryCopy.primary_cover_image_id.label("primary_cover_image_id"),
        )
        .select_from(InventoryCopy)
        .where(InventoryCopy.user_id == user_id)
        .order_by(InventoryCopy.id.asc())
    )
    return list(session.exec(stmt).all())


def _covers_for_inventory(session: Session, inventory_ids: set[int]) -> dict[int, set[int]]:
    if not inventory_ids:
        return {}
    rows = session.exec(
        select(CoverImage.id, CoverImage.inventory_copy_id).where(
            CoverImage.inventory_copy_id.in_(sorted(inventory_ids)),
        ),
    ).all()
    out: defaultdict[int, set[int]] = defaultdict(set)
    for cid, inv in rows:
        if cid is None or inv is None:
            continue
        out[int(inv)].add(int(cid))
    return dict(out)


def _pending_duplicate_inventory_keys(session: Session) -> set[str]:
    keys = session.exec(
        select(DuplicateCandidateReview.metadata_identity_key).where(
            DuplicateCandidateReview.review_status == "pending",
        ),
    ).all()
    return {str(k) for k in keys if k}


def _canonical_issue_pending_edges(session: Session, inventory_ids: set[int]) -> list[tuple[int, int]]:
    if len(inventory_ids) < 2:
        return []
    rows = session.exec(
        select(CanonicalIssueLinkSuggestion.inventory_copy_id, CanonicalIssueLinkSuggestion.canonical_issue_id).where(
            CanonicalIssueLinkSuggestion.review_state == "pending",
            CanonicalIssueLinkSuggestion.inventory_copy_id.is_not(None),
            CanonicalIssueLinkSuggestion.canonical_issue_id.is_not(None),
            CanonicalIssueLinkSuggestion.inventory_copy_id.in_(sorted(inventory_ids)),
        ),
    ).all()
    bucket: defaultdict[int, list[int]] = defaultdict(list)
    for inv_id, issue_id in rows:
        bucket[int(issue_id)].append(int(inv_id))
    edges: list[tuple[int, int]] = []
    for members in bucket.values():
        uniq = sorted({mid for mid in members if mid in inventory_ids})
        if len(uniq) < 2:
            continue
        head = uniq[0]
        for other in uniq[1:]:
            edges.append((head, other))
    return edges


def _canonical_duplicate_scan_hints(session: Session, cover_ids: set[int]) -> bool:
    if not cover_ids:
        return False
    hits = session.exec(
        select(CanonicalIssueLinkSuggestion.id).where(
            CanonicalIssueLinkSuggestion.review_state == "pending",
            CanonicalIssueLinkSuggestion.suggestion_type == "duplicate_scan_context",
            CanonicalIssueLinkSuggestion.cover_image_id.in_(sorted(cover_ids)),
        ),
    ).first()
    return hits is not None


def _active_human_cover_pairs(session: Session) -> tuple[set[frozenset[int]], set[frozenset[int]]]:
    rows = session.exec(
        select(CoverImageLinkDecision).where(
            CoverImageLinkDecision.decision_state == "active",
            CoverImageLinkDecision.decision_type == "approved_link",
            CoverImageLinkDecision.relationship_type.in_(("same_cover", "duplicate_scan")),
        ),
    ).all()
    dup_pairs: set[frozenset[int]] = set()
    same_pairs: set[frozenset[int]] = set()
    for row in rows:
        pair = frozenset((int(row.source_cover_image_id), int(row.candidate_cover_image_id)))
        if row.relationship_type == "duplicate_scan":
            dup_pairs.add(pair)
        else:
            same_pairs.add(pair)
    return dup_pairs, same_pairs


def classify_duplicate_ownership(
    *,
    preorder_and_in_hand: bool,
    graded_and_raw: bool,
    pending_dup_review_touch: bool,
    duplicate_scan_exact: bool,
    human_dup_scan_pair: bool,
    human_same_cover: bool,
    touches_dup_cluster: bool,
    overlaps_probable_cluster_only: bool,
    raw_members: int,
    canonical_duplicate_scan_hint: bool,
) -> DuplicateOwnershipClassification:
    if pending_dup_review_touch:
        return "unresolved_duplicate"
    if preorder_and_in_hand:
        return "preorder_plus_owned"
    if graded_and_raw:
        return "graded_plus_raw"
    if duplicate_scan_exact or human_dup_scan_pair:
        return "duplicate_scan_only"

    probable_accidental = False
    if raw_members >= 3 and canonical_duplicate_scan_hint:
        probable_accidental = True
    elif raw_members >= 3 and human_same_cover:
        probable_accidental = True
    elif raw_members >= 3 and overlaps_probable_cluster_only:
        probable_accidental = True
    elif raw_members >= 3 and touches_dup_cluster:
        probable_accidental = True

    if probable_accidental:
        return "probable_accidental_duplicate"
    if touches_dup_cluster:
        return "duplicate_scan_only"
    return "intentional_multi_copy"


def _cluster_signals_for_covers(clusters: list[DuplicateScanClusterRead], cover_ids: frozenset[int]) -> tuple[bool, bool, bool]:
    touches = False
    exact_hit = False
    for cluster in clusters:
        cset = {int(cid) for cid in cluster.cover_image_ids}
        if not cover_ids & cset:
            continue
        touches = True
        if cluster.classification == "confirmed":
            exact_hit = True
        elif cluster.evidence_strength in ("human_confirmed", "sha256_exact_match"):
            exact_hit = True
    probable_touch = touches and not exact_hit
    return touches, exact_hit, probable_touch


def _component_cover_bundle(
    inv_ids_sorted: list[int],
    *,
    inv_to_cover: Mapping[int, set[int]],
    row_by_inv: Mapping[int, object],
) -> set[int]:
    covers: set[int] = set()
    for inv in inv_ids_sorted:
        covers |= inv_to_cover.get(inv, set())
        row = row_by_inv[inv]
        prim = getattr(row, "primary_cover_image_id", None)
        if prim is not None:
            covers.add(int(prim))

    return covers


def duplicate_ownership_inventory_groups_for_user(
    session: Session,
    *,
    owner_user_id: int,
    dup_cluster_payload: DuplicateScanClustersListResponse,
) -> list[DuplicateOwnershipGroupRead]:
    pending_keys = _pending_duplicate_inventory_keys(session)
    dup_pairs_global, same_pairs_global = _active_human_cover_pairs(session)

    rows = _inventory_projection_rows(session, user_id=owner_user_id)
    inv_ids = {int(r.inventory_copy_id) for r in rows}
    if len(inv_ids) < 2:
        return []

    row_by_inv = {int(r.inventory_copy_id): r for r in rows}
    uf = _UnionFind()
    for nid in sorted(inv_ids):
        uf.add(nid)

    identity_buckets: defaultdict[str | None, list[int]] = defaultdict(list)
    for r in rows:
        mk = getattr(r, "metadata_identity_key", None)
        norm = None if mk is None or str(mk).strip() == "" else str(mk)
        identity_buckets[norm].append(int(r.inventory_copy_id))

    for members in identity_buckets.values():
        uniq = sorted({m for m in members if m in inv_ids})
        if len(uniq) <= 1:
            continue
        anchor = uniq[0]
        for other in uniq[1:]:
            uf.union(anchor, other)

    inv_to_cover = _covers_for_inventory(session, inv_ids)
    cover_lookup_rows = session.exec(
        select(CoverImage.id, CoverImage.inventory_copy_id).where(
            CoverImage.inventory_copy_id.in_(sorted(inv_ids)),
        ),
    ).all()
    cid_to_inventory: dict[int, int] = {}
    for cid, inv in cover_lookup_rows:
        if cid is None or inv is None:
            continue
        cid_to_inventory[int(cid)] = int(inv)

    for cluster in dup_cluster_payload.clusters:
        cluster_inv_ids: set[int] = set()
        for cid in cluster.cover_image_ids:
            mapped = cid_to_inventory.get(int(cid))
            if mapped is not None and mapped in inv_ids:
                cluster_inv_ids.add(mapped)

        uniq = sorted(cluster_inv_ids)
        if len(uniq) <= 1:
            continue

        anchor = uniq[0]
        for peer in uniq[1:]:
            uf.union(anchor, peer)

    for edge in _canonical_issue_pending_edges(session, inv_ids):
        uf.union(edge[0], edge[1])

    cover_ids_owner: set[int] = set(cid_to_inventory.keys())
    dup_pairs_touching = {pair for pair in dup_pairs_global if all(int(c) in cover_ids_owner for c in pair)}
    same_pairs_touching = {
        pair for pair in same_pairs_global if all(int(c) in cover_ids_owner for c in pair)
    }

    for pair in dup_pairs_touching:
        lids = sorted(pair)
        inv_a = cid_to_inventory.get(lids[0])
        inv_b = cid_to_inventory.get(lids[1])
        if inv_a is not None and inv_b is not None:
            uf.union(inv_a, inv_b)

    for pair in same_pairs_touching:
        lids = sorted(pair)
        inv_a = cid_to_inventory.get(lids[0])
        inv_b = cid_to_inventory.get(lids[1])
        if inv_a is not None and inv_b is not None:
            uf.union(inv_a, inv_b)

    components: dict[int, list[int]] = defaultdict(list)
    for nid in sorted(inv_ids):
        components[uf.find(nid)].append(nid)

    clusters_list = dup_cluster_payload.clusters

    grouped_reads: list[DuplicateOwnershipGroupRead] = []

    for _root, payload in sorted(components.items(), key=lambda item: tuple(sorted(item[1]))):
        uniq_ids = sorted({int(x) for x in payload})
        if len(uniq_ids) < 2:
            continue

        cover_bundle_set = _component_cover_bundle(
            uniq_ids,
            inv_to_cover=inv_to_cover,
            row_by_inv=row_by_inv,
        )
        cover_bundle = frozenset(cover_bundle_set)
        touches, exact_hit, probable_only = _cluster_signals_for_covers(clusters_list, cover_bundle)

        keys_observed: list[str | None] = []

        has_preorder_own = False
        in_hand_states = False
        pending_dup_touch = False

        raw_members = 0
        graded_members = 0

        for nid in uniq_ids:
            rr = row_by_inv[nid]

            mk = getattr(rr, "metadata_identity_key", None)
            norm_key = None if mk is None or str(mk).strip() == "" else str(mk)
            keys_observed.append(norm_key)

            own = normalize_ownership_state(
                release_status=str(rr.release_status),
                order_status=str(rr.order_status),
                received_at=rr.received_at,
            )
            has_preorder_own |= own == "preorder"
            in_hand_states |= own == "in_hand"

            if str(rr.grade_status) == "raw":
                raw_members += 1
            else:
                graded_members += 1

            nk_row = getattr(rr, "metadata_identity_key", None)
            nk_clean = None if nk_row is None or str(nk_row).strip() == "" else str(nk_row)
            if nk_clean and nk_clean in pending_keys:
                pending_dup_touch = True

        preorder_and_in_hand = has_preorder_own and in_hand_states

        graded_mix = graded_members >= 1 and raw_members >= 1

        non_null_keys = [k for k in keys_observed if k is not None]
        unique_non_null = sorted(set(non_null_keys))
        shares_identity = (
            len(unique_non_null) == 1 and len(non_null_keys) >= 2 and all(k == unique_non_null[0] for k in non_null_keys)
        )

        canonical_hint = _canonical_duplicate_scan_hints(session, cover_bundle_set)

        covers_plain = cover_bundle_set
        human_dup_scan = any(pair <= covers_plain for pair in dup_pairs_touching)
        human_same_cover = any(pair <= covers_plain for pair in same_pairs_touching)

        classification = classify_duplicate_ownership(
            preorder_and_in_hand=preorder_and_in_hand,
            graded_and_raw=graded_mix,
            pending_dup_review_touch=pending_dup_touch,
            duplicate_scan_exact=exact_hit,
            human_dup_scan_pair=human_dup_scan,
            human_same_cover=human_same_cover,

            touches_dup_cluster=touches,
            overlaps_probable_cluster_only=probable_only,

            raw_members=raw_members,
            canonical_duplicate_scan_hint=canonical_hint,
        )

        non_null_sorted = sorted({str(k) for k in keys_observed if k is not None})
        metadata_identity_keys_ordered: list[str | None] = list(non_null_sorted)
        if any(k is None for k in keys_observed):
            metadata_identity_keys_ordered.append(None)

        grouped_reads.append(
            DuplicateOwnershipGroupRead(
                group_key=_component_group_key(uniq_ids),
                owner_user_id=int(owner_user_id),
                classification=classification,
                inventory_copy_ids=uniq_ids,

                signal_flags=DuplicateOwnershipSignals(
                    shares_metadata_identity_key=shares_identity,
                    metadata_identity_keys=metadata_identity_keys_ordered,
                    preorder_and_in_hand_both_present=preorder_and_in_hand,

                    graded_and_raw_both_present=graded_mix,
                    pending_duplicate_inventory_review=pending_dup_touch,
                    touches_duplicate_scan_cluster=touches,
                    duplicate_scan_evidence_exact=exact_hit,
                    overlaps_probable_duplicate_scan_cluster=probable_only,
                    human_duplicate_scan_approved_pair=human_dup_scan,
                    human_same_cover_approved_pair=human_same_cover,
                    canonical_pending_duplicate_scan_context=canonical_hint,
                ),
            )
        )

    grouped_reads.sort(key=lambda g: (g.classification, g.group_key, tuple(g.inventory_copy_ids)))
    return grouped_reads


def duplicate_owner_summary(groups: list[DuplicateOwnershipGroupRead]) -> DuplicateOwnershipSummary:
    summary = DuplicateOwnershipSummary()
    summary.total_groups = len(groups)
    for group in groups:
        cls = group.classification
        if cls == "intentional_multi_copy":
            summary.intentional_multi_copy_groups += 1
        elif cls == "probable_accidental_duplicate":
            summary.probable_accidental_duplicate_groups += 1
        elif cls == "duplicate_scan_only":
            summary.duplicate_scan_only_groups += 1
        elif cls == "preorder_plus_owned":
            summary.preorder_plus_owned_groups += 1
        elif cls == "graded_plus_raw":
            summary.graded_plus_raw_groups += 1
        elif cls == "unresolved_duplicate":
            summary.unresolved_duplicate_groups += 1
    return summary


def duplicate_ownership_inventory_attach_map(
    groups: list[DuplicateOwnershipGroupRead],
) -> dict[int, DuplicateOwnershipCopyAttachment]:
    out: dict[int, DuplicateOwnershipCopyAttachment] = {}
    for group in groups:
        for inv_id in group.inventory_copy_ids:
            peers = [i for i in group.inventory_copy_ids if i != inv_id]
            out[int(inv_id)] = DuplicateOwnershipCopyAttachment(
                group_key=group.group_key,
                classification=group.classification,
                sibling_inventory_copy_ids=sorted(peers),
            )
    return out


def _owner_cluster_payload(
    session: Session,
    user: User,
    dup_scan_classification: DuplicateScanClassificationFilter,
) -> DuplicateScanClustersListResponse:
    return list_duplicate_scan_clusters_for_owner(
        session,
        current_user=user,

        classification_filter=dup_scan_classification,
    )


def duplicate_ownership_inventory_context_for_owner(
    session: Session,

    *,
    user: User,
    dup_scan_classification: DuplicateScanClassificationFilter = "all",
) -> tuple[list[DuplicateOwnershipGroupRead], dict[int, DuplicateOwnershipCopyAttachment]]:
    assert user.id is not None

    dup_payload = _owner_cluster_payload(session, user, dup_scan_classification)


    groups = duplicate_ownership_inventory_groups_for_user(
        session,

        owner_user_id=int(user.id),
        dup_cluster_payload=dup_payload,
    )


    attachments = duplicate_ownership_inventory_attach_map(groups)
    return groups, attachments


def list_duplicate_ownership_owner(
    session: Session,
    *,
    user: User,

    dup_scan_classification: DuplicateScanClassificationFilter,
    classification: DuplicateOwnershipClassification | None,
) -> DuplicateOwnershipListRead:
    groups, _ = duplicate_ownership_inventory_context_for_owner(
        session,
        user=user,
        dup_scan_classification=dup_scan_classification,
    )


    if classification is not None:
        groups = [g for g in groups if g.classification == classification]

    summary = duplicate_owner_summary(groups)
    return DuplicateOwnershipListRead(summary=summary, groups=groups)


def list_duplicate_ownership_ops(
    session: Session,
    *,
    dup_scan_classification: DuplicateScanClassificationFilter,
    classification: DuplicateOwnershipClassification | None,

) -> DuplicateOwnershipListRead:
    ids = session.exec(select(InventoryCopy.user_id)).all()
    aggregated: list[DuplicateOwnershipGroupRead] = []

    user_ids_sorted = sorted({int(uid) for uid in ids if uid is not None})

    for uid in user_ids_sorted:
        phantom = User(id=uid)


        dup_payload = list_duplicate_scan_clusters_for_owner(session, current_user=phantom, classification_filter=dup_scan_classification)

        groups_user = duplicate_ownership_inventory_groups_for_user(
            session,
            owner_user_id=uid,

            dup_cluster_payload=dup_payload,
        )


        aggregated.extend(groups_user)


    aggregated.sort(key=lambda g: (int(g.owner_user_id or -1), g.group_key))


    if classification is not None:
        aggregated = [g for g in aggregated if g.classification == classification]

    summary = duplicate_owner_summary(aggregated)
    return DuplicateOwnershipListRead(summary=summary, groups=aggregated)


def get_duplicate_ownership_detail_owner(session: Session, *, user: User, group_key: str) -> DuplicateOwnershipGroupRead:
    groups, _ = duplicate_ownership_inventory_context_for_owner(session, user=user, dup_scan_classification="all")
    match = next((g for g in groups if g.group_key == group_key), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Duplicate ownership group not found")

    inv_set = set(match.inventory_copy_ids)
    user_ids = session.exec(
        select(InventoryCopy.user_id).where(InventoryCopy.id.in_(sorted(inv_set))),
    ).all()
    assert user.id is not None
    if len(user_ids) != len(inv_set) or any(int(uid) != int(user.id) for uid in user_ids):
        raise HTTPException(status_code=404, detail="Duplicate ownership group not found")
    return match


def get_duplicate_ownership_detail_ops(session: Session, *, group_key: str) -> DuplicateOwnershipGroupRead:


    rollup = list_duplicate_ownership_ops(session, dup_scan_classification="all", classification=None)
    detail = next((g for g in rollup.groups if g.group_key == group_key), None)
    if detail is None:


        raise HTTPException(status_code=404, detail="Duplicate ownership group not found")
    return detail
