"""P79-01 locate inventory by series, issue, variant, or copy id."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Variant
from app.models.storage_location import P79InventoryLocationAssignment, P79StorageBox, P79StorageSlot
from app.schemas.storage_foundation import P79StorageSearchResponse, P79StorageSearchResultRead
from app.services.storage_assignment_service import assignment_read, build_location_path


def search_storage(
    session: Session,
    *,
    owner_user_id: int,
    query: str,
    limit: int = 50,
) -> P79StorageSearchResponse:
    q = query.strip()
    if not q:
        return P79StorageSearchResponse(items=[], total_items=0, query=q)

    results: list[P79StorageSearchResultRead] = []
    seen: set[int] = set()

    if q.isdigit():
        copy_id = int(q)
        copy = session.get(InventoryCopy, copy_id)
        if copy is not None and copy.user_id == owner_user_id:
            _append_copy(session, owner_user_id=owner_user_id, copy=copy, results=results, seen=seen)

    assignments = session.exec(
        select(P79InventoryLocationAssignment).where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
    ).all()
    q_lower = q.lower()
    for assignment in assignments:
        copy = session.get(InventoryCopy, assignment.inventory_copy_id)
        if copy is None:
            continue
        variant = session.get(Variant, copy.variant_id)
        if variant is None:
            continue
        issue = session.get(ComicIssue, variant.comic_issue_id)
        if issue is None:
            continue
        title = session.get(ComicTitle, issue.comic_title_id)
        series = (title.name if title else "").lower()
        issue_num = issue.issue_number.lower()
        variant_bits = " ".join(
            filter(None, [variant.cover_name, variant.printing, variant.ratio, variant.variant_type])
        ).lower()
        if q_lower in series or q_lower in issue_num or q_lower in variant_bits or q_lower in f"{series} {issue_num}":
            _append_copy(session, owner_user_id=owner_user_id, copy=copy, results=results, seen=seen)

    page = results[:limit]
    return P79StorageSearchResponse(items=page, total_items=len(results), query=q)


def _append_copy(
    session: Session,
    *,
    owner_user_id: int,
    copy: InventoryCopy,
    results: list[P79StorageSearchResultRead],
    seen: set[int],
) -> None:
    cid = int(copy.id or 0)
    if cid in seen:
        return
    assignment = session.exec(
        select(P79InventoryLocationAssignment)
        .where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        .where(P79InventoryLocationAssignment.inventory_copy_id == cid)
    ).first()
    if assignment is None:
        return
    seen.add(cid)
    read = assignment_read(session, assignment=assignment, copy=copy)
    results.append(
        P79StorageSearchResultRead(
            inventory_copy_id=cid,
            series_name=read.series_name or "",
            issue_number=read.issue_number or "",
            variant_label=read.variant_label or "",
            location_path=read.location_path,
            box_name=read.box_name,
            slot_number=read.slot_number,
        )
    )
