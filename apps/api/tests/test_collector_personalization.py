"""P77 personalization API smoke tests."""

from __future__ import annotations

from test_p77_personalization import (
    test_budget_status_and_quantities,
    test_personalize_score_publisher_and_budget,
    test_personalized_recommendations_api,
)

__all__ = [
    "test_personalize_score_publisher_and_budget",
    "test_personalized_recommendations_api",
    "test_budget_status_and_quantities",
]
