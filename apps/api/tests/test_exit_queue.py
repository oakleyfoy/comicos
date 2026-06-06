from app.models.sell_intelligence_platform import EXIT_HOLD


def test_hold_not_queued_constant() -> None:
    assert EXIT_HOLD == "HOLD"
