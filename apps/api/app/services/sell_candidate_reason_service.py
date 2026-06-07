"""P89-01 rule-based sell candidate reason copy."""

from __future__ import annotations


def build_reason_summary(
    *,
    recommendation: str,
    profit: float,
    cost: float,
    confidence: str,
    duplicate_count: int,
    concentration: float,
    grade_first_signal: bool,
    hold_sell_signal: str | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    profit_ratio = (profit / cost) if cost > 0 else 0.0

    if recommendation == "SELL_NOW":
        if profit > 0 and cost > 0 and profit_ratio >= 0.5:
            reasons.append("FMV significantly exceeds cost basis")
        elif profit > 0:
            reasons.append("Positive unrealized profit")
        if duplicate_count >= 3:
            reasons.append("Strong profit opportunity on excess copy")
        elif duplicate_count >= 2:
            reasons.append("Duplicate copy may be trimmed")
        if concentration >= 0.15:
            reasons.append("Portfolio concentration suggests trimming")
        if not reasons:
            reasons.append("Sell score leads other exit paths")
        if confidence == "HIGH":
            reasons.append("Recommendation confidence high")
    elif recommendation == "HOLD":
        reasons.append("Long-term collector significance")
        if profit <= 0:
            reasons.append("Limited realized upside at current FMV")
        else:
            reasons.append("Appreciation potential remains")
        if hold_sell_signal == "HOLD":
            reasons.append("Hold/sell signals align on retention")
    elif recommendation == "GRADE_FIRST":
        reasons.append("High-value raw book")
        reasons.append("Grading may increase realized value")
        if grade_first_signal:
            reasons.append("Grade candidate signals are strong")
    else:
        reasons.append("Mixed signals; monitor before acting")
        if confidence == "LOW":
            reasons.append("Data quality limits conviction")

    summary = " · ".join(reasons[:4])
    return summary, reasons[:6]
