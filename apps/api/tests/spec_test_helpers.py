from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Session

from app.models import Order, ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.release_watchlist import CollectionRun, ReleaseWatchlist, ReleaseWatchlistItem


def seed_spec_release_inputs(session: Session, *, owner_user_id: int) -> dict[str, int]:
    batman_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="DC",
        series_name="Batman",
        series_type="ONGOING",
        status="ACTIVE",
    )
    invincible_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Image",
        series_name="Invincible Universe",
        series_type="LIMITED",
        status="ACTIVE",
    )
    indie_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Boom!",
        series_name="Minor Threats",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(batman_series)
    session.add(invincible_series)
    session.add(indie_series)
    session.commit()
    session.refresh(batman_series)
    session.refresh(invincible_series)
    session.refresh(indie_series)

    batman_issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"spec-batman-{owner_user_id}",
        series_id=int(batman_series.id or 0),
        issue_number="1",
        title="Batman #1 First Appearance",
        foc_date=date(2026, 5, 31),
        release_date=date(2026, 6, 3),
        cover_price=4.99,
        release_status="SCHEDULED",
    )
    invincible_issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"spec-invincible-{owner_user_id}",
        series_id=int(invincible_series.id or 0),
        issue_number="25",
        title="Invincible Universe #25 Milestone",
        foc_date=date(2026, 5, 31),
        release_date=date(2026, 6, 3),
        cover_price=7.99,
        release_status="SCHEDULED",
    )
    indie_issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"spec-indie-{owner_user_id}",
        series_id=int(indie_series.id or 0),
        issue_number="4",
        title="Minor Threats #4",
        foc_date=date(2026, 5, 31),
        release_date=date(2026, 6, 10),
        cover_price=3.99,
        release_status="SCHEDULED",
    )
    session.add(batman_issue)
    session.add(invincible_issue)
    session.add(indie_issue)
    session.commit()
    session.refresh(batman_issue)
    session.refresh(invincible_issue)
    session.refresh(indie_issue)

    session.add(
        ReleaseVariant(
            issue_id=int(invincible_issue.id or 0),
            variant_name="1:25 Foil",
            ratio_value=25,
            variant_type="INCENTIVE",
            cover_artist="Ryan Ottley",
        )
    )
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_user_id,
            issue_id=int(batman_issue.id or 0),
            signal_type="NEW_NUMBER_ONE",
            confidence_score=0.95,
            signal_payload_json={"launch_type": "relaunch"},
        )
    )
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_user_id,
            issue_id=int(batman_issue.id or 0),
            signal_type="FIRST_APPEARANCE",
            confidence_score=0.92,
            signal_payload_json={"character": "Ghostmaker"},
        )
    )
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_user_id,
            issue_id=int(invincible_issue.id or 0),
            signal_type="MILESTONE_NUMBERING",
            confidence_score=0.88,
            signal_payload_json={"milestone": 25},
        )
    )
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_user_id,
            issue_id=int(invincible_issue.id or 0),
            signal_type="VARIANT_RATIO",
            confidence_score=0.83,
            signal_payload_json={"ratio_value": 25},
        )
    )
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_user_id,
            issue_id=int(invincible_issue.id or 0),
            signal_type="HIGH_RATIO_VARIANT",
            confidence_score=0.79,
            signal_payload_json={"ratio_value": 25},
        )
    )
    session.add(
        CollectionRun(
            owner_user_id=owner_user_id,
            publisher="DC",
            series_name="Batman",
            first_issue_owned="1",
            latest_issue_owned="150",
            issue_count_owned=35,
            continuity_status="ACTIVE_RUN",
        )
    )
    session.add(
        CollectionRun(
            owner_user_id=owner_user_id,
            publisher="Image",
            series_name="Invincible Universe",
            first_issue_owned="1",
            latest_issue_owned="24",
            issue_count_owned=12,
            continuity_status="ACTIVE_RUN",
        )
    )
    watchlist = ReleaseWatchlist(
        owner_user_id=owner_user_id,
        watchlist_name="Spec Favorites",
        watchlist_type="MANUAL",
    )
    session.add(watchlist)
    session.commit()
    session.refresh(watchlist)
    session.add(
        ReleaseWatchlistItem(
            watchlist_id=int(watchlist.id or 0),
            series_name="Batman",
            keyword="first appearance",
        )
    )
    session.add(
        ReleaseWatchlistItem(
            watchlist_id=int(watchlist.id or 0),
            publisher="Image",
            keyword="ratio",
        )
    )
    session.add(
        Order(
            user_id=owner_user_id,
            retailer="MyComicShop",
            order_date=date(2026, 5, 20),
            source_type="manual",
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("0"),
            total_amount=Decimal("34.99"),
        )
    )
    session.commit()
    return {
        "batman_issue_id": int(batman_issue.id or 0),
        "invincible_issue_id": int(invincible_issue.id or 0),
        "indie_issue_id": int(indie_issue.id or 0),
    }
