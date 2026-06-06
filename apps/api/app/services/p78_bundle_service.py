"""P78-01 bundle opportunity detection."""

from __future__ import annotations

import re

from sqlmodel import Session

from app.schemas.p78_sell_workflow import P78SellBundleListResponse, P78SellBundleRead
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p77_personalization_engine import load_personalization_context


def _issue_sort_key(issue: str) -> float:
    try:
        return float(re.sub(r"[^0-9.]", "", issue) or "0")
    except ValueError:
        return 0.0


def list_sell_bundles(session: Session, *, owner_user_id: int) -> P78SellBundleListResponse:
    queue = build_sell_queue(session, owner_user_id=owner_user_id, limit=300, offset=0, refresh_upstream=False)
    p77 = load_personalization_context(session, owner_user_id=owner_user_id)
    characters = [c.label.lower() for c in p77.profile.characters[:6]]
    publishers = [p.label.lower() for p in p77.profile.publishers[:6]]

    by_series: dict[str, list] = {}
    for item in queue.items:
        if item.priority == "WATCH" and item.suggested_sell_quantity <= 0:
            continue
        series = item.title.split("#")[0].strip() or item.title
        by_series.setdefault(series.lower(), []).append(item)

    bundles: list[P78SellBundleRead] = []

    for series_key, members in by_series.items():
        if len(members) < 3:
            continue
        members_sorted = sorted(members, key=lambda m: _issue_sort_key(m.issue_number))
        fmv = sum(m.fmv for m in members_sorted)
        label = f"{members_sorted[0].title.split('#')[0].strip()} run ({len(members_sorted)} issues)"
        bundles.append(
            P78SellBundleRead(
                bundle_key=f"run:{series_key}",
                bundle_type="RUN",
                label=label,
                item_count=len(members_sorted),
                inventory_copy_ids=[m.inventory_copy_id for m in members_sorted],
                expected_bundle_fmv=round(fmv, 2),
                suggested_list_price=round(fmv * 0.92, 2),
                signals=["Complete or partial run bundle", f"{len(members_sorted)} sell-queue issues"],
            )
        )

    for ch in characters:
        matched = [i for i in queue.items if ch in i.title.lower() and i.priority != "WATCH"]
        if len(matched) >= 2:
            fmv = sum(m.fmv for m in matched)
            bundles.append(
                P78SellBundleRead(
                    bundle_key=f"character:{ch}",
                    bundle_type="CHARACTER",
                    label=f"{ch.title()} set",
                    item_count=len(matched),
                    inventory_copy_ids=[m.inventory_copy_id for m in matched],
                    expected_bundle_fmv=round(fmv, 2),
                    suggested_list_price=round(fmv * 0.9, 2),
                    signals=[f"Character focus ({ch})", "Personalized collector interest"],
                )
            )

    for pub in publishers:
        pub_items = [i for i in queue.items if pub in (i.publisher or "").lower() and i.issue_number in {"1", "1.0"}]
        if len(pub_items) >= 2:
            fmv = sum(m.fmv for m in pub_items)
            bundles.append(
                P78SellBundleRead(
                    bundle_key=f"publisher:{pub}:1",
                    bundle_type="PUBLISHER",
                    label=f"{pub.title()} #1 bundle",
                    item_count=len(pub_items),
                    inventory_copy_ids=[m.inventory_copy_id for m in pub_items],
                    expected_bundle_fmv=round(fmv, 2),
                    suggested_list_price=round(fmv * 0.88, 2),
                    signals=[f"Publisher focus ({pub})", "#1 launch candidates"],
                )
            )

    bundles.sort(key=lambda b: (-b.expected_bundle_fmv, b.label.lower()))
    return P78SellBundleListResponse(items=bundles[:40], total_items=len(bundles))
