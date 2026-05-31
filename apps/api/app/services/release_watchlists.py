from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.release_watchlist import ReleaseWatchlist, ReleaseWatchlistItem
from app.schemas.release_intelligence import ReleaseIssueRead
from app.schemas.release_watchlist import (
    ReleaseWatchlistCreateRequest,
    ReleaseWatchlistDetailRead,
    ReleaseWatchlistItemCreateRequest,
    ReleaseWatchlistItemRead,
    ReleaseWatchlistRead,
    WatchlistMatchRead,
)


def create_watchlist(
    session: Session,
    *,
    owner_user_id: int,
    payload: ReleaseWatchlistCreateRequest,
) -> ReleaseWatchlistDetailRead:
    row = session.exec(
        select(ReleaseWatchlist)
        .where(ReleaseWatchlist.owner_user_id == owner_user_id)
        .where(ReleaseWatchlist.watchlist_name == payload.watchlist_name)
        .where(ReleaseWatchlist.watchlist_type == payload.watchlist_type)
    ).first()
    if row is None:
        row = ReleaseWatchlist(
            owner_user_id=owner_user_id,
            watchlist_name=payload.watchlist_name,
            watchlist_type=payload.watchlist_type,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    return get_watchlist(session, watchlist_id=int(row.id or 0), owner_user_id=owner_user_id)


def add_watchlist_item(
    session: Session,
    *,
    owner_user_id: int,
    watchlist_id: int,
    payload: ReleaseWatchlistItemCreateRequest,
) -> ReleaseWatchlistDetailRead:
    watchlist = session.get(ReleaseWatchlist, watchlist_id)
    if watchlist is None or watchlist.owner_user_id != owner_user_id:
        raise ValueError("Watchlist not found.")
    row = session.exec(
        select(ReleaseWatchlistItem)
        .where(ReleaseWatchlistItem.watchlist_id == watchlist_id)
        .where(ReleaseWatchlistItem.publisher == payload.publisher)
        .where(ReleaseWatchlistItem.series_name == payload.series_name)
        .where(ReleaseWatchlistItem.character_name == payload.character_name)
        .where(ReleaseWatchlistItem.creator_name == payload.creator_name)
        .where(ReleaseWatchlistItem.keyword == payload.keyword)
    ).first()
    if row is None:
        row = ReleaseWatchlistItem(
            watchlist_id=watchlist_id,
            publisher=payload.publisher,
            series_name=payload.series_name,
            character_name=payload.character_name,
            creator_name=payload.creator_name,
            keyword=payload.keyword,
        )
        session.add(row)
        session.commit()
    return get_watchlist(session, watchlist_id=watchlist_id, owner_user_id=owner_user_id)


def remove_watchlist_item(session: Session, *, owner_user_id: int, watchlist_id: int, item_id: int) -> None:
    watchlist = session.get(ReleaseWatchlist, watchlist_id)
    item = session.get(ReleaseWatchlistItem, item_id)
    if watchlist is None or watchlist.owner_user_id != owner_user_id or item is None or item.watchlist_id != watchlist_id:
        raise ValueError("Watchlist item not found.")
    session.delete(item)
    session.commit()


def _read_detail(session: Session, watchlist: ReleaseWatchlist) -> ReleaseWatchlistDetailRead:
    items = session.exec(
        select(ReleaseWatchlistItem)
        .where(ReleaseWatchlistItem.watchlist_id == int(watchlist.id or 0))
        .order_by(ReleaseWatchlistItem.created_at.desc(), ReleaseWatchlistItem.id.desc())
    ).all()
    return ReleaseWatchlistDetailRead(
        watchlist=ReleaseWatchlistRead.model_validate(watchlist),
        items=[ReleaseWatchlistItemRead.model_validate(item) for item in items],
    )


def list_watchlists(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ReleaseWatchlist)
        .where(ReleaseWatchlist.owner_user_id == owner_user_id)
        .order_by(ReleaseWatchlist.created_at.desc(), ReleaseWatchlist.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [_read_detail(session, row) for row in page], len(rows)


def get_watchlist(session: Session, *, watchlist_id: int, owner_user_id: int) -> ReleaseWatchlistDetailRead:
    row = session.get(ReleaseWatchlist, watchlist_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("Watchlist not found.")
    return _read_detail(session, row)


def _match_item_to_issue(item: ReleaseWatchlistItem, series: ReleaseSeries, issue: ReleaseIssue) -> bool:
    haystacks = " ".join(
        value.lower()
        for value in [series.publisher, series.series_name, issue.title]
        if value
    )
    if item.publisher and item.publisher.lower() != series.publisher.lower():
        return False
    if item.series_name and item.series_name.lower() != series.series_name.lower():
        return False
    if item.keyword and item.keyword.lower() not in haystacks:
        return False
    if item.character_name and item.character_name.lower() not in haystacks:
        return False
    if item.creator_name and item.creator_name.lower() not in haystacks:
        return False
    return True


def list_watchlist_matches(session: Session, *, owner_user_id: int, limit: int = 50) -> list[WatchlistMatchRead]:
    watchlists, _ = list_watchlists(session, owner_user_id=owner_user_id, limit=200, offset=0)
    issues = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
    ).all()
    series_by_id = {
        int(series.id or 0): series
        for series in session.exec(select(ReleaseSeries).where(ReleaseSeries.owner_user_id == owner_user_id)).all()
    }
    matches: list[WatchlistMatchRead] = []
    for watchlist in watchlists:
        for item in watchlist.items:
            item_row = session.get(ReleaseWatchlistItem, item.id)
            if item_row is None:
                continue
            for issue in issues:
                series = series_by_id.get(issue.series_id)
                if series is None:
                    continue
                if _match_item_to_issue(item_row, series, issue):
                    matches.append(
                        WatchlistMatchRead(
                            watchlist=watchlist.watchlist,
                            item=item,
                            release_issue=ReleaseIssueRead.model_validate(issue),
                        )
                    )
    return matches[:limit]
