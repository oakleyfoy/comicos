from __future__ import annotations

from app.models.recommendation_v2 import RecommendationDecisionV2
from app.services.recommendation_v2_components import IssueComponentBundle, ScoreComponentResult


def _top_components(components: list[ScoreComponentResult], *, limit: int = 4) -> list[ScoreComponentResult]:
    positive = [c for c in components if c.component_name != "RISK_SCORE"]
    return sorted(positive, key=lambda c: c.component_score * c.component_weight, reverse=True)[:limit]


def build_recommendation_decision(
    *,
    bundle: IssueComponentBundle,
    series_name: str,
    issue_number: str,
    publisher: str,
) -> RecommendationDecisionV2:
    tier = bundle.recommendation_tier
    tops = _top_components(bundle.components)
    reason_bits = [f"{c.component_name.replace('_', ' ').title()}: {c.explanation or f'{c.component_score:.0f}'}" for c in tops]
    primary = reason_bits[0] if reason_bits else f"{tier} advisory for {series_name} #{issue_number}"

    risk_comp = next((c for c in bundle.components if c.component_name == "RISK_SCORE"), None)
    risk_note = risk_comp.explanation if risk_comp and risk_comp.component_score >= 50 else "Moderate collector risk; verify demand before buying."

    if tier == "MUST_BUY":
        summary = f"MUST BUY — {series_name} #{issue_number} ({publisher})"
        action = "Buy Cover A; add ratio variant if affordable."
        qty = 2 if bundle.recommendation_type == "INVESTMENT_NUMBER_ONE" else 1
    elif tier == "STRONG_BUY":
        summary = f"STRONG BUY — {series_name} #{issue_number}"
        action = "Buy primary cover; consider second copy for investment #1 types."
        qty = 2 if bundle.recommendation_type in {"INVESTMENT_NUMBER_ONE", "START_RUN"} else 1
    elif tier == "BUY":
        summary = f"BUY — {series_name} #{issue_number}"
        action = "Buy Cover A for collection or spec."
        qty = 1
    elif tier == "WATCH":
        summary = f"WATCH — {series_name} #{issue_number}"
        action = "Monitor FOC; buy only if market or key issue signals strengthen."
        qty = 0
        risk_note = "New #1 with variants but weak franchise demand and limited key issue signal."
    else:
        summary = f"PASS — {series_name} #{issue_number}"
        action = "Skip unless personal preference overrides."
        qty = 0
        risk_note = "Low-demand property, weak market/user fit."

    if bundle.recommendation_type == "START_RUN" and tier in {"MUST_BUY", "STRONG_BUY", "BUY"}:
        action = "Start run: buy Cover A; add second copy if investment + collection score both strong."

    return RecommendationDecisionV2(
        recommendation_score_id=0,
        decision_summary=summary,
        primary_reason="; ".join(reason_bits[:3]) or primary,
        risk_note=risk_note,
        suggested_action=action,
        suggested_quantity=qty,
    )
