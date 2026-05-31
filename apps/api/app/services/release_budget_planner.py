from __future__ import annotations

from sqlmodel import Session

from app.schemas.release_platform import BudgetCategorySpendRead, BudgetForecastRead
from app.services.future_buy_queue import build_future_buy_queue

DEFAULT_COVER_PRICE = 4.99


def _estimate_price(cover_price: float) -> float:
    if cover_price and cover_price > 0:
        return float(cover_price)
    return DEFAULT_COVER_PRICE


def _sum_items(items) -> BudgetCategorySpendRead:
    must_buy = 0.0
    strong_buy = 0.0
    watch = 0.0
    for row in items:
        price = _estimate_price(row.issue.cover_price)
        if row.buy_category == "MUST_BUY":
            must_buy += price
        elif row.buy_category == "STRONG_BUY":
            strong_buy += price
        elif row.buy_category == "WATCH":
            watch += price
    return BudgetCategorySpendRead(must_buy=round(must_buy, 2), strong_buy=round(strong_buy, 2), watch=round(watch, 2))


def build_budget_forecast(session: Session, *, owner_user_id: int) -> BudgetForecastRead:
    queue = build_future_buy_queue(session, owner_user_id=owner_user_id)

    days_30 = _sum_items(queue.next_30_days)
    days_60 = _sum_items(queue.next_60_days)
    days_90 = _sum_items(queue.next_90_days)

    def total(spend: BudgetCategorySpendRead) -> float:
        return round(spend.must_buy + spend.strong_buy + spend.watch, 2)

    return BudgetForecastRead(
        days_30=days_30,
        days_60=days_60,
        days_90=days_90,
        expected_spend_total_30=total(days_30),
        expected_spend_total_60=total(days_60),
        expected_spend_total_90=total(days_90),
    )
