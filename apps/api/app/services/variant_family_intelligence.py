"""Deterministic variant-family visibility — read-only; no linking, merges, or metadata mutation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    CoverImage,
    CoverImageDerivative,
    CoverImageFingerprint,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    InventoryCopy,
    User,
)
from app.schemas.variant_family import (
    VariantFamilyCandidatesResponse,
    VariantFamilyClassificationFilter,
    VariantFamilyClusterRead,
    VariantFamilyClustersListResponse,
    VariantFamilyEvidenceFlags,
    VariantFamilyEvidenceStrength,
    VariantFamilyPeerRead,
    VariantFamilySuppressedPairRead,
)
from app.services.cover_images import (
    _build_fingerprint_signals,
    _fingerprints_for_cover,
    _fingerprint_similarity_metrics,
    _grouping_fp_divergent,
    _grouping_fp_near_identical,
    get_cover_entity_for_processing_by_ops_or_404,
    get_cover_entity_for_processing_by_owner,
)
from app.services.cover_link_decisions import active_cover_link_decisions_for_pairs, cover_link_pair_key
from app.services.duplicate_scan_intelligence import canonical_edge_tuple, owner_cover_scope


def stable_variant_cluster_key(sorted_cover_ids: list[int]) -> str:
    payload = "|".join(str(cid) for cid in sorted_cover_ids).encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()
    return f"vf_cluster:{digest[:24]}"


@dataclass
class VFPairAgg:
    human_vf: bool = False
    human_variant_family_decision_id: int | None = None

    probable_variant_family_group: bool = False
    same_issue_divergent_fingerprint: bool = False
    metadata_identity_divergent: bool = False

    ocr_title_issue_exact_pairwise: bool = False
    publisher_exact_pairwise: bool = False
    fingerprint_divergent_signal: bool = False

    match_candidate_ids: list[int] = field(default_factory=list)
    grouping_keys_sorted: list[str] = field(default_factory=list)
    shared_upcs: set[str] = field(default_factory=set)
    fingerprint_metrics: dict[str, float] | None = None

    def merge_inplace(self, other: VFPairAgg) -> None:
        self.human_vf = self.human_vf or other.human_vf
        if other.human_variant_family_decision_id is not None:
            if self.human_variant_family_decision_id is None:
                self.human_variant_family_decision_id = other.human_variant_family_decision_id
            else:
                self.human_variant_family_decision_id = min(
                    self.human_variant_family_decision_id,
                    other.human_variant_family_decision_id,
                )

        self.probable_variant_family_group = (
            self.probable_variant_family_group or other.probable_variant_family_group
        )
        self.same_issue_divergent_fingerprint = (
            self.same_issue_divergent_fingerprint or other.same_issue_divergent_fingerprint
        )
        self.metadata_identity_divergent = self.metadata_identity_divergent or other.metadata_identity_divergent

        self.ocr_title_issue_exact_pairwise = (
            self.ocr_title_issue_exact_pairwise or other.ocr_title_issue_exact_pairwise
        )
        self.publisher_exact_pairwise = self.publisher_exact_pairwise or other.publisher_exact_pairwise
        self.fingerprint_divergent_signal = (
            self.fingerprint_divergent_signal or other.fingerprint_divergent_signal
        )

        for mid in other.match_candidate_ids:
            if mid not in self.match_candidate_ids:
                self.match_candidate_ids.append(mid)
        self.match_candidate_ids.sort()
        self.grouping_keys_sorted = sorted(set([*self.grouping_keys_sorted, *other.grouping_keys_sorted]))
        self.shared_upcs |= other.shared_upcs
        if other.fingerprint_metrics is not None:
            self.fingerprint_metrics = dict(other.fingerprint_metrics)


def _merge_vf_chunks(*chunks: dict[tuple[int, int], VFPairAgg]) -> dict[tuple[int, int], VFPairAgg]:
    merged: defaultdict[tuple[int, int], VFPairAgg] = defaultdict(VFPairAgg)
    keys = sorted({k for blob in chunks for k in blob})
    for tup in keys:
        for blob in chunks:
            if tup in blob:
                merged[tup].merge_inplace(blob[tup])
    return dict(merged)


def _collect_shared_upcs(piece: VFPairAgg, matched_signals: dict[str, object]) -> None:
    barcode_matches = matched_signals.get("barcode_matches")
    if not isinstance(barcode_matches, list):
        return
    for candidate in barcode_matches:
        if isinstance(candidate, str) and candidate.strip():
            piece.shared_upcs.add(candidate.strip())


def _vf_snippet_from_match_candidate(row: CoverImageMatchCandidate) -> VFPairAgg | None:
    if row.dismissed_at is not None:
        return None
    hard = dict(row.hard_match_flags_json or {})
    signals = dict(row.matched_signals or {})
    metrics = _fingerprint_similarity_metrics(signals)
    biblio = bool(hard.get("ocr_title_exact_match")) and bool(hard.get("ocr_issue_number_exact_match"))
    publisher_exact = bool(hard.get("ocr_publisher_exact_match"))
    if not biblio:
        return None
    near_identical_fp = _grouping_fp_near_identical(metrics)
    divergent_fp = _grouping_fp_divergent(metrics)

    grouping = row.grouping_type or ""
    snippet = VFPairAgg(
        fingerprint_metrics=dict(metrics),
        ocr_title_issue_exact_pairwise=True,
        publisher_exact_pairwise=publisher_exact,
        fingerprint_divergent_signal=divergent_fp,
    )

    if grouping == "probable_variant_family":
        if near_identical_fp:
            return None
        snippet.probable_variant_family_group = True
        snippet.fingerprint_divergent_signal = divergent_fp or True
        if row.grouping_key:
            snippet.grouping_keys_sorted = sorted({*snippet.grouping_keys_sorted, row.grouping_key})
    elif grouping == "probable_same_issue" and divergent_fp:
        if near_identical_fp:
            return None
        snippet.same_issue_divergent_fingerprint = True
        snippet.fingerprint_divergent_signal = True
        if row.grouping_key:
            snippet.grouping_keys_sorted = sorted({*snippet.grouping_keys_sorted, row.grouping_key})
    else:
        return None

    _collect_shared_upcs(snippet, signals)

    if row.id is not None:
        snippet.match_candidate_ids = sorted({*snippet.match_candidate_ids, int(row.id)})
    return snippet


def duplicate_scan_human_pair_set(session: Session, *, scope: frozenset[int] | None) -> frozenset[tuple[int, int]]:
    stmt = select(CoverImageLinkDecision.source_cover_image_id, CoverImageLinkDecision.candidate_cover_image_id).where(
        CoverImageLinkDecision.decision_state == "active",
        CoverImageLinkDecision.decision_type == "approved_link",
        CoverImageLinkDecision.relationship_type == "duplicate_scan",
    )
    settled: list[tuple[int, int]] = []
    for left_id, right_id in session.exec(stmt).all():
        left_i, right_i = int(left_id), int(right_id)
        if scope is not None and (left_i not in scope or right_i not in scope):
            continue
        settled.append(canonical_edge_tuple(left_i, right_i))
    return frozenset(settled)


def _match_candidate_variant_edges(session: Session, *, scope: frozenset[int] | None) -> dict[tuple[int, int], VFPairAgg]:
    merged: defaultdict[tuple[int, int], VFPairAgg] = defaultdict(VFPairAgg)
    stmt = select(CoverImageMatchCandidate).where(CoverImageMatchCandidate.dismissed_at.is_(None))  # type: ignore[union-attr]
    for row in session.exec(stmt).all():
        src = int(row.source_cover_image_id)
        cand = int(row.candidate_cover_image_id)
        if scope is not None and (src not in scope or cand not in scope):
            continue
        snippet = _vf_snippet_from_match_candidate(row)
        if snippet is None:
            continue
        tup = canonical_edge_tuple(src, cand)
        merged[tup].merge_inplace(snippet)
    return dict(merged)


def _metadata_identity_variant_edges(session: Session, *, scope: frozenset[int] | None) -> dict[tuple[int, int], VFPairAgg]:
    stmt = (
        select(CoverImage.id, InventoryCopy.metadata_identity_key)
        .join(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .where(CoverImage.inventory_copy_id.is_not(None))
    )
    if scope is not None:
        stmt = stmt.where(CoverImage.id.in_(sorted(scope)))

    buckets: defaultdict[str, list[int]] = defaultdict(list)
    for cid, mi_key in session.exec(stmt).all():
        if mi_key is None:
            continue
        key_trim = str(mi_key).strip()
        if not key_trim:
            continue
        buckets[key_trim].append(int(cid))

    merged: defaultdict[tuple[int, int], VFPairAgg] = defaultdict(VFPairAgg)
    identity_keys_sorted = sorted(buckets.keys())
    for ik in identity_keys_sorted:
        cover_ids_sorted = sorted(set(buckets[ik]))
        if len(cover_ids_sorted) < 2:
            continue
        fp_rows = session.exec(
            select(CoverImageFingerprint)
            .where(CoverImageFingerprint.cover_image_id.in_(cover_ids_sorted))
            .order_by(CoverImageFingerprint.cover_image_id.asc(), CoverImageFingerprint.id.asc())
        ).all()
        fps_by_cover = _fingerprints_for_cover(list(fp_rows))
        pairs = [(cover_ids_sorted[i], cover_ids_sorted[j]) for i in range(len(cover_ids_sorted)) for j in range(i + 1, len(cover_ids_sorted))]
        for src, cand in pairs:
            left_fp = fps_by_cover.get(int(src), {})
            right_fp = fps_by_cover.get(int(cand), {})
            if not left_fp or not right_fp:
                continue
            sig_bundle = _build_fingerprint_signals(left_fp, right_fp)
            matched = dict(sig_bundle.get("matched_signals") or {})
            metrics = _fingerprint_similarity_metrics(matched)
            if _grouping_fp_near_identical(metrics):
                continue
            if not _grouping_fp_divergent(metrics):
                continue
            tup = canonical_edge_tuple(int(src), int(cand))
            snippet = VFPairAgg(
                metadata_identity_divergent=True,
                ocr_title_issue_exact_pairwise=True,
                fingerprint_divergent_signal=True,
                fingerprint_metrics=dict(metrics),
            )
            snippet.grouping_keys_sorted = sorted(set([*snippet.grouping_keys_sorted, f"identity:{ik}"]))
            merged[tup].merge_inplace(snippet)
    return dict(merged)


def _human_variant_family_edges(session: Session, *, scope: frozenset[int] | None) -> dict[tuple[int, int], VFPairAgg]:
    merged: defaultdict[tuple[int, int], VFPairAgg] = defaultdict(VFPairAgg)
    stmt = select(CoverImageLinkDecision).where(
        CoverImageLinkDecision.decision_state == "active",
        CoverImageLinkDecision.decision_type == "approved_link",
        CoverImageLinkDecision.relationship_type == "variant_family",
    )
    for row in session.exec(stmt).all():
        src = int(row.source_cover_image_id)
        cand = int(row.candidate_cover_image_id)
        if scope is not None and (src not in scope or cand not in scope):
            continue
        tup = canonical_edge_tuple(src, cand)
        merged[tup].merge_inplace(
            VFPairAgg(
                human_vf=True,
                human_variant_family_decision_id=int(row.id) if row.id is not None else None,
                ocr_title_issue_exact_pairwise=True,
                publisher_exact_pairwise=False,
                fingerprint_divergent_signal=False,
            )
        )
    return dict(merged)


def _pair_actively_unrelated(pair_key_str: str, active_by_pair: dict[str, CoverImageLinkDecision]) -> bool:
    snap = active_by_pair.get(pair_key_str)
    if snap is None:
        return False
    return snap.decision_type == "rejected_link" and snap.relationship_type == "unrelated"


def _evidence_labels_for_vf_tech_only(tech_only: VFPairAgg) -> list[str]:
    snaps: list[str] = []
    if tech_only.probable_variant_family_group:
        snaps.append("probable_variant_family_group")
    if tech_only.same_issue_divergent_fingerprint:
        snaps.append("same_issue_divergent_fingerprint")
    if tech_only.metadata_identity_divergent:
        snaps.append("metadata_identity_divergent")
    supporting = sorted(tech_only.shared_upcs)
    if supporting:
        snaps.append("supporting_shared_upcs")
    return sorted(set(snaps))


def flags_from_vf_agg(agg: VFPairAgg) -> VariantFamilyEvidenceFlags:
    return VariantFamilyEvidenceFlags(
        human_variant_family=agg.human_vf,
        probable_variant_family_group=agg.probable_variant_family_group,
        same_issue_divergent_fingerprint=agg.same_issue_divergent_fingerprint,
        metadata_identity_normalized=agg.metadata_identity_divergent,
        ocr_title_issue_exact_pairwise=agg.ocr_title_issue_exact_pairwise,
        publisher_exact_pairwise=agg.publisher_exact_pairwise,
        fingerprint_divergent_signal=agg.fingerprint_divergent_signal,
        supporting_shared_upcs=sorted(agg.shared_upcs),
    )


def _suppress_technical_vf_edges(
    *,
    technical_edges: dict[tuple[int, int], VFPairAgg],
    active_by_pair: dict[str, CoverImageLinkDecision],
) -> tuple[dict[tuple[int, int], VFPairAgg], list[VariantFamilySuppressedPairRead]]:
    suppressed: list[VariantFamilySuppressedPairRead] = []
    surviving: defaultdict[tuple[int, int], VFPairAgg] = defaultdict(VFPairAgg)
    for pair in sorted(technical_edges.keys()):
        agg = technical_edges[pair]
        pk_str = cover_link_pair_key(pair[0], pair[1])
        if _pair_actively_unrelated(pk_str, active_by_pair):
            suppressed.append(
                VariantFamilySuppressedPairRead(
                    pair_key=pk_str,
                    left_cover_image_id=pair[0],
                    right_cover_image_id=pair[1],
                    suppressed_signal_labels=_evidence_labels_for_vf_tech_only(agg),
                    evidence_snapshot=flags_from_vf_agg(agg),
                )
            )
            continue
        surviving[pair].merge_inplace(agg)
    return dict(surviving), suppressed


def _active_decisions_index(
    session: Session,
    pairs: list[tuple[int, int]],
) -> dict[str, CoverImageLinkDecision]:
    if not pairs:
        return {}
    return active_cover_link_decisions_for_pairs(session, pairs=sorted(set(pairs), key=lambda t: (t[0], t[1])))


class _VFDSU:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def _touch(self, x: int) -> int:
        self.parent.setdefault(x, x)
        nodes: list[int] = []
        curr = x
        while curr != self.parent[curr]:
            nodes.append(curr)
            curr = self.parent[curr]
        root = curr
        for node in nodes:
            self.parent[node] = root
        return root

    def unite(self, a: int, b: int) -> None:
        ra, rb = self._touch(a), self._touch(b)
        if ra == rb:
            return
        low, high = (ra, rb) if ra < rb else (rb, ra)
        self.parent[high] = low


def _vf_rank(agg: VFPairAgg) -> int:
    if agg.human_vf:
        return 0
    if agg.probable_variant_family_group:
        return 1
    if agg.same_issue_divergent_fingerprint:
        return 2
    if agg.metadata_identity_divergent:
        return 3
    return 4


def _strength_literal_from_rank(rank: int) -> VariantFamilyEvidenceStrength:
    if rank == 0:
        return "human_confirmed_variant_family"
    if rank == 1:
        return "probable_variant_family_group"
    if rank == 2:
        return "same_issue_divergent_fingerprint"
    if rank == 3:
        return "metadata_identity_divergent_fingerprint"
    return "mixed"


def cluster_vf_evidence_strength(ranks: list[int]) -> VariantFamilyEvidenceStrength:
    uniq_rank = sorted(set(ranks))
    if 0 in uniq_rank:
        return "human_confirmed_variant_family"
    tiers = [r for r in uniq_rank if r < 5]
    if not tiers:
        return "mixed"
    lowest = tiers[0]
    if lowest == uniq_rank[-1]:
        return _strength_literal_from_rank(lowest)
    if lowest in {1, 2, 3} and max(tiers) > lowest:
        return "mixed"
    return _strength_literal_from_rank(lowest)


def _collect_vf_nodes(edges: dict[tuple[int, int], VFPairAgg]) -> set[int]:
    members: set[int] = set()
    for left_id, right_id in edges:
        members.add(left_id)
        members.add(right_id)
    return members


def vf_clusters_from_edges(edges: dict[tuple[int, int], VFPairAgg]) -> list[list[int]]:
    members = _collect_vf_nodes(edges)
    if not members:
        return []
    forest = _VFDSU()
    for left_id, right_id in edges:
        forest.unite(left_id, right_id)
    roots: defaultdict[int, list[int]] = defaultdict(list)
    for cover_id_member in sorted(members):
        anchor = forest._touch(cover_id_member)
        roots[anchor].append(cover_id_member)
    clustered = [sorted(v) for v in roots.values() if len(v) >= 2]
    clustered.sort(key=lambda group: tuple(group))
    return clustered


def _build_vf_cluster_read(
    cover_ids_sorted: list[int],
    merged_edges: dict[tuple[int, int], VFPairAgg],
) -> VariantFamilyClusterRead:
    cid_set = set(cover_ids_sorted)
    tiers: list[int] = []
    anybody_human = False
    for (left_id, right_id), snippet in sorted(merged_edges.items(), key=lambda kv: kv[0]):
        if left_id not in cid_set or right_id not in cid_set:
            continue
        tiers.append(_vf_rank(snippet))
        anybody_human = anybody_human or snippet.human_vf
    tier_strength = cluster_vf_evidence_strength(tiers)
    clustering_label = stable_variant_cluster_key(cover_ids_sorted)
    return VariantFamilyClusterRead(
        cluster_key=clustering_label,
        cover_image_ids=list(cover_ids_sorted),
        cluster_size=len(cover_ids_sorted),
        classification="confirmed" if anybody_human else "probable",
        evidence_strength=tier_strength,
    )


def _derivative_counts(session: Session, cover_ids: set[int]) -> dict[int, int]:
    if not cover_ids:
        return {}
    stmt = (
        select(CoverImageDerivative.cover_image_id, func.count())
        .where(CoverImageDerivative.cover_image_id.in_(sorted(cover_ids)))
        .group_by(CoverImageDerivative.cover_image_id)
    )
    rows = session.exec(stmt).all()
    return {int(cover_id_i): int(qty) for cover_id_i, qty in rows}


def _cover_dimension_map(session: Session, cover_ids: set[int]) -> dict[int, dict[str, int | None]]:
    if not cover_ids:
        return {}
    exec_rows = session.exec(
        select(CoverImage.id, CoverImage.image_width, CoverImage.image_height).where(CoverImage.id.in_(sorted(cover_ids)))
    ).all()
    return {int(rid): {"width": w, "height": h} for rid, w, h in exec_rows}


def _peer_vf_detail(
    *,
    agg: VFPairAgg,
    dims: dict[int, dict[str, int | None]],
    derivatives: dict[int, int],
    focal_id: int,
    peer_id: int,
) -> dict[str, object]:
    out: dict[str, object] = {
        "focal_dimensions": dims.get(int(focal_id), {"width": None, "height": None}),
        "peer_dimensions": dims.get(int(peer_id), {"width": None, "height": None}),
        "focal_derivative_count": derivatives.get(int(focal_id), 0),
        "peer_derivative_count": derivatives.get(int(peer_id), 0),
        "grouping_keys": list(agg.grouping_keys_sorted),
        "deterministic_signals": {
            "human_variant_family": agg.human_vf,
            "probable_variant_family_group": agg.probable_variant_family_group,
            "same_issue_divergent": agg.same_issue_divergent_fingerprint,
            "metadata_identity": agg.metadata_identity_divergent,
            "publisher_pairwise_exact": agg.publisher_exact_pairwise,
            "ocr_title_issue_pairwise_exact": agg.ocr_title_issue_exact_pairwise,
        },
    }
    if agg.fingerprint_metrics is not None:
        refined = {k: round(v, 6) for k, v in sorted(agg.fingerprint_metrics.items())}
        out["fingerprint_similarity_metrics"] = refined
    return out


def _neighbor_variant_reads_for_focal(
    session: Session,
    *,
    focal_i: int,
    reachable_clusters: list[VariantFamilyClusterRead],
    merged_edges_bundle: dict[tuple[int, int], VFPairAgg],
) -> list[VariantFamilyPeerRead]:
    reachable_clusters.sort(key=lambda c: tuple(c.cover_image_ids))
    aggregated_reads: dict[int, VariantFamilyPeerRead] = {}
    for cluster_snapshot in reachable_clusters:
        peers_chain_all = sorted(p for p in cluster_snapshot.cover_image_ids if int(p) != focal_i)
        for neighbor_pid in peers_chain_all:
            pairing_bundle = canonical_edge_tuple(focal_i, int(neighbor_pid))
            enrichment_ids_here = {focal_i, int(neighbor_pid)}
            dims_bundle = _cover_dimension_map(session, enrichment_ids_here)
            derivatives_bundle_hint = _derivative_counts(session, enrichment_ids_here)
            snippet_direct = merged_edges_bundle.get(pairing_bundle)
            if snippet_direct is not None:
                flagged_candidate = VariantFamilyPeerRead(
                    peer_cover_image_id=int(neighbor_pid),
                    pair_key=cover_link_pair_key(focal_i, int(neighbor_pid)),
                    canonical_pair_low_id=int(pairing_bundle[0]),
                    canonical_pair_high_id=int(pairing_bundle[1]),
                    classification=("confirmed" if snippet_direct.human_vf else "probable"),
                    evidences=flags_from_vf_agg(snippet_direct),
                    evidence_detail=_peer_vf_detail(
                        agg=snippet_direct,
                        dims=dims_bundle,
                        derivatives=derivatives_bundle_hint,
                        focal_id=focal_i,
                        peer_id=int(neighbor_pid),
                    ),
                    match_candidate_ids=list(snippet_direct.match_candidate_ids),
                    human_variant_family_decision_id=snippet_direct.human_variant_family_decision_id,
                )
            else:
                bridging_detail: dict[str, object] = {
                    "cluster_transitive_variant_family": True,
                    "touching_cluster_key": cluster_snapshot.cluster_key,
                    "touching_cluster_evidence_strength": cluster_snapshot.evidence_strength,
                    "touching_cluster_classification": cluster_snapshot.classification,
                }
                bridging_detail.update(
                    _peer_vf_detail(
                        agg=VFPairAgg(),
                        dims=dims_bundle,
                        derivatives=derivatives_bundle_hint,
                        focal_id=focal_i,
                        peer_id=int(neighbor_pid),
                    )
                )
                flagged_candidate = VariantFamilyPeerRead(
                    peer_cover_image_id=int(neighbor_pid),
                    pair_key=cover_link_pair_key(focal_i, int(neighbor_pid)),
                    canonical_pair_low_id=int(pairing_bundle[0]),
                    canonical_pair_high_id=int(pairing_bundle[1]),
                    classification="probable",
                    evidences=VariantFamilyEvidenceFlags(),
                    evidence_detail=bridging_detail,
                    match_candidate_ids=[],
                    human_variant_family_decision_id=None,
                )
            incumbent = aggregated_reads.get(int(neighbor_pid))
            if incumbent is None or (
                incumbent.classification != "confirmed" and flagged_candidate.classification == "confirmed"
            ):
                aggregated_reads[int(neighbor_pid)] = flagged_candidate
    return [aggregated_reads[k] for k in sorted(aggregated_reads)]


def _variant_family_graph(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> tuple[
    dict[tuple[int, int], VFPairAgg],
    dict[tuple[int, int], VFPairAgg],
    dict[tuple[int, int], VFPairAgg],
    list[VariantFamilySuppressedPairRead],
    frozenset[tuple[int, int]],
]:
    dup_block = duplicate_scan_human_pair_set(session, scope=scope)

    technical_pre_merge = _merge_vf_chunks(
        _match_candidate_variant_edges(session, scope=scope),
        _metadata_identity_variant_edges(session, scope=scope),
    )
    humans = _human_variant_family_edges(session, scope=scope)

    technical_no_duplicate: defaultdict[tuple[int, int], VFPairAgg] = defaultdict(VFPairAgg)
    for pair_k, snippet in sorted(technical_pre_merge.items()):
        if pair_k in dup_block:
            continue
        technical_no_duplicate[pair_k].merge_inplace(snippet)
    technical_no_dup_final = dict(technical_no_duplicate)

    unrelated_stmt = (
        select(CoverImageLinkDecision.source_cover_image_id, CoverImageLinkDecision.candidate_cover_image_id).where(
            CoverImageLinkDecision.decision_state == "active",
            CoverImageLinkDecision.decision_type == "rejected_link",
            CoverImageLinkDecision.relationship_type == "unrelated",
        )
    )
    pairs_for_active_lookup: list[tuple[int, int]] = [*sorted(set(technical_no_dup_final) | set(humans))]
    for left_id, right_id in session.exec(unrelated_stmt).all():
        li, ri = int(left_id), int(right_id)
        if scope is not None and (li not in scope or ri not in scope):
            continue
        pairs_for_active_lookup.append(canonical_edge_tuple(li, ri))

    active_index = _active_decisions_index(session, pairs_for_active_lookup)

    surviving_tech, suppressed_reads = _suppress_technical_vf_edges(
        technical_edges=technical_no_dup_final,
        active_by_pair=active_index,
    )

    merged: defaultdict[tuple[int, int], VFPairAgg] = defaultdict(VFPairAgg)

    filtered_humans: dict[tuple[int, int], VFPairAgg] = {}
    for pair_k2, snippet2 in humans.items():
        if pair_k2 in dup_block:
            continue
        filtered_humans[pair_k2] = snippet2

    for pair_key, snippet in surviving_tech.items():
        merged[pair_key].merge_inplace(snippet)
    for pair_key, snippet in filtered_humans.items():
        merged[pair_key].merge_inplace(snippet)
    final_edges = dict(merged)
    return final_edges, technical_pre_merge, technical_no_dup_final, suppressed_reads, dup_block


def _apply_vf_cluster_filter(
    clusters: list[VariantFamilyClusterRead],
    filt: VariantFamilyClassificationFilter,
) -> list[VariantFamilyClusterRead]:
    if filt == "all":
        return clusters
    if filt == "confirmed":
        return [row for row in clusters if row.classification == "confirmed"]
    if filt == "probable":
        return [row for row in clusters if row.classification == "probable"]
    return []


def _apply_vf_suppressed_filter(
    suppressed: list[VariantFamilySuppressedPairRead],
    filt: VariantFamilyClassificationFilter,
) -> list[VariantFamilySuppressedPairRead]:
    if filt in {"all", "suppressed"}:
        return sorted(suppressed, key=lambda row: (row.pair_key, row.left_cover_image_id))
    return []


def variant_family_candidates_for_cover_owner(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User,
) -> VariantFamilyCandidatesResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    uid = current_user.id
    assert uid is not None
    scope_bundle = owner_cover_scope(session, user_id=int(uid))
    focal_i = int(cover_image_id)

    merged_edges_bundle, _, _, suppressed_reads, _ = _variant_family_graph(session, scope=scope_bundle)
    clustered_layout = vf_clusters_from_edges(merged_edges_bundle)

    reads_cluster = [_build_vf_cluster_read(mb, merged_edges_bundle) for mb in clustered_layout]
    reachable_blocks = [
        clustered_row for clustered_row in reads_cluster if focal_i in set(clustered_row.cover_image_ids)
    ]
    reachable_blocks.sort(key=lambda item: tuple(item.cover_image_ids))

    neighbor_manifest = _neighbor_variant_reads_for_focal(
        session,
        focal_i=focal_i,
        reachable_clusters=reachable_blocks,
        merged_edges_bundle=merged_edges_bundle,
    )
    focal_suppressed = sorted(
        [
            suppressed_row_one
            for suppressed_row_one in suppressed_reads
            if focal_i in {suppressed_row_one.left_cover_image_id, suppressed_row_one.right_cover_image_id}
        ],
        key=lambda row: row.pair_key,
    )
    return VariantFamilyCandidatesResponse(
        focal_cover_image_id=focal_i,
        touching_clusters=reachable_blocks,
        variant_peers=neighbor_manifest,
        suppressed_pairs_touching_focal=focal_suppressed,
    )


def variant_family_candidates_for_ops(
    session: Session,
    *,
    cover_image_id: int,
) -> VariantFamilyCandidatesResponse:
    _ = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=int(cover_image_id))
    focal_i = int(cover_image_id)
    merged_edges_bundle, _, _, suppressed_reads, _ = _variant_family_graph(session, scope=None)

    clustered_layout = vf_clusters_from_edges(merged_edges_bundle)
    reads_cluster = [_build_vf_cluster_read(mb, merged_edges_bundle) for mb in clustered_layout]
    reachable_blocks = [
        clustered_line for clustered_line in reads_cluster if focal_i in set(clustered_line.cover_image_ids)
    ]
    reachable_blocks.sort(key=lambda item: tuple(item.cover_image_ids))
    neighbor_manifest = _neighbor_variant_reads_for_focal(
        session,
        focal_i=focal_i,
        reachable_clusters=reachable_blocks,
        merged_edges_bundle=merged_edges_bundle,
    )
    focal_suppressed = sorted(
        [
            sp
            for sp in suppressed_reads
            if focal_i in {sp.left_cover_image_id, sp.right_cover_image_id}
        ],
        key=lambda row: row.pair_key,
    )
    return VariantFamilyCandidatesResponse(
        focal_cover_image_id=focal_i,
        touching_clusters=reachable_blocks,
        variant_peers=neighbor_manifest,
        suppressed_pairs_touching_focal=focal_suppressed,
    )


def list_variant_family_clusters_for_owner(
    session: Session,
    *,
    current_user: User,
    classification_filter: VariantFamilyClassificationFilter = "all",
) -> VariantFamilyClustersListResponse:
    uid = current_user.id
    assert uid is not None
    scope_bundle = owner_cover_scope(session, user_id=int(uid))
    merged_edges_bundle, _, _, suppressed_all, _ = _variant_family_graph(session, scope=scope_bundle)
    clustered_layout = vf_clusters_from_edges(merged_edges_bundle)
    clustered_reads = [_build_vf_cluster_read(mb, merged_edges_bundle) for mb in clustered_layout]
    clustered_reads.sort(key=lambda item: tuple(item.cover_image_ids))
    return VariantFamilyClustersListResponse(
        clusters=_apply_vf_cluster_filter(clustered_reads, classification_filter),
        suppressed_pairs=_apply_vf_suppressed_filter(suppressed_all, classification_filter),
        classification_filter=classification_filter,
    )


def list_variant_family_clusters_for_ops(
    session: Session,
    *,
    classification_filter: VariantFamilyClassificationFilter = "all",
) -> VariantFamilyClustersListResponse:
    merged_edges_bundle, _, _, suppressed_all, _ = _variant_family_graph(session, scope=None)
    clustered_layout = vf_clusters_from_edges(merged_edges_bundle)
    clustered_reads = [_build_vf_cluster_read(mb, merged_edges_bundle) for mb in clustered_layout]
    clustered_reads.sort(key=lambda item: tuple(item.cover_image_ids))
    return VariantFamilyClustersListResponse(
        clusters=_apply_vf_cluster_filter(clustered_reads, classification_filter),
        suppressed_pairs=_apply_vf_suppressed_filter(suppressed_all, classification_filter),
        classification_filter=classification_filter,
    )
