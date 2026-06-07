"""P88-03 marketplace monitoring orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.models.p88_marketplace_listing import P88MarketplaceListing, utc_now
from app.models.p88_marketplace_monitoring import (
    MarketplaceAlert,
    MarketplaceMonitoringRun,
    MarketplaceSavedSearch,
)
from app.services.marketplace.ebay_search_service import (
    EbayLiveSearchApiError,
    EbayLiveSearchConfigurationError,
    NormalizedMarketplaceListing,
    search_comics,
)
from app.services.marketplace.marketplace_listing_service import (
    sync_opportunity_best_listing,
    upsert_listing_from_search,
)
from app.services.marketplace.marketplace_watchlist_match import watchlist_match_labels

logger = logging.getLogger(__name__)

DEFAULT_MIN_DISCOUNT_FMV = 15.0


@dataclass
class MonitoringRunSummary:
    searches_run: int = 0
    listings_found: int = 0
    new_listings: int = 0
    price_drops: int = 0
    below_fmv_alerts: int = 0
    watchlist_matches: int = 0
    errors: list[str] = field(default_factory=list)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _search_terms(saved: MarketplaceSavedSearch) -> tuple[str | None, str | None, str | None, str | None]:
    title = saved.query.strip() or None
    series = saved.series.strip() or None
    issue = saved.issue_number.strip() or None
    publisher = saved.publisher.strip() or None
    if not any([title, series, issue]):
        raise ValueError("Saved search requires query and/or series and issue.")
    return title, series, issue, publisher


def find_opportunity_for_saved_search(
    session: Session,
    *,
    owner_user_id: int,
    saved: MarketplaceSavedSearch,
    listing_title: str,
) -> MarketplaceAcquisitionOpportunity | None:
    series_n = _norm(saved.series)
    issue_n = _norm(saved.issue_number)
    rows = session.exec(
        select(MarketplaceAcquisitionOpportunity)
        .where(MarketplaceAcquisitionOpportunity.owner_user_id == owner_user_id)
        .where(MarketplaceAcquisitionOpportunity.status == "ACTIVE")
    ).all()
    for row in rows:
        if series_n and issue_n and _norm(row.series) == series_n and _norm(row.issue).lstrip("#") == issue_n.lstrip("#"):
            return row
    title_n = _norm(listing_title)
    for row in rows:
        if title_n and title_n in _norm(row.title):
            return row
    return None


def _severity_for_alert(alert_type: str, *, discount_pct: float | None = None) -> str:
    if alert_type == "PRICE_DROP":
        return "MEDIUM"
    if alert_type == "BELOW_FMV" and discount_pct is not None and discount_pct >= 30:
        return "HIGH"
    if alert_type in {"NEW_LISTING", "WATCHLIST_MATCH"}:
        return "MEDIUM"
    return "LOW"


def _try_create_alert(
    session: Session,
    *,
    owner_user_id: int,
    saved_search_id: int | None,
    opportunity_id: int | None,
    listing_id: int | None,
    alert_type: str,
    title: str,
    message: str,
    dedupe_key: str,
    severity: str,
    dry_run: bool,
) -> bool:
    if dry_run:
        return True
    if listing_id is not None:
        exists = session.exec(
            select(MarketplaceAlert)
            .where(MarketplaceAlert.owner_user_id == owner_user_id)
            .where(MarketplaceAlert.listing_id == listing_id)
            .where(MarketplaceAlert.alert_type == alert_type)
            .where(MarketplaceAlert.dedupe_key == dedupe_key[:128])
        ).first()
        if exists:
            return False
    row = MarketplaceAlert(
        owner_user_id=owner_user_id,
        saved_search_id=saved_search_id,
        opportunity_id=opportunity_id,
        listing_id=listing_id,
        alert_type=alert_type,
        title=title,
        message=message,
        severity=severity,
        status="NEW",
        dedupe_key=dedupe_key[:128],
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    _maybe_create_collector_notification(
        session,
        owner_user_id=owner_user_id,
        title=title,
        message=message,
        opportunity_id=opportunity_id,
    )
    return True


def _maybe_create_collector_notification(
    session: Session,
    *,
    owner_user_id: int,
    title: str,
    message: str,
    opportunity_id: int | None,
) -> None:
    try:
        from app.services.collector_notification_service import _upsert_notification

        action = f"/marketplace-opportunity/{opportunity_id}" if opportunity_id else "/marketplace-monitoring"
        _upsert_notification(
            session,
            owner_user_id=owner_user_id,
            notification_type="MARKETPLACE_ALERT",
            priority="NORMAL",
            title=title[:512],
            message=message[:2000],
            action_url=action,
            related_entity_type="marketplace_alert",
            related_entity_id=opportunity_id,
        )
    except Exception:  # noqa: BLE001
        logger.debug("MARKETPLACE_ALERT notification skipped", exc_info=True)


def _process_listing(
    session: Session,
    *,
    owner_user_id: int,
    saved: MarketplaceSavedSearch,
    normalized: NormalizedMarketplaceListing,
    created: bool,
    listing: P88MarketplaceListing,
    opportunity: MarketplaceAcquisitionOpportunity | None,
    dry_run: bool,
    summary: MonitoringRunSummary,
) -> None:
    total = normalized.price + normalized.shipping
    if saved.max_price is not None and total > saved.max_price:
        return

    opp_id = int(opportunity.id) if opportunity and opportunity.id else None
    fmv = float(opportunity.estimated_fmv) if opportunity else 0.0
    min_disc = saved.min_discount_to_fmv if saved.min_discount_to_fmv is not None else DEFAULT_MIN_DISCOUNT_FMV

    if created:
        _try_create_alert(
            session,
            owner_user_id=owner_user_id,
            saved_search_id=int(saved.id) if saved.id else None,
            opportunity_id=opp_id,
            listing_id=int(listing.id) if listing.id else None,
            alert_type="NEW_LISTING",
            title=normalized.title,
            message=f"New {saved.marketplace} listing found at ${total:.2f}.",
            dedupe_key=normalized.item_id,
            severity=_severity_for_alert("NEW_LISTING"),
            dry_run=dry_run,
        )

    prior = listing.previous_price
    current = listing.price
    if prior is not None and current < prior - 0.009:
        last_alert = listing.last_price_drop_alert_price
        if last_alert is None or current < last_alert - 0.009:
            msg = f"{normalized.title} dropped from ${prior:.2f} to ${current:.2f}."
            if _try_create_alert(
                session,
                owner_user_id=owner_user_id,
                saved_search_id=int(saved.id) if saved.id else None,
                opportunity_id=opp_id,
                listing_id=int(listing.id) if listing.id else None,
                alert_type="PRICE_DROP",
                title=normalized.title,
                message=msg,
                dedupe_key=f"{prior:.2f}->{current:.2f}",
                severity=_severity_for_alert("PRICE_DROP"),
                dry_run=dry_run,
            ):
                summary.price_drops += 1
                if not dry_run:
                    listing.last_price_drop_alert_price = current
                    session.add(listing)

    if fmv > 0 and total < fmv:
        discount_pct = (fmv - total) / fmv * 100.0
        if discount_pct >= min_disc:
            dedupe = f"disc_{round(discount_pct, 1)}_{round(total, 2)}"
            msg = f"{normalized.title} is listed {discount_pct:.0f}% below estimated FMV."
            if _try_create_alert(
                session,
                owner_user_id=owner_user_id,
                saved_search_id=int(saved.id) if saved.id else None,
                opportunity_id=opp_id,
                listing_id=int(listing.id) if listing.id else None,
                alert_type="BELOW_FMV",
                title=normalized.title,
                message=msg,
                dedupe_key=dedupe,
                severity=_severity_for_alert("BELOW_FMV", discount_pct=discount_pct),
                dry_run=dry_run,
            ):
                summary.below_fmv_alerts += 1

    labels = watchlist_match_labels(
        session,
        owner_user_id=owner_user_id,
        series=saved.series,
        issue_number=saved.issue_number,
        title=normalized.title,
    )
    if labels:
        label_text = ", ".join(labels)
        if _try_create_alert(
            session,
            owner_user_id=owner_user_id,
            saved_search_id=int(saved.id) if saved.id else None,
            opportunity_id=opp_id,
            listing_id=int(listing.id) if listing.id else None,
            alert_type="WATCHLIST_MATCH",
            title=normalized.title,
            message=f"Listing matches your {label_text}.",
            dedupe_key=label_text.replace(" ", "_").lower()[:128],
            severity=_severity_for_alert("WATCHLIST_MATCH"),
            dry_run=dry_run,
        ):
            summary.watchlist_matches += 1


def run_saved_search(
    session: Session,
    *,
    saved: MarketplaceSavedSearch,
    settings: Settings | None = None,
    dry_run: bool = False,
    search_limit: int = 20,
) -> MonitoringRunSummary:
    resolved = settings or get_settings()
    summary = MonitoringRunSummary(searches_run=1)
    now = utc_now()
    saved.last_run_at = now
    saved.updated_at = now
    if not dry_run:
        session.add(saved)

    try:
        title, series, issue, publisher = _search_terms(saved)
        results = search_comics(
            title=title or saved.query or series,
            series=series,
            issue_number=issue,
            publisher=publisher,
            limit=search_limit,
            settings=resolved,
        )
    except (EbayLiveSearchConfigurationError, EbayLiveSearchApiError, ValueError) as exc:
        summary.errors.append(str(exc))
        saved.last_error = str(exc)[:512]
        if not dry_run:
            session.add(saved)
        return summary

    summary.listings_found = len(results)
    saved.last_error = ""
    saved.last_success_at = now

    for normalized in results:
        opportunity = find_opportunity_for_saved_search(
            session,
            owner_user_id=saved.owner_user_id,
            saved=saved,
            listing_title=normalized.title,
        )
        opp_id = int(opportunity.id) if opportunity and opportunity.id else None

        if dry_run:
            continue

        try:
            listing, created = upsert_listing_from_search(
                session,
                owner_user_id=saved.owner_user_id,
                opportunity_id=opp_id,
                normalized=normalized,
            )
        except ValueError:
            continue

        if created:
            summary.new_listings += 1

        if opportunity:
            sync_opportunity_best_listing(session, opportunity=opportunity)

        _process_listing(
            session,
            owner_user_id=saved.owner_user_id,
            saved=saved,
            normalized=normalized,
            created=created,
            listing=listing,
            opportunity=opportunity,
            dry_run=dry_run,
            summary=summary,
        )

    if not dry_run:
        session.add(saved)
        run = MarketplaceMonitoringRun(
            owner_user_id=saved.owner_user_id,
            saved_search_id=saved.id,
            searches_run=summary.searches_run,
            listings_found=summary.listings_found,
            new_listings=summary.new_listings,
            price_drops=summary.price_drops,
            below_fmv_alerts=summary.below_fmv_alerts,
            watchlist_matches=summary.watchlist_matches,
            errors_json=summary.errors[:50],
            created_at=now,
        )
        session.add(run)
        session.flush()
    return summary


def run_active_saved_searches(
    session: Session,
    *,
    owner_user_id: int,
    saved_search_id: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> MonitoringRunSummary:
    query = (
        select(MarketplaceSavedSearch)
        .where(MarketplaceSavedSearch.owner_user_id == owner_user_id)
        .where(MarketplaceSavedSearch.is_active == True)  # noqa: E712
        .order_by(MarketplaceSavedSearch.id.asc())
    )
    if saved_search_id is not None:
        query = query.where(MarketplaceSavedSearch.id == saved_search_id)
    if limit is not None:
        query = query.limit(max(1, limit))
    rows = session.exec(query).all()

    total = MonitoringRunSummary()
    for saved in rows:
        try:
            one = run_saved_search(session, saved=saved, settings=settings, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001
            total.errors.append(f"{saved.name}: {exc}")
            saved.last_error = str(exc)[:512]
            session.add(saved)
            continue
        total.searches_run += one.searches_run
        total.listings_found += one.listings_found
        total.new_listings += one.new_listings
        total.price_drops += one.price_drops
        total.below_fmv_alerts += one.below_fmv_alerts
        total.watchlist_matches += one.watchlist_matches
        total.errors.extend(one.errors)
    return total
