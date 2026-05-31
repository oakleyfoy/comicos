from __future__ import annotations

from collections import Counter

from sqlmodel import Session

from app.schemas.release_watchlist import (
    ReleaseWatchlistCreateRequest,
    ReleaseWatchlistDetailRead,
    ReleaseWatchlistItemCreateRequest,
    WatchlistAgentExecutionRead,
)
from app.services.release_watchlist_execution import AGENT_AUTO_WATCHLISTS, run_with_watchlist_execution
from app.services.release_watchlists import add_watchlist_item, create_watchlist
from app.services.run_continuity_agent import _inventory_issue_rows


def _character_candidates(series_names: list[str]) -> list[str]:
    candidates: list[str] = []
    for name in series_names:
        if ":" in name:
            candidates.append(name.split(":", 1)[0].strip())
    return [value for value, count in Counter(candidates).items() if count >= 1 and value]


def generate_watchlists_from_inventory(session: Session, *, owner_user_id: int) -> list[ReleaseWatchlistDetailRead]:
    rows = _inventory_issue_rows(session, owner_user_id=owner_user_id)
    if not rows:
        return []
    watchlists: list[ReleaseWatchlistDetailRead] = []
    owned_runs = create_watchlist(
        session,
        owner_user_id=owner_user_id,
        payload=ReleaseWatchlistCreateRequest(watchlist_name="Owned Active Runs", watchlist_type="AUTO_OWNED_RUNS"),
    )
    for row in {(item.publisher, item.series_name) for item in rows}:
        owned_runs = add_watchlist_item(
            session,
            owner_user_id=owner_user_id,
            watchlist_id=owned_runs.watchlist.id,
            payload=ReleaseWatchlistItemCreateRequest(publisher=row[0], series_name=row[1]),
        )
    watchlists.append(owned_runs)

    publisher_counts = Counter(row.publisher for row in rows)
    favorite_publishers = create_watchlist(
        session,
        owner_user_id=owner_user_id,
        payload=ReleaseWatchlistCreateRequest(watchlist_name="Favorite Publishers", watchlist_type="AUTO_PUBLISHERS"),
    )
    for publisher, _count in publisher_counts.items():
        favorite_publishers = add_watchlist_item(
            session,
            owner_user_id=owner_user_id,
            watchlist_id=favorite_publishers.watchlist.id,
            payload=ReleaseWatchlistItemCreateRequest(publisher=publisher),
        )
    watchlists.append(favorite_publishers)

    favorite_series = create_watchlist(
        session,
        owner_user_id=owner_user_id,
        payload=ReleaseWatchlistCreateRequest(watchlist_name="Favorite Series", watchlist_type="AUTO_SERIES"),
    )
    for series_name, _count in Counter(row.series_name for row in rows).items():
        favorite_series = add_watchlist_item(
            session,
            owner_user_id=owner_user_id,
            watchlist_id=favorite_series.watchlist.id,
            payload=ReleaseWatchlistItemCreateRequest(series_name=series_name),
        )
    watchlists.append(favorite_series)
    return watchlists


def generate_watchlists_from_user_preferences(session: Session, *, owner_user_id: int) -> list[ReleaseWatchlistDetailRead]:
    rows = _inventory_issue_rows(session, owner_user_id=owner_user_id)
    watchlists: list[ReleaseWatchlistDetailRead] = []
    favorite_characters = create_watchlist(
        session,
        owner_user_id=owner_user_id,
        payload=ReleaseWatchlistCreateRequest(watchlist_name="Favorite Characters", watchlist_type="AUTO_CHARACTERS"),
    )
    for character in _character_candidates([row.series_name for row in rows]):
        favorite_characters = add_watchlist_item(
            session,
            owner_user_id=owner_user_id,
            watchlist_id=favorite_characters.watchlist.id,
            payload=ReleaseWatchlistItemCreateRequest(character_name=character),
        )
    watchlists.append(favorite_characters)

    preference_signals = create_watchlist(
        session,
        owner_user_id=owner_user_id,
        payload=ReleaseWatchlistCreateRequest(watchlist_name="User Preference Signals", watchlist_type="AUTO_PREFERENCES"),
    )
    for publisher, _count in Counter(row.publisher for row in rows).most_common(2):
        preference_signals = add_watchlist_item(
            session,
            owner_user_id=owner_user_id,
            watchlist_id=preference_signals.watchlist.id,
            payload=ReleaseWatchlistItemCreateRequest(keyword=publisher),
        )
    watchlists.append(preference_signals)
    return watchlists


def run_auto_watchlists(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[ReleaseWatchlistDetailRead], WatchlistAgentExecutionRead]:
    def runner():
        watchlists: list[ReleaseWatchlistDetailRead] = []
        watchlists.extend(generate_watchlists_from_inventory(session, owner_user_id=owner_user_id))
        watchlists.extend(generate_watchlists_from_user_preferences(session, owner_user_id=owner_user_id))
        deduped: dict[int, ReleaseWatchlistDetailRead] = {row.watchlist.id: row for row in watchlists}
        return list(deduped.values())

    result, execution = run_with_watchlist_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_AUTO_WATCHLISTS,
        runner=runner,
    )
    return result, WatchlistAgentExecutionRead.model_validate(execution)
