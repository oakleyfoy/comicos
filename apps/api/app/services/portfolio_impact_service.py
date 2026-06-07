"""P90-03 portfolio impact estimates from advisor actions."""

from __future__ import annotations

from typing import Any


def compute_portfolio_impact(
    *,
    buy_actions: list[dict[str, Any]],
    sell_actions: list[dict[str, Any]],
    grade_actions: list[dict[str, Any]],
) -> dict[str, float]:
    potential_profit = sum(float(a.get("profit_potential") or 0.0) for a in sell_actions)
    potential_savings = sum(float(a.get("potential_upside") or 0.0) for a in buy_actions)
    potential_value_gain = sum(float(a.get("value_increase") or 0.0) for a in grade_actions)
    portfolio_impact_total = potential_profit + potential_savings + potential_value_gain
    portfolio_score = min(100.0, round(20.0 + portfolio_impact_total / 10.0 + len(buy_actions) * 2 + len(sell_actions) * 2, 2))
    return {
        "potential_profit": round(potential_profit, 2),
        "potential_savings": round(potential_savings, 2),
        "potential_value_gain": round(potential_value_gain, 2),
        "portfolio_impact_total": round(portfolio_impact_total, 2),
        "portfolio_score": portfolio_score,
        "estimated_profit": round(potential_profit, 2),
        "estimated_savings": round(potential_savings, 2),
    }
