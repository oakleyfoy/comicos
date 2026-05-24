"""Deterministic 1-hop cover relationship graph from active human link decisions only."""

from __future__ import annotations

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    ComicIssue,
    ComicTitle,
    CoverImage,
    CoverImageDerivative,
    CoverImageLinkDecision,
    InventoryCopy,
    OrderItem,
    Publisher,
    User,
    Variant,
)
from app.schemas.cover_relationship_graph import (
    CoverRelationshipGraphEdge,
    CoverRelationshipGraphInventoryMetadata,
    CoverRelationshipGraphNode,
    CoverRelationshipGraphNodeDecisionSummary,
    CoverRelationshipGraphRead,
)
from app.services.cover_images import cover_derivative_fetch_path, cover_fetch_path
from app.services.cover_link_decisions import get_cover_or_404, owner_can_access_cover


def cover_relationship_graph_lane(*, decision_type: str, relationship_type: str) -> str:
    """Map persisted decision rows to UI lanes — no inferred semantics beyond explicit fields."""

    if decision_type == "needs_review":
        return "needs_review"
    if decision_type == "rejected_link":
        return "blocked"
    if decision_type == "approved_link":
        if relationship_type in ("same_cover", "duplicate_scan"):
            return "strong"
        return "related"
    return "needs_review"


def _load_inventory_metadata_map(
    session: Session,
    *,
    inventory_copy_ids: set[int],
    restrict_to_user_id: int | None,
) -> dict[int, CoverRelationshipGraphInventoryMetadata]:
    if not inventory_copy_ids:
        return {}
    stmt = (
        select(
            InventoryCopy.id,
            ComicTitle.name,
            Publisher.name,
            ComicIssue.issue_number,
            Variant.cover_name,
        )
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.id.in_(inventory_copy_ids))
    )
    if restrict_to_user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == restrict_to_user_id)
    rows = session.exec(stmt).all()
    out: dict[int, CoverRelationshipGraphInventoryMetadata] = {}
    for row in rows:
        inv_id, title, publisher, issue_number, cover_name = row
        out[int(inv_id)] = CoverRelationshipGraphInventoryMetadata(
            inventory_copy_id=int(inv_id),
            title=str(title),
            publisher=str(publisher),
            issue_number=str(issue_number),
            cover_name=cover_name,
        )
    return out


def _derivative_paths_by_cover(
    session: Session,
    cover_image_ids: set[int],
) -> dict[int, dict[str, str]]:
    """Return `{cover_id: {thumb|medium: fetch_path}}` for existing derivatives."""

    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageDerivative.cover_image_id, CoverImageDerivative.derivative_type).where(
            CoverImageDerivative.cover_image_id.in_(cover_image_ids),
            CoverImageDerivative.derivative_type.in_(("thumb", "medium")),
        )
    ).all()
    out: dict[int, dict[str, str]] = {}
    for cid, deriv_type in rows:
        cid_i = int(cid)
        t = str(deriv_type)
        out.setdefault(cid_i, {})[t] = cover_derivative_fetch_path(cid_i, t)
    return out


def _incident_nodes_for_cover(
    focal_cover_image_id: int,
    rows: list[CoverImageLinkDecision],
) -> set[int]:
    ids: set[int] = {focal_cover_image_id}
    for row in rows:
        ids.add(int(row.source_cover_image_id))
        ids.add(int(row.candidate_cover_image_id))
    return ids


def _summaries_for_edges(
    node_ids: set[int], edges_sorted: list[CoverRelationshipGraphEdge]
) -> dict[int, CoverRelationshipGraphNodeDecisionSummary]:
    summaries: dict[int, CoverRelationshipGraphNodeDecisionSummary] = {
        nid: CoverRelationshipGraphNodeDecisionSummary() for nid in sorted(node_ids)
    }

    def bump(node_id: int, lane: str) -> None:
        s = summaries[node_id]
        if lane == "strong":
            s.incident_strong_edges += 1
        elif lane == "related":
            s.incident_related_edges += 1
        elif lane == "blocked":
            s.incident_blocked_edges += 1
        elif lane == "needs_review":
            s.incident_needs_review_edges += 1

    for edge in edges_sorted:
        bump(edge.source_cover_image_id, edge.display_lane)
        bump(edge.candidate_cover_image_id, edge.display_lane)
    return summaries


def build_cover_relationship_graph(
    session: Session,
    *,
    center_cover_image_id: int,
    current_user: User | None,
) -> CoverRelationshipGraphRead:
    """
    One-hop subgraph: focal cover plus neighbors touching it via active link decisions.

    Focal-cover ownership is *not* re-checked here; owner routes validate before calling.

    - Ops (`current_user` None): unrestricted inventory joins for enrichment.
    - Owner: incident edges filtered to endpoints the user may access.
      Inventory biblio payloads only for copies owned by that user when applicable.
    """

    restrict_inventory_user: int | None = None if current_user is None else current_user.id

    incident_rows = session.exec(
        select(CoverImageLinkDecision)
        .where(
            CoverImageLinkDecision.decision_state == "active",
            or_(
                CoverImageLinkDecision.source_cover_image_id == center_cover_image_id,
                CoverImageLinkDecision.candidate_cover_image_id == center_cover_image_id,
            ),
        )
        .order_by(
            CoverImageLinkDecision.source_cover_image_id,
            CoverImageLinkDecision.candidate_cover_image_id,
            CoverImageLinkDecision.id,
        )
    ).all()

    visible: list[CoverImageLinkDecision] = []
    if current_user is None:
        visible = list(incident_rows)
    elif current_user.id is None:
        visible = []
    else:
        for row in incident_rows:
            src = get_cover_or_404(session, row.source_cover_image_id)
            cand = get_cover_or_404(session, row.candidate_cover_image_id)
            can_src = owner_can_access_cover(session, cover=src, current_user=current_user)
            can_cand = owner_can_access_cover(session, cover=cand, current_user=current_user)
            if can_src or can_cand:
                visible.append(row)

    node_ids = _incident_nodes_for_cover(center_cover_image_id, visible)
    covers = session.exec(select(CoverImage).where(CoverImage.id.in_(node_ids))).all()
    cover_by_id: dict[int, CoverImage] = {int(c.id): c for c in covers if c.id is not None}

    inventory_ids: set[int] = set()
    for cid in sorted(node_ids):
        c_row = cover_by_id.get(cid)
        if c_row is not None and c_row.inventory_copy_id is not None:
            inventory_ids.add(int(c_row.inventory_copy_id))

    inv_meta = _load_inventory_metadata_map(
        session,
        inventory_copy_ids=inventory_ids,
        restrict_to_user_id=restrict_inventory_user,
    )

    deriv_map = _derivative_paths_by_cover(session, node_ids)

    edges: list[CoverRelationshipGraphEdge] = []
    for row in visible:
        if row.id is None:
            continue
        lane = cover_relationship_graph_lane(
            decision_type=row.decision_type, relationship_type=row.relationship_type
        )
        edges.append(
            CoverRelationshipGraphEdge(
                source_cover_image_id=int(row.source_cover_image_id),
                candidate_cover_image_id=int(row.candidate_cover_image_id),
                relationship_type=row.relationship_type,  # type: ignore[arg-type]
                decision_type=row.decision_type,  # type: ignore[arg-type]
                decision_id=int(row.id),
                created_at=row.created_at,
                reviewer_user_id=row.reviewer_user_id,
                decision_reason=row.decision_reason,
                display_lane=lane,  # type: ignore[arg-type]
            )
        )

    edges_sorted = sorted(
        edges,
        key=lambda e: (
            e.source_cover_image_id,
            e.candidate_cover_image_id,
            e.decision_id,
        ),
    )
    summary_by_node = _summaries_for_edges(node_ids, edges_sorted)

    nodes_out: list[CoverRelationshipGraphNode] = []
    for nid in sorted(node_ids):
        c_row = cover_by_id.get(nid)
        if c_row is None:
            continue
        inv_payload: CoverRelationshipGraphInventoryMetadata | None = None
        if c_row.inventory_copy_id is not None:
            inv_payload = inv_meta.get(int(c_row.inventory_copy_id))
        dpaths = deriv_map.get(nid, {})
        nodes_out.append(
            CoverRelationshipGraphNode(
                cover_image_id=nid,
                inventory=inv_payload,
                primary_fetch_path=cover_fetch_path(nid),
                thumbnail_fetch_path=dpaths.get("thumb"),
                medium_fetch_path=dpaths.get("medium"),
                decision_summary=summary_by_node[nid],
            )
        )

    return CoverRelationshipGraphRead(
        center_cover_image_id=center_cover_image_id,
        nodes=nodes_out,
        edges=edges_sorted,
    )


def get_cover_relationship_graph_for_owner(
    session: Session,
    *,
    center_cover_image_id: int,
    current_user: User,
) -> CoverRelationshipGraphRead:
    from fastapi import HTTPException

    focal_cover = get_cover_or_404(session, center_cover_image_id)
    if current_user.id is None or not owner_can_access_cover(
        session, cover=focal_cover, current_user=current_user
    ):
        raise HTTPException(status_code=404, detail="Cover image not found")

    return build_cover_relationship_graph(
        session,
        center_cover_image_id=center_cover_image_id,
        current_user=current_user,
    )


def get_cover_relationship_graph_for_ops(
    session: Session,
    *,
    center_cover_image_id: int,
) -> CoverRelationshipGraphRead:
    get_cover_or_404(session, center_cover_image_id)
    return build_cover_relationship_graph(
        session,
        center_cover_image_id=center_cover_image_id,
        current_user=None,
    )
