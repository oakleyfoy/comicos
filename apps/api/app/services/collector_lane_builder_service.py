"""P64 deterministic lane builders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.models.collector_assistant import (
    COLLECTOR_LANES,
    LANE_ACQUIRE,
    LANE_BUY,
    LANE_GRADE,
    LANE_HOLD,
    LANE_SELL,
    LANE_WATCH,
)
from app.models.market_intelligence_platform import SELL_ACTION_GRADE_FIRST, SELL_ACTION_HOLD
from app.services.collector_assistant_context_service import CollectorAssistantContext


@dataclass
class LaneItemDraft:
    lane: str
    priority_score: float
    confidence: str
    title: str
    publisher: str
    issue_number: str
    release_issue_id: int | None
    external_catalog_issue_id: int | None
    inventory_copy_id: int | None
    recommended_action: str
    reason_codes: list[str]
    explanation: str
    provenance_json: dict


def _conf(score: float) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def build_lane_drafts(ctx: CollectorAssistantContext) -> dict[str, list[LaneItemDraft]]:
    lanes: dict[str, list[LaneItemDraft]] = {lane: [] for lane in COLLECTOR_LANES}

    for row in ctx.buy_queue_items:
        lanes[LANE_BUY].append(
            LaneItemDraft(
                lane=LANE_BUY,
                priority_score=float(getattr(row, "priority_score", 50) or 50),
                confidence=_conf(float(getattr(row, "priority_score", 50) or 50)),
                title=row.title,
                publisher=row.publisher or "",
                issue_number=row.issue_number or "",
                release_issue_id=int(row.release_issue_id) if row.release_issue_id else None,
                external_catalog_issue_id=int(row.external_catalog_issue_id) if row.external_catalog_issue_id else None,
                inventory_copy_id=None,
                recommended_action=str(getattr(row, "status", "BUY") or "BUY"),
                reason_codes=["p62_buy_queue"],
                explanation=row.buy_reason or "Buy queue recommendation",
                provenance_json={"p62_buy_queue_item_id": int(row.id or 0)},
            )
        )

    for row in ctx.foc_items:
        if float(row.urgency_score) >= 70:
            target = LANE_BUY
            action = "PREORDER"
            codes = ["p62_foc", "foc_urgent"]
        else:
            target = LANE_WATCH
            action = "WATCH_FOC"
            codes = ["p62_foc", "foc_watch"]
        lanes[target].append(
            LaneItemDraft(
                lane=target,
                priority_score=float(row.urgency_score),
                confidence=_conf(float(row.urgency_score)),
                title=row.title,
                publisher=row.publisher,
                issue_number="",
                release_issue_id=int(row.release_issue_id),
                external_catalog_issue_id=None,
                inventory_copy_id=None,
                recommended_action=action,
                reason_codes=codes,
                explanation=row.alert_reason or "FOC window",
                provenance_json={"p62_foc_alert_item_id": int(row.id or 0)},
            )
        )

    for row in ctx.sell_items:
        if row.recommended_action == SELL_ACTION_GRADE_FIRST:
            lane = LANE_GRADE
            codes = ["p63_grade_first"]
        elif row.recommended_action == SELL_ACTION_HOLD:
            lane = LANE_HOLD
            codes = ["p63_hold"]
        else:
            lane = LANE_SELL
            codes = ["p63_sell_signal"]
        lanes[lane].append(
            LaneItemDraft(
                lane=lane,
                priority_score=float(row.sell_score if lane == LANE_SELL else row.hold_score),
                confidence=row.confidence,
                title=row.title,
                publisher=row.publisher,
                issue_number=row.issue_number,
                release_issue_id=None,
                external_catalog_issue_id=int(row.external_catalog_issue_id) if row.external_catalog_issue_id else None,
                inventory_copy_id=int(row.inventory_copy_id),
                recommended_action=row.recommended_action,
                reason_codes=codes,
                explanation=row.sell_reason or row.recommended_action,
                provenance_json={"p63_sell_signal_item_id": int(row.id or 0)},
            )
        )

    for row in ctx.acquisition_items:
        action = row.action
        lane = LANE_ACQUIRE if action in ("BUY_NOW", "ADD_TO_WANT_LIST") else LANE_WATCH
        lanes[lane].append(
            LaneItemDraft(
                lane=lane,
                priority_score=float(row.opportunity_score),
                confidence=_conf(float(row.opportunity_score)),
                title=row.title,
                publisher=row.publisher,
                issue_number=row.issue_number,
                release_issue_id=int(row.release_issue_id) if row.release_issue_id else None,
                external_catalog_issue_id=int(row.external_catalog_issue_id) if row.external_catalog_issue_id else None,
                inventory_copy_id=None,
                recommended_action=action,
                reason_codes=["p63_acquisition", row.reason or "opportunity"],
                explanation=row.reason or "Acquisition opportunity",
                provenance_json={"p63_acquisition_item_id": int(row.id or 0)},
            )
        )

    for row in ctx.pull_forecast_items:
        score = 62.0 if row.confidence == "HIGH" else 55.0 if row.confidence == "MEDIUM" else 45.0
        lanes[LANE_HOLD].append(
            LaneItemDraft(
                lane=LANE_HOLD,
                priority_score=score,
                confidence=row.confidence,
                title=row.title,
                publisher="",
                issue_number="",
                release_issue_id=int(row.release_issue_id) if row.release_issue_id else None,
                external_catalog_issue_id=None,
                inventory_copy_id=None,
                recommended_action="CONTINUE_PULL",
                reason_codes=["p62_pull_forecast"],
                explanation=row.explanation or "Pull forecast",
                provenance_json={"p62_pull_forecast_item_id": int(row.id or 0)},
            )
        )

    for row in ctx.watchlist_items:
        lanes[LANE_WATCH].append(
            LaneItemDraft(
                lane=LANE_WATCH,
                priority_score=58.0,
                confidence="MEDIUM",
                title=row.title,
                publisher="",
                issue_number="",
                release_issue_id=int(row.release_issue_id) if row.release_issue_id else None,
                external_catalog_issue_id=None,
                inventory_copy_id=None,
                recommended_action="WATCH",
                reason_codes=["p62_auto_watchlist"],
                explanation=row.inclusion_reason or "Auto watchlist",
                provenance_json={"p62_auto_watchlist_item_id": int(row.id or 0)},
            )
        )

    for row in ctx.market_signal_items:
        if row.signal_type in ("RISING_DEMAND", "SPEC_OPPORTUNITY"):
            lanes[LANE_WATCH].append(
                LaneItemDraft(
                    lane=LANE_WATCH,
                    priority_score=float(row.market_score),
                    confidence=row.confidence,
                    title=row.title,
                    publisher=row.publisher,
                    issue_number=row.issue_number,
                    release_issue_id=None,
                    external_catalog_issue_id=int(row.external_catalog_issue_id) if row.external_catalog_issue_id else None,
                    inventory_copy_id=int(row.inventory_copy_id) if row.inventory_copy_id else None,
                    recommended_action="WATCH",
                    reason_codes=["p63_market_signal", row.signal_type.lower()],
                    explanation=row.signal_reason,
                    provenance_json={"p63_market_signal_item_id": int(row.id or 0)},
                )
            )

    for lane in COLLECTOR_LANES:
        lanes[lane].sort(key=lambda d: (-d.priority_score, d.title))
    return lanes


def build_briefing_json(
    ctx: CollectorAssistantContext,
    *,
    run_id: int,
    lane_snapshot_ids: dict[str, int],
    health_id: int | None,
) -> dict:
    week_start = date.today()
    days_ahead = (2 - week_start.weekday()) % 7
    if days_ahead:
        week_start = week_start + timedelta(days=days_ahead)

    gain = ctx.portfolio_header.get("total_unrealized_gain_pct")
    headline_parts = []
    if ctx.foc_items:
        headline_parts.append(f"{len(ctx.foc_items)} FOC items")
    if ctx.sell_items:
        headline_parts.append(f"{sum(1 for s in ctx.sell_items if s.recommended_action in ('SELL_NOW', 'CONSIDER_SELLING'))} sell signals")
    if gain is not None:
        headline_parts.append(f"portfolio {gain:+.1f}% unrealized")
    headline = "; ".join(headline_parts) if headline_parts else "Collector assistant briefing"

    return {
        "week_start": week_start.isoformat(),
        "headline": headline,
        "run_id": run_id,
        "readiness": ctx.readiness_reason,
        "sections": [
            {"id": "buy", "title": "Buy / preorder", "lane_snapshot_id": lane_snapshot_ids.get(LANE_BUY)},
            {"id": "sell", "title": "Sell", "lane_snapshot_id": lane_snapshot_ids.get(LANE_SELL)},
            {"id": "portfolio", "title": "Portfolio health", "health_snapshot_id": health_id},
        ],
        "freshness": ctx.freshness,
    }


def build_health_from_context(ctx: CollectorAssistantContext) -> tuple[float, str, dict, list]:
    if not ctx.portfolio_header:
        return 50.0, "FAIR", {"inventory_count": ctx.inventory_count}, ["no_portfolio_snapshot"]
    gain_pct = float(ctx.portfolio_header.get("total_unrealized_gain_pct", 0))
    score = 55.0
    if gain_pct >= 15:
        score += 20
    elif gain_pct >= 5:
        score += 10
    elif gain_pct <= -10:
        score -= 15
    score = max(0.0, min(100.0, score))
    if score >= 80:
        band = "EXCELLENT"
    elif score >= 65:
        band = "GOOD"
    elif score >= 45:
        band = "FAIR"
    else:
        band = "AT_RISK"
    metrics = {
        "inventory_count": ctx.inventory_count,
        "portfolio_items": ctx.portfolio_header.get("total_items", 0),
        "total_unrealized_gain_pct": gain_pct,
    }
    risks: list = []
    if gain_pct <= -10:
        risks.append("portfolio_drawdown")
    return score, band, metrics, risks


def build_alert_drafts(ctx: CollectorAssistantContext) -> list[dict]:
    alerts: list[dict] = []
    now = datetime.now(timezone.utc)
    for row in ctx.foc_items:
        if float(row.urgency_score) < 75:
            continue
        days = 7
        if row.foc_date:
            days = (row.foc_date - date.today()).days
        sev = "CRITICAL" if days <= 3 else "HIGH"
        alerts.append(
            {
                "alert_type": "FOC_DEADLINE",
                "severity": sev,
                "title": row.title,
                "message": f"FOC in {days}d — {row.alert_reason}",
                "expires_at": (now + timedelta(days=max(days, 1))).isoformat(),
                "action_deep_link": "/recommendation-intelligence/foc/alerts",
                "provenance_json": {"p62_foc_alert_item_id": int(row.id or 0)},
            }
        )
    for row in ctx.sell_items:
        if row.recommended_action not in ("SELL_NOW", "CONSIDER_SELLING"):
            continue
        alerts.append(
            {
                "alert_type": "SELL_WINDOW",
                "severity": "HIGH" if row.recommended_action == "SELL_NOW" else "MEDIUM",
                "title": row.title,
                "message": row.sell_reason[:200],
                "expires_at": (now + timedelta(days=14)).isoformat(),
                "action_deep_link": "/market-intelligence/sell-signals/latest",
                "provenance_json": {"p63_sell_signal_item_id": int(row.id or 0)},
            }
        )
    alerts.sort(key=lambda a: (0 if a["severity"] == "CRITICAL" else 1, a["title"]))
    return alerts
