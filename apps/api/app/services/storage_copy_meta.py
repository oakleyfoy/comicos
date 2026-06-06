"""Shared inventory copy metadata for P79 storage services."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Publisher, Variant
from app.models.p72_grading_operations import P72GradingQueueEntry, P72InventoryGradingHistory


def section_for_slot(slot_number: int) -> str:
    return f"Section {(max(1, slot_number) - 1) // 25 + 1}"


def copy_display_meta(session: Session, copy: InventoryCopy) -> dict[str, str]:
    variant = session.get(Variant, copy.variant_id)
    series = ""
    issue_num = ""
    variant_label = ""
    publisher = ""
    title = ""
    if variant is not None:
        issue = session.get(ComicIssue, variant.comic_issue_id)
        if issue is not None:
            issue_num = issue.issue_number
            ct = session.get(ComicTitle, issue.comic_title_id)
            if ct is not None:
                series = ct.name
                title = f"{series} #{issue_num}"
                pub = session.get(Publisher, ct.publisher_id)
                publisher = pub.name if pub else ""
        parts = [variant.cover_name, variant.printing, variant.ratio, variant.variant_type]
        variant_label = " / ".join(p for p in parts if p) or "Standard"
    if not title:
        title = f"Copy {copy.id}"
    return {
        "title": title,
        "series_name": series,
        "issue_number": issue_num,
        "variant_label": variant_label,
        "publisher": publisher,
    }


def copy_search_blob(session: Session, copy: InventoryCopy) -> str:
    meta = copy_display_meta(session, copy)
    bits = [
        meta["title"],
        meta["series_name"],
        meta["issue_number"],
        meta["variant_label"],
        meta["publisher"],
        str(copy.id or ""),
        copy.metadata_identity_key or "",
        copy.condition_notes or "",
    ]
    cert_rows = session.exec(
        select(P72InventoryGradingHistory.certification_number)
        .where(P72InventoryGradingHistory.inventory_copy_id == int(copy.id or 0))
    ).all()
    queue_rows = session.exec(
        select(P72GradingQueueEntry.certification_number)
        .where(P72GradingQueueEntry.inventory_copy_id == int(copy.id or 0))
    ).all()
    for c in cert_rows + queue_rows:
        if c:
            bits.append(str(c))
    return " ".join(bits).lower()
