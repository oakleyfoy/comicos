"""P78-01 sell candidate queue (P54/P56/P68/P70/P77 workflow layer)."""

from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models.p78_sell_workflow import P78ListingDraft
from app.schemas.p78_sell_workflow import P78SellQueueItemRead, P78SellQueueListResponse
from app.services.exit_recommendation_service import (
    build_exit_recommendation_snapshot,
    get_latest_exit_recommendation_snapshot,
    list_exit_recommendation_items,
)
from app.services.p71_sell_context import SellIntelCopyContext, load_sell_intel_contexts
from app.models.sell_intelligence_platform import EXIT_GRADE_THEN_SELL, EXIT_SELL_NOW, EXIT_TRIM, EXIT_WATCH
from app.services.p71_sell_scoring import score_exit, score_listing
from app.services.p77_personalization_engine import load_personalization_context
from app.services.sell_candidates import generate_sell_candidate_recommendations, list_latest_sell_candidate_recommendations


def _title_key(ctx: SellIntelCopyContext) -> str:
    return f"{ctx.publisher}|{ctx.title}".strip().lower()


def _priority_for(
    *,
    exit_action: str,
    exit_score: float,
    excess_copies: int,
    timing: str,
    gain_pct: float,
) -> str:
    if exit_action in {EXIT_SELL_NOW, EXIT_TRIM} or excess_copies >= 2 or exit_score >= 58:
        return "HIGH"
    if timing == "SELL_NOW" or gain_pct >= 35 or exit_score >= 42:
        return "HIGH"
    if exit_action in {EXIT_WATCH, EXIT_GRADE_THEN_SELL} or timing == "SELL_SOON" or exit_score >= 30:
        return "MEDIUM"
    if gain_pct >= 12 or excess_copies >= 1:
        return "MEDIUM"
    return "WATCH"


def _signals_for(
    ctx: SellIntelCopyContext,
    *,
    owned: int,
    target_hold: int,
    excess: int,
    exit_action: str,
    primary: str,
) -> list[str]:
    signals: list[str] = []
    if excess > 0:
        signals.append(f"Duplicate ownership ({owned} owned, target hold {target_hold})")
    if ctx.unrealized_gain_pct >= 20:
        signals.append(f"Strong appreciation ({ctx.unrealized_gain_pct:.0f}% vs cost)")
    if ctx.market_liquidity_score >= 55 or ctx.liquidity_score >= 55:
        signals.append("High liquidity market")
    if ctx.market_timing_signal in {"SELL_NOW", "SELL_SOON"}:
        signals.append(f"Market timing: {ctx.market_timing_signal}")
    if exit_action and exit_action not in {"HOLD"}:
        signals.append(f"Exit intelligence: {exit_action.replace('_', ' ').lower()}")
    if primary:
        signals.append(primary.replace("_", " "))
    if ctx.price_trend == "FALLING":
        signals.append("Declining momentum")
    return signals[:6]


def _draft_by_copy(session: Session, *, owner_user_id: int) -> dict[int, int]:
    rows = session.exec(
        select(P78ListingDraft)
        .where(P78ListingDraft.owner_user_id == owner_user_id)
        .where(P78ListingDraft.status != "ARCHIVED")
        .order_by(P78ListingDraft.updated_at.desc(), P78ListingDraft.id.desc())
    ).all()
    out: dict[int, int] = {}
    for row in rows:
        cid = row.inventory_copy_id
        if cid and cid not in out:
            out[int(cid)] = int(row.id or 0)
    return out


def build_sell_queue(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
    refresh_upstream: bool = True,
) -> P78SellQueueListResponse:
    if refresh_upstream:
        try:
            generate_sell_candidate_recommendations(session, owner_user_id=owner_user_id)
        except Exception:  # pragma: no cover
            pass
        try:
            if get_latest_exit_recommendation_snapshot(session, owner_user_id=owner_user_id) is None:
                build_exit_recommendation_snapshot(session, owner_user_id=owner_user_id)
        except Exception:  # pragma: no cover
            pass

    ctx_list = load_sell_intel_contexts(session, owner_user_id=owner_user_id)
    p77 = load_personalization_context(session, owner_user_id=owner_user_id)
    target_hold = max(1, int(p77.profile.default_copy_count))
    hold_pref = (p77.profile.hold_preference or "MIXED").upper()
    if hold_pref == "LONG_TERM":
        target_hold = max(target_hold, target_hold + 1)

    by_title: dict[str, list[SellIntelCopyContext]] = defaultdict(list)
    for ctx in ctx_list:
        by_title[_title_key(ctx)].append(ctx)

    exit_by_copy: dict[int, object] = {}
    snap = get_latest_exit_recommendation_snapshot(session, owner_user_id=owner_user_id)
    if snap:
        for ex in list_exit_recommendation_items(session, snapshot_id=int(snap.id or 0)):
            exit_by_copy[int(ex.inventory_copy_id)] = ex

    sell_cand_ids: set[int] = set()
    try:
        sell_cands, _ = list_latest_sell_candidate_recommendations(session, owner_user_id=owner_user_id, limit=200, offset=0)
        sell_cand_ids = {r.inventory_item_id for r in sell_cands if r.recommendation in {"SELL", "TRIM", "LIST"}}
    except Exception:  # pragma: no cover
        sell_cand_ids = set()

    draft_map = _draft_by_copy(session, owner_user_id=owner_user_id)
    items: list[P78SellQueueItemRead] = []

    for ctx in ctx_list:
        if ctx.estimated_fmv <= 0 and ctx.cost_basis <= 0:
            continue
        key = _title_key(ctx)
        siblings = by_title[key]
        owned = len(siblings)
        excess = max(0, owned - target_hold)
        sorted_siblings = sorted(siblings, key=lambda c: c.copy_id, reverse=True)
        rank = next((i for i, c in enumerate(sorted_siblings) if c.copy_id == ctx.copy_id), 0)
        copy_excess = 1 if excess > 0 and rank < excess else 0
        suggested_qty = copy_excess if copy_excess else (1 if ctx.copy_id in sell_cand_ids else 0)

        action, escore, _, primary, _, _ = score_exit(ctx)
        ex_row = exit_by_copy.get(ctx.copy_id)
        if ex_row is not None:
            escore = max(escore, float(getattr(ex_row, "exit_score", 0) or 0))
            if getattr(ex_row, "recommendation", None):
                action = str(ex_row.recommendation)

        _, _, _, _, _, _, days, _, _ = score_listing(ctx)
        priority = _priority_for(
            exit_action=action,
            exit_score=escore,
            excess_copies=excess,
            timing=ctx.market_timing_signal,
            gain_pct=ctx.unrealized_gain_pct,
        )
        signals = _signals_for(
            ctx,
            owned=owned,
            target_hold=target_hold,
            excess=excess,
            exit_action=action,
            primary=primary,
        )

        include = (
            priority in {"HIGH", "MEDIUM"}
            or excess > 0
            or ctx.copy_id in sell_cand_ids
            or escore >= 28
            or ctx.unrealized_gain_pct >= 15
        )
        if not include:
            continue
        if suggested_qty == 0 and priority == "WATCH" and escore < 35:
            suggested_qty = 0
        elif suggested_qty == 0 and priority != "WATCH":
            suggested_qty = 1

        items.append(
            P78SellQueueItemRead(
                inventory_copy_id=ctx.copy_id,
                title=ctx.title,
                publisher=ctx.publisher,
                issue_number=ctx.issue_number,
                priority=priority,  # type: ignore[arg-type]
                owned_copies=owned,
                target_hold_copies=target_hold,
                suggested_sell_quantity=max(suggested_qty, 0) or (1 if priority == "HIGH" else 0),
                fmv=round(ctx.estimated_fmv, 2),
                cost_basis=round(ctx.cost_basis, 2),
                liquidity_score=round(ctx.market_liquidity_score or ctx.liquidity_score, 1),
                average_sale_days=round(days, 1) if days else None,
                signals=signals,
                listing_draft_id=draft_map.get(ctx.copy_id),
                exit_score=round(escore, 1),
            )
        )

    order = {"HIGH": 0, "MEDIUM": 1, "WATCH": 2}
    items.sort(key=lambda r: (order.get(r.priority, 9), -(r.exit_score or 0), -r.fmv, r.title.lower()))
    high = sum(1 for i in items if i.priority == "HIGH")
    med = sum(1 for i in items if i.priority == "MEDIUM")
    watch = sum(1 for i in items if i.priority == "WATCH")
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    page = items[off : off + lim]
    return P78SellQueueListResponse(
        items=page,
        total_items=len(items),
        limit=lim,
        offset=off,
        high_priority_count=high,
        medium_priority_count=med,
        watch_count=watch,
    )
