"""P88-03 watchlist / gap matching for marketplace monitoring."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.p81_discovery import P81FuturePullListItem
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _issue_match(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    return na.lstrip("#") == nb.lstrip("#")


def watchlist_match_labels(
    session: Session,
    *,
    owner_user_id: int,
    series: str,
    issue_number: str,
    title: str,
) -> list[str]:
    """Return human-readable watchlist match reasons (no external calls)."""
    labels: list[str] = []
    series_n = _norm(series)
    issue_n = _norm(issue_number)
    title_n = _norm(title)

    gaps = session.exec(
        select(MarketplaceAcquisitionOpportunity)
        .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
        .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
        .where(MarketplaceAcquisitionOpportunity.ownership_status == "GAP")
    ).all()
    for row in gaps:
        if series_n and _norm(row.series) == series_n and _issue_match(row.issue, issue_number):
            labels.append("Collection gap")
            break
        if title_n and title_n in _norm(row.title):
            labels.append("Collection gap")
            break

    buy_targets = session.exec(
        select(MarketplaceAcquisitionOpportunity)
        .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
        .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
        .where(MarketplaceAcquisitionOpportunity.recommendation.in_(("STRONG_BUY", "GOOD_BUY")))  # type: ignore[attr-defined]
    ).all()
    for row in buy_targets:
        if series_n and _norm(row.series) == series_n and _issue_match(row.issue, issue_number):
            labels.append("Buy target")
            break

    pull_rows = session.exec(
        select(P81FuturePullListItem).where(P81FuturePullListItem.owner_user_id == owner_user_id)
    ).all()
    for row in pull_rows:
        row_title = _norm(getattr(row, "title", "") or "")
        row_series = _norm(getattr(row, "series_name", "") or getattr(row, "series", "") or "")
        if series_n and row_series == series_n and issue_n and _issue_match(row.issue_number, issue_number):
            labels.append("Future pull list")
            break
        if title_n and title_n and title_n in row_title:
            labels.append("Future pull list")
            break

    return list(dict.fromkeys(labels))
