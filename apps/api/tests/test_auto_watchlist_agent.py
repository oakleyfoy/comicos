from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_watchlist import ReleaseWatchlist, ReleaseWatchlistItem
from app.services.auto_watchlist_agent import run_auto_watchlists
from test_inventory import create_order, register_and_login


def test_auto_watchlist_agent_generates_watchlists_from_inventory(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "auto-watchlists@example.com"
    token = register_and_login(client, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Batman: Dark Age",
                "publisher": "DC",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            }
        ],
    )

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        watchlists, execution = run_auto_watchlists(session, owner_user_id=owner_user_id)
        assert execution.status == "COMPLETED"
        assert len(watchlists) >= 3
        assert len(session.exec(select(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)).all()) >= 3
        assert len(session.exec(select(ReleaseWatchlistItem)).all()) >= 1
