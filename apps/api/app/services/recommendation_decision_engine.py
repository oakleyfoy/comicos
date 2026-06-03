"""Recommendation Decision Engine V1 — turn ranked recs into buy/watch/pass decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlmodel import Session, select

from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.purchase_variant import PurchaseVariantRecommendation
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.models.spec_intelligence import SpecRecommendation
from app.schemas.recommendation_decision import REASON_CODE_LABELS, RecommendationDecisionRead
from app.services.foc_dates import days_until_foc, utc_today
from app.services.recommendation_catalog_quality import build_forward_release_title_index
from app.services.recommendation_title_index import RecommendationPipelineIndexCache
from app.services.recommendation_forward_window import _key_signals_by_issue, _latest_spec_by_issue
from app.services.recommendation_intelligence_enrichment import build_collector_significance_enrichment
from app.services.recommendation_priority_enrichment import (
    KEY_SIGNAL_TYPES,
    NEW_ONE_SIGNALS,
    build_recommendation_priority_enrichment,
    build_owned_series_inventory_stats,
)

PURCHASE_TYPES = frozenset({"PREORDER", "ACQUIRE"})
ALLOWED_QUANTITIES = (1, 2, 3, 5)

SIGNAL_REASON_MAP: dict[str, str] = {
    "FIRST_APPEARANCE": "FIRST_APPEARANCE",
    "FIRST_FULL_APPEARANCE": "FIRST_APPEARANCE",
    "FIRST_CAMEO": "FIRST_APPEARANCE",
    "KEY_ISSUE": "KEY_ISSUE",
    "ORIGIN": "KEY_ISSUE",
    "MILESTONE_NUMBERING": "KEY_ISSUE",
    "RATIO_VARIANT": "RATIO_OPPORTUNITY",
    "INCENTIVE_VARIANT": "RATIO_OPPORTUNITY",
    "VARIANT_HOT": "SCARCITY",
    "NEW_NUMBER_ONE": "MARKET_DEMAND",
    "UNIVERSE_LAUNCH": "MEDIA_CATALYST",
    "RELAUNCH": "MEDIA_CATALYST",
}


@dataclass
class _RecommendationInput:
    kind: str
    title: str
    priority_score: float
    confidence_score: float
    rationale: str
    source_systems: list[str]
    estimated_value: float | None = None


@dataclass
class RecommendationDecisionContext:
    release_index: dict[str, tuple[ReleaseIssue, ReleaseSeries]]
    key_signals_by_issue: dict[int, list[str]]
    quantity_by_release: dict[int, PurchaseQuantityRecommendation]
    variant_recs_by_release: dict[int, list[PurchaseVariantRecommendation]]
    variants_by_issue: dict[int, list[ReleaseVariant]]
    spec_by_issue: dict[int, SpecRecommendation]
    owned_stats: object = field(default_factory=dict)


def build_recommendation_decision_context(
    session: Session,
    *,
    owner_user_id: int,
    index_cache: RecommendationPipelineIndexCache | None = None,
) -> RecommendationDecisionContext:
    cache = index_cache or RecommendationPipelineIndexCache(owner_user_id=owner_user_id)
    release_index = build_forward_release_title_index(
        session,
        owner_user_id=owner_user_id,
        pipeline_cache=cache,
    )
    issue_ids = [int(pair[0].id or 0) for pair in release_index.values() if pair[0].id is not None]
    key_signals = _key_signals_by_issue(session, issue_ids=issue_ids)

    qty_rows = session.exec(
        select(PurchaseQuantityRecommendation)
        .where(PurchaseQuantityRecommendation.owner_user_id == owner_user_id)
        .order_by(PurchaseQuantityRecommendation.created_at.desc(), PurchaseQuantityRecommendation.id.desc())
    ).all()
    quantity_by_release: dict[int, PurchaseQuantityRecommendation] = {}
    for row in qty_rows:
        rid = int(row.release_id)
        if rid not in quantity_by_release:
            quantity_by_release[rid] = row

    var_rows = session.exec(
        select(PurchaseVariantRecommendation)
        .where(PurchaseVariantRecommendation.owner_user_id == owner_user_id)
        .order_by(PurchaseVariantRecommendation.created_at.desc(), PurchaseVariantRecommendation.id.desc())
    ).all()
    variant_recs_by_release: dict[int, list[PurchaseVariantRecommendation]] = {}
    for row in var_rows:
        rid = int(row.release_id)
        bucket = variant_recs_by_release.setdefault(rid, [])
        if row.variant_id is not None and any(r.variant_id == row.variant_id for r in bucket):
            continue
        if row.variant_id is None and any(r.variant_id is None and r.cover_label == row.cover_label for r in bucket):
            continue
        bucket.append(row)

    variants_by_issue: dict[int, list[ReleaseVariant]] = {}
    if issue_ids:
        for variant in session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(issue_ids))).all():
            variants_by_issue.setdefault(int(variant.issue_id), []).append(variant)

    return RecommendationDecisionContext(
        release_index=release_index,
        key_signals_by_issue=key_signals,
        quantity_by_release=quantity_by_release,
        variant_recs_by_release=variant_recs_by_release,
        variants_by_issue=variants_by_issue,
        spec_by_issue=_latest_spec_by_issue(session, owner_user_id=owner_user_id),
        owned_stats=build_owned_series_inventory_stats(session, owner_user_id=owner_user_id),
    )


def _resolve_release(
    title: str,
    ctx: RecommendationDecisionContext,
) -> tuple[ReleaseIssue, ReleaseSeries] | None:
    key = title.strip().lower()
    if key.endswith(" (variants)"):
        key = key[: -len(" (variants)")]
    return ctx.release_index.get(key)


def _headline(action: str, quantity: int) -> str:
    if action == "BUY_AGGRESSIVE":
        return f"BUY {quantity} COPIES" if quantity > 1 else "BUY AGGRESSIVE"
    if action == "BUY":
        return f"BUY {quantity} COPIES" if quantity != 1 else "BUY 1 COPY"
    if action == "WATCH":
        return "WATCH"
    return "PASS"


def _pick_quantity(
    *,
    priority: float,
    confidence: float,
    action: str,
    release_id: int | None,
    ctx: RecommendationDecisionContext,
) -> int:
    if action in {"WATCH", "PASS"}:
        return 0
    if release_id is not None:
        qty_row = ctx.quantity_by_release.get(release_id)
        if qty_row is not None and int(qty_row.quantity_recommended) > 0:
            q = int(qty_row.quantity_recommended)
            if action == "BUY_AGGRESSIVE" and q < 5:
                for step in ALLOWED_QUANTITIES:
                    if step > q:
                        return step
            return q
    if priority >= 92.0 and confidence >= 0.82:
        base = 5
    elif priority >= 86.0 and confidence >= 0.75:
        base = 3
    elif priority >= 78.0:
        base = 2
    else:
        base = 1
    if action == "BUY_AGGRESSIVE":
        base = min(5, base + (2 if base < 3 else 1))
    return base


def _cover_labels(
    *,
    release_id: int | None,
    issue_id: int | None,
    ctx: RecommendationDecisionContext,
) -> list[str]:
    if release_id is None:
        return []
    labels: list[str] = []
    for rec in ctx.variant_recs_by_release.get(release_id, []):
        if rec.recommendation.strip().upper() not in {"BUY", "STRONG_BUY", "MUST_BUY"}:
            continue
        label = (rec.cover_label or "").strip()
        if label and label not in labels:
            labels.append(label)
    if labels:
        return labels[:4]
    if issue_id is None:
        return ["Cover A Recommended"] if release_id else []
    for variant in ctx.variants_by_issue.get(issue_id, []):
        if variant.ratio_value:
            label = f"1:{int(variant.ratio_value)}"
        else:
            name = (variant.variant_name or "Cover A").strip()
            label = name if name.lower().startswith("cover") else f"Cover {name}"
        if label not in labels:
            labels.append(label)
        if len(labels) >= 3:
            break
    if not labels:
        labels.append("Cover A Recommended")
    return labels


def _risk_tier(
    *,
    confidence: float,
    priority: float,
    has_high_ratio: bool,
    action: str,
) -> str:
    if action in {"PASS", "WATCH"}:
        return "LOW" if action == "PASS" else "MEDIUM"
    if has_high_ratio and confidence < 0.72:
        return "HIGH"
    if confidence >= 0.82 and priority >= 80.0 and not has_high_ratio:
        return "LOW"
    if confidence < 0.58 or priority < 62.0:
        return "HIGH"
    return "MEDIUM"


def _strategy_for(
    *,
    kind: str,
    quantity: int,
    signals: set[str],
    spec_type: str | None,
    owns_run: bool,
    action: str,
) -> str:
    if kind == "GRADE":
        return "GRADE_CANDIDATE"
    if kind in {"SELL", "REBALANCE"}:
        return "FLIP"
    if action in {"WATCH", "PASS"}:
        return "HOLD"
    if quantity >= 2 and (spec_type in {"STRONG_BUY", "BUY"} or "VARIANT_HOT" in signals):
        return "SELL_ONE_KEEP_ONE"
    if owns_run or signals.intersection(KEY_SIGNAL_TYPES - NEW_ONE_SIGNALS):
        return "LONG_TERM_HOLD"
    if spec_type in {"STRONG_BUY", "BUY"} or "NEW_NUMBER_ONE" in signals:
        return "FLIP"
    return "HOLD"


def _roi_range(*, strategy: str, action: str, priority: float) -> str:
    if action in {"WATCH", "PASS"}:
        return "Long-term hold" if strategy == "LONG_TERM_HOLD" else "Monitor"
    if strategy == "LONG_TERM_HOLD":
        return "Long-term hold"
    if strategy == "GRADE_CANDIDATE":
        return "1.5x–2.5x (graded)"
    if priority >= 88.0:
        return "2x–3x"
    if priority >= 75.0:
        return "1.2x–1.5x"
    return "1.1x–1.3x"


def _action_for(*, kind: str, priority: float, confidence: float) -> str:
    if kind in {"SELL", "REBALANCE"}:
        return "PASS"
    if kind == "GRADE":
        return "WATCH"
    if kind == "WATCH" or kind == "REVIEW":
        return "WATCH"
    if kind not in PURCHASE_TYPES:
        return "WATCH"
    if priority >= 86.0 and confidence >= 0.78:
        return "BUY_AGGRESSIVE"
    if priority >= 68.0 and confidence >= 0.58:
        return "BUY"
    if priority >= 52.0 or confidence >= 0.5:
        return "WATCH"
    return "PASS"


def compute_recommendation_decision(
    rec: _RecommendationInput,
    *,
    ctx: RecommendationDecisionContext,
    session: Session,
    owner_user_id: int,
) -> RecommendationDecisionRead:
    kind = rec.kind.strip().upper()
    pair = _resolve_release(rec.title, ctx)
    issue, series = pair if pair else (None, None)
    issue_id = int(issue.id) if issue and issue.id is not None else None
    release_id = issue_id
    signals_list = ctx.key_signals_by_issue.get(issue_id or -1, [])
    signal_set = {s.upper() for s in signals_list}
    spec = ctx.spec_by_issue.get(issue_id) if issue_id else None
    spec_type = spec.recommendation_type.strip().upper() if spec else None

    owns_run = False
    enrichment_rationale: tuple[str, ...] = ()
    priority_enrichment = None
    collector_intel = None
    if issue is not None and series is not None:
        series_key = (series.publisher or "").strip().lower(), (series.series_name or "").strip().lower()
        owned_in = ctx.owned_stats.copies_by_series.get(series_key, 0) if hasattr(ctx.owned_stats, "copies_by_series") else 0
        owns_run = owned_in > 0
        priority_enrichment = build_recommendation_priority_enrichment(
            session,
            owner_user_id=owner_user_id,
            series_name=series.series_name,
            issue_title=issue.title,
            publisher=series.publisher,
            key_signals=signals_list,
            v2_confidence=rec.confidence_score,
            spec_type=spec_type,
            owns_series_run=owns_run,
            owned_stats=ctx.owned_stats if hasattr(ctx.owned_stats, "copies_by_series") else None,
            scoring_ctx=None,
            issue_id=issue_id or 0,
            issue=issue,
            series=series,
        )
        enrichment_rationale = priority_enrichment.rationale_bits
        owns_run = owns_run or priority_enrichment.continuity_bonus >= 2.0
        variants = ctx.variants_by_issue.get(issue_id or -1, [])
        collector_intel = build_collector_significance_enrichment(
            session,
            series=series,
            issue=issue,
            variants=variants,
            rationale=rec.rationale,
            key_signals=signals_list,
            priority_enrichment=priority_enrichment,
            owned_stats=ctx.owned_stats if hasattr(ctx.owned_stats, "copies_by_series") else None,
        )

    decision_priority = rec.priority_score
    decision_confidence = rec.confidence_score
    if collector_intel is not None:
        decision_priority = min(94.0, rec.priority_score + collector_intel.decision_boost)
        decision_confidence = min(0.97, rec.confidence_score + collector_intel.confidence_boost)

    action = _action_for(kind=kind, priority=decision_priority, confidence=decision_confidence)
    quantity = _pick_quantity(
        priority=decision_priority,
        confidence=decision_confidence,
        action=action,
        release_id=release_id,
        ctx=ctx,
    )
    if action == "PASS":
        quantity = 0
    elif action == "WATCH" and kind in PURCHASE_TYPES:
        quantity = 0

    has_high_ratio = any(
        (v.ratio_value or 0) >= 25 for v in ctx.variants_by_issue.get(issue_id or -1, [])
    )
    covers = _cover_labels(release_id=release_id, issue_id=issue_id, ctx=ctx)
    strategy = _strategy_for(
        kind=kind,
        quantity=quantity,
        signals=signal_set,
        spec_type=spec_type,
        owns_run=owns_run,
        action=action,
    )
    risk = _risk_tier(
        confidence=decision_confidence,
        priority=decision_priority,
        has_high_ratio=has_high_ratio,
        action=action,
    )

    reason_codes: list[str] = []
    if collector_intel is not None:
        for code in collector_intel.reason_codes:
            if code not in reason_codes:
                reason_codes.append(code)
    for sig in signals_list:
        code = SIGNAL_REASON_MAP.get(sig.upper())
        if code and code not in reason_codes:
            reason_codes.append(code)
    if spec_type in {"STRONG_BUY", "BUY"}:
        reason_codes.append("SPEC_HEAT")
    if enrichment_rationale:
        if any("Franchise" in bit for bit in enrichment_rationale):
            reason_codes.append("FRANCHISE_STRENGTH")
        if any("continuity" in bit.lower() or "run" in bit.lower() for bit in enrichment_rationale):
            reason_codes.append("COLLECTOR_CONTINUITY")
        if any("demand" in bit.lower() for bit in enrichment_rationale):
            reason_codes.append("MARKET_DEMAND")
    if len(rec.source_systems) >= 2:
        reason_codes.append("MULTI_SOURCE")
    if issue and issue.foc_date is not None:
        foc_days = days_until_foc(issue.foc_date, today=utc_today())
        if foc_days is not None and foc_days <= 14:
            reason_codes.append("FOC_URGENCY")
    rationale_lower = rec.rationale.lower()
    if "media" in rationale_lower or "launch" in rationale_lower:
        if "MEDIA_CATALYST" not in reason_codes:
            reason_codes.append("MEDIA_CATALYST")
    if "creator" in rationale_lower or "heat" in rationale_lower:
        reason_codes.append("CREATOR_HEAT")
    if has_high_ratio and "RATIO_OPPORTUNITY" not in reason_codes:
        reason_codes.append("RATIO_OPPORTUNITY")

    reason_summary: list[str] = []
    if collector_intel is not None:
        for line in collector_intel.investment_thesis:
            if line not in reason_summary:
                reason_summary.append(line)
    for code in reason_codes:
        label = REASON_CODE_LABELS.get(code, code.replace("_", " ").title())
        if label not in reason_summary:
            reason_summary.append(label)
    for bit in enrichment_rationale:
        clean = bit.rstrip(".")
        if clean and clean not in reason_summary:
            reason_summary.append(clean)
    if not reason_summary and rec.rationale:
        reason_summary.append(rec.rationale[:160])

    foc_date = issue.foc_date if issue else None
    release_date = issue.release_date if issue else None

    return RecommendationDecisionRead(
        action=action,  # type: ignore[arg-type]
        quantity=quantity,
        cover_recommendations=covers,
        risk=risk,  # type: ignore[arg-type]
        strategy=strategy,  # type: ignore[arg-type]
        reason_codes=reason_codes,
        reason_summary=reason_summary[:8],
        expected_roi_range=_roi_range(strategy=strategy, action=action, priority=decision_priority),
        foc_date=foc_date,
        release_date=release_date,
        decision_headline=_headline(action, quantity if quantity else 1),
    )


def decision_for_cross_system(
    *,
    recommendation_type: str,
    title: str,
    priority_score: float,
    confidence_score: float,
    rationale: str,
    source_systems: list[str],
    estimated_value: float | None,
    session: Session,
    owner_user_id: int,
    ctx: RecommendationDecisionContext,
) -> RecommendationDecisionRead:
    return compute_recommendation_decision(
        _RecommendationInput(
            kind=recommendation_type,
            title=title,
            priority_score=priority_score,
            confidence_score=confidence_score,
            rationale=rationale,
            source_systems=source_systems,
            estimated_value=estimated_value,
        ),
        ctx=ctx,
        session=session,
        owner_user_id=owner_user_id,
    )


def decision_for_daily_action(
    *,
    action_type: str,
    title: str,
    priority_score: float,
    confidence_score: float,
    rationale: str,
    source_systems: list[str],
    session: Session,
    owner_user_id: int,
    ctx: RecommendationDecisionContext,
) -> RecommendationDecisionRead:
    return compute_recommendation_decision(
        _RecommendationInput(
            kind=action_type,
            title=title,
            priority_score=priority_score,
            confidence_score=confidence_score,
            rationale=rationale,
            source_systems=source_systems,
        ),
        ctx=ctx,
        session=session,
        owner_user_id=owner_user_id,
    )
