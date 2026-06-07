from __future__ import annotations

from app.services.sell_candidate_reason_service import build_reason_summary


def test_sell_now_reasons() -> None:
    summary, reasons = build_reason_summary(
        recommendation="SELL_NOW",
        profit=40.0,
        cost=10.0,
        confidence="HIGH",
        duplicate_count=3,
        concentration=0.2,
        grade_first_signal=False,
        hold_sell_signal="SELL",
    )
    assert summary
    assert any("FMV" in r or "profit" in r.lower() for r in reasons)
    assert "Recommendation confidence high" in reasons


def test_hold_reasons() -> None:
    _, reasons = build_reason_summary(
        recommendation="HOLD",
        profit=-2.0,
        cost=10.0,
        confidence="MEDIUM",
        duplicate_count=1,
        concentration=0.05,
        grade_first_signal=False,
        hold_sell_signal="HOLD",
    )
    assert "Long-term collector significance" in reasons
    assert any("Limited" in r or "Appreciation" in r for r in reasons)


def test_grade_first_reasons() -> None:
    _, reasons = build_reason_summary(
        recommendation="GRADE_FIRST",
        profit=20.0,
        cost=15.0,
        confidence="MEDIUM",
        duplicate_count=1,
        concentration=0.1,
        grade_first_signal=True,
        hold_sell_signal=None,
    )
    assert "High-value raw book" in reasons
    assert "Grading may increase realized value" in reasons
