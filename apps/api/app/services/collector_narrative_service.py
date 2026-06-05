"""P65-02 Collector narratives — deterministic guidance citing upstream signals."""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.collector_assistant import RUN_STATUS_SUCCESS
from app.models.collector_experience import CollectorNarrativeItem, CollectorNarrativeSnapshot, utc_now
from app.services.collector_assistant_context_service import load_collector_assistant_context
from app.services.collector_assistant_orchestrator import get_latest_briefing, get_latest_run, list_all_recommendations_for_run
from app.services.p65_feature_flags import p65_llm_narration_enabled

KIND_WEEKLY = "WEEKLY_BRIEFING"
KIND_BUY = "BUY_NARRATIVE"
KIND_SELL = "SELL_NARRATIVE"
KIND_GRADE = "GRADE_NARRATIVE"
KIND_ACQUIRE = "ACQUIRE_NARRATIVE"
KIND_WATCH = "WATCH_NARRATIVE"

READINESS_SUCCESS = "SUCCESS"
READINESS_NOT_READY = "NOT_READY"


def get_latest_narrative_snapshot(session: Session, *, owner_user_id: int) -> CollectorNarrativeSnapshot | None:
    return session.exec(
        select(CollectorNarrativeSnapshot)
        .where(CollectorNarrativeSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectorNarrativeSnapshot.generated_at.desc(), CollectorNarrativeSnapshot.id.desc())
    ).first()


def list_narrative_items(session: Session, *, snapshot_id: int) -> list[CollectorNarrativeItem]:
    return list(
        session.exec(
            select(CollectorNarrativeItem)
            .where(CollectorNarrativeItem.snapshot_id == snapshot_id)
            .order_by(CollectorNarrativeItem.narrative_kind.asc(), CollectorNarrativeItem.id.asc())
        ).all()
    )


def _week_start() -> str:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def _buy_narrative(ctx, row) -> tuple[str, list]:
    title = str(getattr(row, "title", "") or "This title")
    tier = getattr(row, "spec_tier", None) or getattr(row, "tier", None)
    velocity = getattr(row, "demand_velocity_pct", None) or getattr(row, "velocity_change_pct", None)
    citations: list[dict] = [{"signal": "buy_queue_item_id", "value": int(getattr(row, "id", 0) or 0)}]
    parts = [f"{title} appears in Buy Queue"]
    if velocity is not None:
        parts.append(f"because demand velocity changed {float(velocity):.0f}%")
        citations.append({"signal": "demand_velocity_pct", "value": float(velocity)})
    if tier:
        parts.append(f"spec score is Tier {tier}")
        citations.append({"signal": "spec_tier", "value": str(tier)})
    rank = getattr(row, "rank", None) or getattr(row, "opportunity_rank", None)
    if rank is not None and int(rank) <= 10:
        parts.append("and it entered the Top 10 opportunities")
        citations.append({"signal": "opportunity_rank", "value": int(rank)})
    text = ", ".join(parts) + "."
    return text, citations


def _sell_narrative(row) -> tuple[str, list]:
    title = str(getattr(row, "title", "") or "This title")
    reason = str(getattr(row, "reason", "") or "sell signal criteria met")
    citations = [
        {"signal": "sell_signal_item_id", "value": int(getattr(row, "id", 0) or 0)},
        {"signal": "reason", "value": reason},
    ]
    qty = getattr(row, "owned_quantity", None) or getattr(row, "quantity", None)
    extra = f" and exceeds your target quantity ({qty})." if qty else "."
    text = f"{title} shows a sell signal: {reason}{extra}"
    return text, citations


def _lane_narrative(kind: str, row) -> tuple[str, list]:
    citations = [
        {"signal": "collector_recommendation_item_id", "value": int(row.id or 0)},
        {"signal": "lane", "value": row.lane},
        {"signal": "reason_codes", "value": list(row.reason_codes_json or [])},
    ]
    text = row.explanation or f"{row.title}: {row.recommended_action or 'review'}."
    if row.reason_codes_json:
        text += f" Signals: {', '.join(row.reason_codes_json)}."
    return text, citations


def build_collector_narratives(session: Session, *, owner_user_id: int) -> CollectorNarrativeSnapshot:
    ctx = load_collector_assistant_context(session, owner_user_id=owner_user_id)
    briefing = get_latest_briefing(session, owner_user_id=owner_user_id)
    headline = ""
    if briefing:
        headline = str((briefing.briefing_json or {}).get("headline", ""))

    snap = CollectorNarrativeSnapshot(
        owner_user_id=owner_user_id,
        week_start=_week_start(),
        readiness_status=READINESS_SUCCESS if ctx.ready else READINESS_NOT_READY,
        briefing_markdown=f"# Weekly Briefing\n\n{headline}\n" if headline else "# Weekly Briefing\n\nNo P64 briefing yet.\n",
        metadata_json={"fingerprint": ctx.fingerprint, "llm_enhanced": False},
    )
    session.add(snap)
    session.flush()

    session.add(
        CollectorNarrativeItem(
            snapshot_id=int(snap.id or 0),
            owner_user_id=owner_user_id,
            narrative_kind=KIND_WEEKLY,
            title="Weekly Briefing",
            narrative_text=headline or "Build P64 collector assistant for a full weekly briefing.",
            signal_citations_json=[{"signal": "p64_briefing", "value": int(briefing.id or 0) if briefing else 0}],
            provenance_json={"freshness": ctx.freshness},
        )
    )

    for row in ctx.buy_queue_items[:12]:
        text, cites = _buy_narrative(ctx, row)
        session.add(
            CollectorNarrativeItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                narrative_kind=KIND_BUY,
                title=str(getattr(row, "title", "") or "Buy"),
                narrative_text=text,
                signal_citations_json=cites,
                provenance_json={"source": "BUY_QUEUE"},
            )
        )

    for row in ctx.sell_items[:12]:
        text, cites = _sell_narrative(row)
        session.add(
            CollectorNarrativeItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                narrative_kind=KIND_SELL,
                title=str(getattr(row, "title", "") or "Sell"),
                narrative_text=text,
                signal_citations_json=cites,
                provenance_json={"source": "SELL_SIGNAL"},
            )
        )

    run = get_latest_run(session, owner_user_id=owner_user_id)
    if run and run.status == RUN_STATUS_SUCCESS:
        lanes = list_all_recommendations_for_run(session, run_id=int(run.id or 0))
        lane_kind = {
            "buy": KIND_BUY,
            "sell": KIND_SELL,
            "grade": KIND_GRADE,
            "acquire": KIND_ACQUIRE,
            "watch": KIND_WATCH,
        }
        for lane, items in lanes.items():
            kind = lane_kind.get(lane)
            if not kind:
                continue
            for row in items[:6]:
                text, cites = _lane_narrative(kind, row)
                session.add(
                    CollectorNarrativeItem(
                        snapshot_id=int(snap.id or 0),
                        owner_user_id=owner_user_id,
                        narrative_kind=kind,
                        title=row.title,
                        narrative_text=text,
                        signal_citations_json=cites,
                        provenance_json=row.provenance_json or {},
                    )
                )

    if p65_llm_narration_enabled():
        snap.metadata_json = {**(snap.metadata_json or {}), "llm_enhanced": False, "llm_skipped": "no_key_or_stub"}

    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
