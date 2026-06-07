from __future__ import annotations

from app.services.sell_candidate_confidence import ConfidenceInputs, score_exit_confidence


def test_confidence_high_with_complete_data() -> None:
    level = score_exit_confidence(
        ConfidenceInputs(
            has_fmv=True,
            has_cost=True,
            has_identity=True,
            has_grade_status=True,
            hold_sell_agrees=True,
            grade_signal=False,
            profit_ratio=0.5,
        )
    )
    assert level == "HIGH"


def test_confidence_low_with_sparse_data() -> None:
    level = score_exit_confidence(
        ConfidenceInputs(
            has_fmv=False,
            has_cost=False,
            has_identity=False,
            has_grade_status=False,
            hold_sell_agrees=None,
            grade_signal=False,
            profit_ratio=None,
        )
    )
    assert level == "LOW"


def test_confidence_medium_mid_tier() -> None:
    level = score_exit_confidence(
        ConfidenceInputs(
            has_fmv=True,
            has_cost=True,
            has_identity=False,
            has_grade_status=False,
            hold_sell_agrees=None,
            grade_signal=False,
            profit_ratio=0.1,
        )
    )
    assert level == "MEDIUM"
