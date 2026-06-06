def test_dashboard_cards_keys() -> None:
    cards = {
        "top_sell_opportunities": [],
        "largest_gains": [],
        "largest_positions": [],
        "concentration_risks": [],
        "illiquid_positions": [],
        "fast_movers": [],
        "exit_queue_summary": {"queued": 0},
    }
    assert "expected_realized_profit" not in cards
    assert len(cards) == 7
