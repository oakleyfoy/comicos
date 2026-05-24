"""Deterministic duplicate scan visibility — read-only; no merges, deletes, or metadata mutation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    CoverImage,
    CoverImageDerivative,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    DraftImport,
    InventoryCopy,
    User,
)
from app.schemas.duplicate_scan import (
    DuplicateScanCandidatesResponse,
    DuplicateScanClassificationFilter,
    DuplicateScanClusterRead,
    DuplicateScanClustersListResponse,
    DuplicateScanDuplicatePeerRead,
    DuplicateScanEvidenceFlags,
    DuplicateScanEvidenceStrength,
    DuplicateScanSuppressedPairRead,
)
from app.services.cover_images import (
    _fingerprint_similarity_metrics,
    _grouping_fp_strong,
    get_cover_entity_for_processing_by_ops_or_404,
    get_cover_entity_for_processing_by_owner,
)
from app.services.cover_link_decisions import active_cover_link_decisions_for_pairs, cover_link_pair_key


def canonical_edge_tuple(left_id: int, right_id: int) -> tuple[int, int]:
    left, right = int(left_id), int(right_id)
    return (left, right) if left < right else (right, left)


def stable_cluster_key(sorted_cover_ids: list[int]) -> str:
    payload = "|".join(str(cid) for cid in sorted_cover_ids).encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()
    return f"dup_cluster:{digest[:24]}"


@dataclass
class PairAgg:
    human_confirmed: bool = False
    human_duplicate_scan_decision_id: int | None = None
    sha256_exact: bool = False
    match_candidate_group_duplicate_scan: bool = False
    fingerprint_probable: bool = False
    match_candidate_ids: list[int] = field(default_factory=list)
    grouping_keys_sorted: list[str] = field(default_factory=list)
    shared_upcs: set[str] = field(default_factory=set)
    fingerprint_metrics: dict[str, float] | None = None

    def merge_inplace(self, other: PairAgg) -> None:
        self.human_confirmed = self.human_confirmed or other.human_confirmed
        if other.human_duplicate_scan_decision_id is not None:
            if self.human_duplicate_scan_decision_id is None:
                self.human_duplicate_scan_decision_id = other.human_duplicate_scan_decision_id
            else:
                self.human_duplicate_scan_decision_id = min(
                    self.human_duplicate_scan_decision_id,
                    other.human_duplicate_scan_decision_id,
                )
        self.sha256_exact = self.sha256_exact or other.sha256_exact
        self.match_candidate_group_duplicate_scan = (
            self.match_candidate_group_duplicate_scan or other.match_candidate_group_duplicate_scan
        )
        self.fingerprint_probable = self.fingerprint_probable or other.fingerprint_probable
        for mid in other.match_candidate_ids:
            if mid not in self.match_candidate_ids:
                self.match_candidate_ids.append(mid)
        self.match_candidate_ids.sort()
        self.grouping_keys_sorted = sorted(set([*self.grouping_keys_sorted, *other.grouping_keys_sorted]))
        self.shared_upcs |= other.shared_upcs
        if other.fingerprint_metrics is not None:
            self.fingerprint_metrics = dict(other.fingerprint_metrics)


def owner_cover_scope(session: Session, *, user_id: int) -> frozenset[int]:
    inv_ids = session.exec(
        select(CoverImage.id)
        .join(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .where(InventoryCopy.user_id == user_id)
    ).all()

    draft_ids = session.exec(
        select(CoverImage.id)
        .join(DraftImport, CoverImage.draft_import_id == DraftImport.id)
        .where(DraftImport.user_id == user_id)
    ).all()


    merged = {int(cid) for cid in [*inv_ids, *draft_ids]}

    return frozenset(merged)


def _merge_pair_chunks(*chunks: dict[tuple[int, int], PairAgg]) -> dict[tuple[int, int], PairAgg]:
    merged: defaultdict[tuple[int, int], PairAgg] = defaultdict(PairAgg)
    for key in sorted({k for blob in chunks for k in blob}):
        for blob in chunks:
            if key in blob:

                merged[key].merge_inplace(blob[key])
    return dict(merged)


def _collect_shared_upcs(piece: PairAgg, matched_signals: dict[str, object]) -> None:
    barcode_matches = matched_signals.get("barcode_matches")
    if not isinstance(barcode_matches, list):

        return
    for candidate in barcode_matches:

        if isinstance(candidate, str) and candidate.strip():
            piece.shared_upcs.add(candidate.strip())


def _match_candidate_pair_piece(row: CoverImageMatchCandidate) -> PairAgg | None:
    if row.dismissed_at is not None:
        return None
    signals = dict(row.matched_signals or {})
    fingerprint_payload = dict(_fingerprint_similarity_metrics(signals))
    ctype = str(row.candidate_type)
    grouping_valid = row.grouping_type == "probable_duplicate_scan"


    barcode_or_ocr_family = ctype in {"ocr_similarity", "barcode_similarity"}

    fingerprint_family_types = ctype in {"fingerprint_similarity", "combined_similarity"}

    fingerprint_path_ok = False
    if barcode_or_ocr_family and _grouping_fp_strong(fingerprint_payload):
        fingerprint_path_ok = True
    elif fingerprint_family_types and _grouping_fp_strong(fingerprint_payload):
        fingerprint_path_ok = True

    snippet = PairAgg()
    if grouping_valid:


        snippet.match_candidate_group_duplicate_scan = True


        snippet.fingerprint_metrics = fingerprint_payload
        _collect_shared_upcs(snippet, signals)
        if row.grouping_key:
            snippet.grouping_keys_sorted = [row.grouping_key]




    if fingerprint_path_ok:


        snippet.fingerprint_probable = True
        snippet.fingerprint_metrics = fingerprint_payload
        _collect_shared_upcs(snippet, signals)

    if not snippet.match_candidate_group_duplicate_scan and not snippet.fingerprint_probable:
        return None

    if row.id is not None:
        snippet.match_candidate_ids = sorted({*snippet.match_candidate_ids, int(row.id)})
    snippet.grouping_keys_sorted = sorted(set(snippet.grouping_keys_sorted))


    return snippet


def _sha256_edges(session: Session, *, scope: frozenset[int] | None) -> dict[tuple[int, int], PairAgg]:
    if scope == frozenset():
        return {}

    stmt = select(CoverImage.id, CoverImage.sha256_hash)
    if scope is not None:


        stmt = stmt.where(CoverImage.id.in_(sorted(scope)))

    buckets: defaultdict[str, list[int]] = defaultdict(list)
    for cid, digest in session.exec(stmt).all():
        buckets[digest].append(int(cid))



    merged: defaultdict[tuple[int, int], PairAgg] = defaultdict(PairAgg)



    for digest_key in sorted(buckets.keys()):
        covers = sorted(set(buckets[digest_key]))
        if len(covers) < 2:
            continue




        pivot = covers[0]
        for sibling in covers[1:]:
            tup = canonical_edge_tuple(pivot, sibling)
            merged[tup].merge_inplace(PairAgg(sha256_exact=True))



    return dict(merged)



def _match_candidate_edges(session: Session, *, scope: frozenset[int] | None) -> dict[tuple[int, int], PairAgg]:
    merged: defaultdict[tuple[int, int], PairAgg] = defaultdict(PairAgg)


    stmt = select(CoverImageMatchCandidate).where(CoverImageMatchCandidate.dismissed_at.is_(None))  # type: ignore[union-attr]
    for row in session.exec(stmt).all():
        src = int(row.source_cover_image_id)
        cand = int(row.candidate_cover_image_id)

        if scope is not None and (src not in scope or cand not in scope):
            continue
        snippet = _match_candidate_pair_piece(row)
        if snippet is None:


            continue



        tup = canonical_edge_tuple(src, cand)
        merged[tup].merge_inplace(snippet)
    return dict(merged)



def _human_duplicate_edges(session: Session, *, scope: frozenset[int] | None) -> dict[tuple[int, int], PairAgg]:
    merged: defaultdict[tuple[int, int], PairAgg] = defaultdict(PairAgg)

    stmt = select(CoverImageLinkDecision).where(
        CoverImageLinkDecision.decision_state == "active",
        CoverImageLinkDecision.decision_type == "approved_link",
        CoverImageLinkDecision.relationship_type == "duplicate_scan",


    )
    rows = session.exec(stmt).all()


    for row in rows:


        src = int(row.source_cover_image_id)


        cand = int(row.candidate_cover_image_id)
        if scope is not None and (src not in scope or cand not in scope):

            continue
        tup = canonical_edge_tuple(src, cand)



        snippet = PairAgg(
            human_confirmed=True,

            human_duplicate_scan_decision_id=int(row.id) if row.id is not None else None,
        )


        merged[tup].merge_inplace(snippet)
    return dict(merged)



def _pair_actively_unrelated(pair_key_str: str, active_by_pair: dict[str, CoverImageLinkDecision]) -> bool:
    snap = active_by_pair.get(pair_key_str)
    if snap is None:
        return False
    return snap.decision_type == "rejected_link" and snap.relationship_type == "unrelated"


class _DU:
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


def _rank_for_agg(agg: PairAgg) -> int:
    if agg.human_confirmed:
        return 0



    if agg.sha256_exact:
        return 1


    if agg.match_candidate_group_duplicate_scan:
        return 2


    if agg.fingerprint_probable:
        return 3




    return 4


def _strength_literal_from_best_rank(rank: int) -> DuplicateScanEvidenceStrength:
    if rank == 0:
        return "human_confirmed"
    if rank == 1:
        return "sha256_exact_match"
    if rank == 2:


        return "probable_duplicate_scan_group"


    if rank == 3:
        return "fingerprint_similarity"



    return "mixed"


def _cluster_evidence_strength(rank_list: list[int]) -> DuplicateScanEvidenceStrength:
    uniq_rank = sorted(set(rank_list))


    if 0 in uniq_rank:
        return "human_confirmed"
    tiers = sorted({r for r in uniq_rank if r < 4})


    if not tiers:


        return "mixed"
    lowest = tiers[0]


    if lowest == 1 and len({r for r in tiers if r > 1}) > 0:
        return "mixed"



    return _strength_literal_from_best_rank(lowest)


def _flags_from_agg(agg: PairAgg) -> DuplicateScanEvidenceFlags:


    supporting = sorted(agg.shared_upcs)

    flags = DuplicateScanEvidenceFlags(
        human_duplicate_scan_confirmed=agg.human_confirmed,
        sha256_exact_match=agg.sha256_exact,

        probable_duplicate_scan_match_group=agg.match_candidate_group_duplicate_scan,

        fingerprint_similarity_probable=agg.fingerprint_probable,
        supporting_shared_upcs=[] if supporting is None else supporting,
    )
    return flags


def _derivative_counts(session: Session, cover_ids: set[int]) -> dict[int, int]:
    if not cover_ids:


        return {}
    stmt = (
        select(CoverImageDerivative.cover_image_id, func.count())
        .where(CoverImageDerivative.cover_image_id.in_(sorted(cover_ids)))
        .group_by(CoverImageDerivative.cover_image_id)


    )


    rows = session.exec(stmt).all()
    out: dict[int, int] = {}
    for cover_id_i, qty in rows:
        out[int(cover_id_i)] = int(qty)
    return out


def _cover_dimension_map(session: Session, cover_ids: set[int]) -> dict[int, dict[str, int | None]]:
    if not cover_ids:


        return {}
    exec_rows = session.exec(
        select(CoverImage.id, CoverImage.image_width, CoverImage.image_height).where(CoverImage.id.in_(sorted(cover_ids)))


    ).all()


    return {int(rid): {"width": w, "height": h} for rid, w, h in exec_rows}


def _evidence_signals_for_agg(tech_only: PairAgg) -> list[str]:
    snaps: list[str] = []

    if tech_only.sha256_exact:

        snaps.append("sha256_exact_match")






    if tech_only.match_candidate_group_duplicate_scan:
        snaps.append("probable_duplicate_scan_match_group")


    if tech_only.fingerprint_probable:


        snaps.append("fingerprint_similarity_probable")
    supporting = sorted(tech_only.shared_upcs)
    if supporting:
        snaps.append("supporting_shared_upcs")
    return sorted(set(snaps))


def _suppress_tech_duplicate_edges(
    _session: Session,
    *,
    technical_edges: dict[tuple[int, int], PairAgg],
    active_by_pair: dict[str, CoverImageLinkDecision],
) -> tuple[dict[tuple[int, int], PairAgg], list[DuplicateScanSuppressedPairRead]]:
    suppressed: list[DuplicateScanSuppressedPairRead] = []

    surviving: defaultdict[tuple[int, int], PairAgg] = defaultdict(PairAgg)



    ordered_keys = sorted(technical_edges)



    for pair in ordered_keys:

        agg = technical_edges[pair]
        pk_str = cover_link_pair_key(pair[0], pair[1])
        if _pair_actively_unrelated(pk_str, active_by_pair):
            suppressed.append(
                DuplicateScanSuppressedPairRead(
                    pair_key=pk_str,
                    left_cover_image_id=pair[0],
                    right_cover_image_id=pair[1],
                    suppressed_signal_labels=_evidence_signals_for_agg(agg),
                    evidence_snapshot=_flags_from_agg(agg),
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




def _duplicate_scan_graph(
    session: Session,
    *,
    scope: frozenset[int] | None,
) -> tuple[dict[tuple[int, int], PairAgg], dict[tuple[int, int], PairAgg], list[DuplicateScanSuppressedPairRead]]:
    technical_pre = _merge_pair_chunks(
        _sha256_edges(session, scope=scope),
        _match_candidate_edges(session, scope=scope),
    )
    humans = _human_duplicate_edges(session, scope=scope)


    pairs_for_active_lookup: list[tuple[int, int]] = [
        *[t for t in sorted(set(technical_pre) | set(humans))],
    ]

    unrelated_stmt = (
        select(CoverImageLinkDecision.source_cover_image_id, CoverImageLinkDecision.candidate_cover_image_id).where(
            CoverImageLinkDecision.decision_state == "active",
            CoverImageLinkDecision.decision_type == "rejected_link",
            CoverImageLinkDecision.relationship_type == "unrelated",


        )
    )


    for left_id, right_id in session.exec(unrelated_stmt).all():
        left_i, right_i = int(left_id), int(right_id)
        if scope is not None and (left_i not in scope or right_i not in scope):


            continue


        pairs_for_active_lookup.append(canonical_edge_tuple(left_i, right_i))


    active_index = _active_decisions_index(session, pairs_for_active_lookup)


    technical_final, suppressed_reads = _suppress_tech_duplicate_edges(
        session,
        technical_edges=technical_pre,
        active_by_pair=active_index,
    )


    merged: defaultdict[tuple[int, int], PairAgg] = defaultdict(PairAgg)


    for pair_key, snippet in technical_final.items():
        merged[pair_key].merge_inplace(snippet)
    for pair_key, snippet in humans.items():
        merged[pair_key].merge_inplace(snippet)


    return dict(merged), technical_pre, suppressed_reads


def _collect_nodes_from_edges(merged_edges: dict[tuple[int, int], PairAgg]) -> set[int]:
    members: set[int] = set()
    for pa, pb in merged_edges:


        members.add(pa)
        members.add(pb)



    return members


def _clusters_from_edges(merged_edges: dict[tuple[int, int], PairAgg]) -> list[list[int]]:
    members = _collect_nodes_from_edges(merged_edges)
    if not members:


        return []
    forest = _DU()
    for left_id, right_id in merged_edges:
        forest.unite(left_id, right_id)


    roots: defaultdict[int, list[int]] = defaultdict(list)
    for cover_id_member in sorted(members):

        anchor = forest._touch(cover_id_member)
        roots[anchor].append(cover_id_member)


    clustered = [sorted(v) for v in roots.values() if len(v) >= 2]
    clustered.sort(key=lambda group: tuple(group))
    return clustered


def _build_duplicate_scan_cluster_read(
    cover_ids_sorted: list[int],
    merged_edges: dict[tuple[int, int], PairAgg],
) -> DuplicateScanClusterRead:


    cid_set = set(cover_ids_sorted)



    tiers: list[int] = []
    anybody_human = False




    ordered_edges = sorted(merged_edges.items(), key=lambda kv: kv[0])
    for (left_id, right_id), snippet in ordered_edges:
        if left_id not in cid_set or right_id not in cid_set:

            continue




        tiers.append(_rank_for_agg(snippet))



        anybody_human = anybody_human or snippet.human_confirmed


    tier_rank_strength_literal = _cluster_evidence_strength(tiers)



    clustering_label = stable_cluster_key(cover_ids_sorted)


    return DuplicateScanClusterRead(
        cluster_key=clustering_label,
        cover_image_ids=list(cover_ids_sorted),

        cluster_size=len(cover_ids_sorted),
        classification="confirmed" if anybody_human else "probable",


        evidence_strength=tier_rank_strength_literal,







    )

def _apply_cluster_filter(
    clusters: list[DuplicateScanClusterRead],
    filt: DuplicateScanClassificationFilter,

) -> list[DuplicateScanClusterRead]:
    if filt == "all":


        return clusters
    if filt == "confirmed":


        return [row for row in clusters if row.classification == "confirmed"]
    if filt == "probable":
        return [row for row in clusters if row.classification == "probable"]
    return []


def _apply_suppressed_filter(
    suppressed: list[DuplicateScanSuppressedPairRead],

    filt: DuplicateScanClassificationFilter,

) -> list[DuplicateScanSuppressedPairRead]:
    if filt in {"all", "suppressed"}:
        out = sorted(suppressed, key=lambda row: (row.pair_key, row.left_cover_image_id))



        return out


    return []


def _peer_detail_payload(
    *,
    agg: PairAgg,
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
    }



    fingerprint_slice = agg.fingerprint_metrics

    if fingerprint_slice is not None:

        refined = {key: round(value, 6) for key, value in sorted(fingerprint_slice.items())}




        out["fingerprint_similarity_metrics"] = refined


    out["deterministic_signals"] = {
        "sha256_exact": agg.sha256_exact,
        "probable_duplicate_scan_group": agg.match_candidate_group_duplicate_scan,
        "fingerprint_probable_duplicate_scan": agg.fingerprint_probable,


        "human_confirmed_duplicate_scan": agg.human_confirmed,

    }


    return out


def _neighbor_duplicate_reads_for_focal(
    session: Session,
    *,
    focal_i: int,

    reachable_clusters: list[DuplicateScanClusterRead],
    merged_edges_bundle: dict[tuple[int, int], PairAgg],

) -> list[DuplicateScanDuplicatePeerRead]:





    reachable_clusters.sort(key=lambda c: tuple(c.cover_image_ids))

    aggregated_reads: dict[int, DuplicateScanDuplicatePeerRead] = {}

    for cluster_snapshot in reachable_clusters:
        peers_chain_all = sorted(p for p in cluster_snapshot.cover_image_ids if int(p) != focal_i)
        for neighbor_pid in peers_chain_all:
            pairing_bundle = canonical_edge_tuple(focal_i, int(neighbor_pid))
            enrichment_ids_here = {focal_i, int(neighbor_pid)}
            dims_bundle = _cover_dimension_map(session, enrichment_ids_here)
            derivatives_bundle_hint = _derivative_counts(session, enrichment_ids_here)
            snippet_direct_candidate = merged_edges_bundle.get(pairing_bundle)



            if snippet_direct_candidate is not None:
                flagged_candidate = DuplicateScanDuplicatePeerRead(
                    peer_cover_image_id=int(neighbor_pid),
                    pair_key=cover_link_pair_key(focal_i, int(neighbor_pid)),
                    canonical_pair_low_id=int(pairing_bundle[0]),
                    canonical_pair_high_id=int(pairing_bundle[1]),
                    classification=("confirmed" if snippet_direct_candidate.human_confirmed else "probable"),
                    evidences=_flags_from_agg(snippet_direct_candidate),
                    evidence_detail=_peer_detail_payload(
                        agg=snippet_direct_candidate,
                        dims=dims_bundle,
                        derivatives=derivatives_bundle_hint,
                        focal_id=focal_i,

                        peer_id=int(neighbor_pid),
                    ),

                    match_candidate_ids=list(snippet_direct_candidate.match_candidate_ids),
                    human_duplicate_scan_decision_id=snippet_direct_candidate.human_duplicate_scan_decision_id,


                )
            else:
                bridging_detail: dict[str, object] = {
                    "cluster_transitive_duplicate_scan": True,
                    "touching_cluster_key": cluster_snapshot.cluster_key,
                    "touching_cluster_evidence_strength": cluster_snapshot.evidence_strength,
                    "touching_cluster_classification": cluster_snapshot.classification,
                }
                bridging_detail.update(
                    _peer_detail_payload(
                        agg=PairAgg(),
                        dims=dims_bundle,
                        derivatives=derivatives_bundle_hint,
                        focal_id=focal_i,

                        peer_id=int(neighbor_pid),
                    )


                )


                flagged_candidate = DuplicateScanDuplicatePeerRead(
                    peer_cover_image_id=int(neighbor_pid),

                    pair_key=cover_link_pair_key(focal_i, int(neighbor_pid)),
                    canonical_pair_low_id=int(pairing_bundle[0]),
                    canonical_pair_high_id=int(pairing_bundle[1]),

                    classification="probable",

                    evidences=DuplicateScanEvidenceFlags(),
                    evidence_detail=bridging_detail,
                    match_candidate_ids=[],
                    human_duplicate_scan_decision_id=None,


                )
            incumbent = aggregated_reads.get(int(neighbor_pid))
            if incumbent is None or (incumbent.classification != "confirmed" and flagged_candidate.classification == "confirmed"):






                aggregated_reads[int(neighbor_pid)] = flagged_candidate


    return [aggregated_reads[k] for k in sorted(aggregated_reads)]



def duplicate_scan_candidates_for_cover_owner(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User,
) -> DuplicateScanCandidatesResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,

        cover_image_id=cover_image_id,
    )
    uid = current_user.id
    assert uid is not None
    scope_bundle = owner_cover_scope(session, user_id=int(uid))



    focal_i = int(cover_image_id)
    merged_edges_bundle, _, suppressed_reads = _duplicate_scan_graph(session, scope=scope_bundle)



    clustered_layout = _clusters_from_edges(merged_edges_bundle)

    reads_cluster: list[DuplicateScanClusterRead] = []

    reads_cluster.extend(
        [_build_duplicate_scan_cluster_read(mb, merged_edges_bundle) for mb in clustered_layout]
    )



    reachable_blocks = [
        clustered_row for clustered_row in reads_cluster if focal_i in set(clustered_row.cover_image_ids)
    ]

    reachable_blocks.sort(key=lambda item: tuple(item.cover_image_ids))




    neighbor_peers_manifest = _neighbor_duplicate_reads_for_focal(
        session,
        focal_i=focal_i,
        reachable_clusters=reachable_blocks,
        merged_edges_bundle=merged_edges_bundle,
    )


    focal_suppressed_reads = sorted(
        [
            suppressed_row_one
            for suppressed_row_one in suppressed_reads





            if focal_i in {suppressed_row_one.left_cover_image_id, suppressed_row_one.right_cover_image_id}







        ],

        key=lambda row: row.pair_key,


    )



    return DuplicateScanCandidatesResponse(
        focal_cover_image_id=focal_i,
        touching_clusters=reachable_blocks,
        duplicate_peers=neighbor_peers_manifest,
        suppressed_pairs_touching_focal=focal_suppressed_reads,


    )



def duplicate_scan_candidates_for_ops(
    session: Session,
    *,
    cover_image_id: int,

) -> DuplicateScanCandidatesResponse:
    _ = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=int(cover_image_id))

    focal_i = int(cover_image_id)

    merged_edges_bundle, _, suppressed_reads = _duplicate_scan_graph(session, scope=None)
    clustered_layout = _clusters_from_edges(merged_edges_bundle)

    reads_cluster = [_build_duplicate_scan_cluster_read(group_block_ops, merged_edges_bundle) for group_block_ops in clustered_layout]



    reachable_blocks = [cluster_line for cluster_line in reads_cluster if focal_i in set(cluster_line.cover_image_ids)]







    reachable_blocks.sort(key=lambda item: tuple(item.cover_image_ids))



    neighbor_peers_manifest = _neighbor_duplicate_reads_for_focal(
        session,
        focal_i=focal_i,
        reachable_clusters=reachable_blocks,
        merged_edges_bundle=merged_edges_bundle,
    )


    focal_suppressed_reads = sorted(
        [
            suppressed_row_two


            for suppressed_row_two in suppressed_reads


            if focal_i


            in {suppressed_row_two.left_cover_image_id, suppressed_row_two.right_cover_image_id}




        ],

        key=lambda row: row.pair_key,


    )


    return DuplicateScanCandidatesResponse(
        focal_cover_image_id=focal_i,

        touching_clusters=reachable_blocks,
        duplicate_peers=neighbor_peers_manifest,

        suppressed_pairs_touching_focal=focal_suppressed_reads,


    )



def list_duplicate_scan_clusters_for_owner(
    session: Session,
    *,
    current_user: User,
    classification_filter: DuplicateScanClassificationFilter = "all",
) -> DuplicateScanClustersListResponse:
    uid = current_user.id
    assert uid is not None
    scope_bundle = owner_cover_scope(session, user_id=int(uid))

    merged_edges_bundle, _, suppressed_reads_all = _duplicate_scan_graph(session, scope=scope_bundle)

    clustered_layout = _clusters_from_edges(merged_edges_bundle)




    clustered_reads_ordered: list[DuplicateScanClusterRead] = []

    for member_block in clustered_layout:


        clustering_read_placeholder = _build_duplicate_scan_cluster_read(member_block, merged_edges_bundle)



        clustered_reads_ordered.append(clustering_read_placeholder)


    clustered_reads_ordered.sort(key=lambda item: tuple(item.cover_image_ids))




    filtered_clusters = _apply_cluster_filter(clustered_reads_ordered, classification_filter)

    filtered_suppressed = _apply_suppressed_filter(suppressed_reads_all, classification_filter)


    return DuplicateScanClustersListResponse(
        clusters=filtered_clusters,

        suppressed_pairs=filtered_suppressed,
        classification_filter=classification_filter,


    )



def list_duplicate_scan_clusters_for_ops(
    session: Session,
    *,
    classification_filter: DuplicateScanClassificationFilter = "all",


) -> DuplicateScanClustersListResponse:
    merged_edges_bundle, _, suppressed_reads_all = _duplicate_scan_graph(session, scope=None)

    clustered_layout = _clusters_from_edges(merged_edges_bundle)





    clustered_reads_ordered: list[DuplicateScanClusterRead] = []

    for member_block in clustered_layout:


        clustering_read_placeholder = _build_duplicate_scan_cluster_read(member_block, merged_edges_bundle)




        clustered_reads_ordered.append(clustering_read_placeholder)




    clustered_reads_ordered.sort(key=lambda item: tuple(item.cover_image_ids))


    filtered_clusters = _apply_cluster_filter(clustered_reads_ordered, classification_filter)

    filtered_suppressed = _apply_suppressed_filter(suppressed_reads_all, classification_filter)

    return DuplicateScanClustersListResponse(
        clusters=filtered_clusters,
        suppressed_pairs=filtered_suppressed,

        classification_filter=classification_filter,


    )
