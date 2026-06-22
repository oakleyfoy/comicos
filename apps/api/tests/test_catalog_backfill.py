"""Phase 3 backfill: link existing legacy/metadata copies to catalog_issue."""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session

from app.models import ComicIssue, ComicTitle, InventoryCopy, Publisher, Variant
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_backfill_service import backfill_catalog_links


def _seed_catalog(session: Session) -> CatalogIssue:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    ser = CatalogSeries(publisher_id=pub.id, name="Uncanny X-Men", normalized_name="uncanny x-men")
    session.add(ser)
    session.flush()
    iss = CatalogIssue(series_id=ser.id, publisher_id=pub.id, issue_number="266", normalized_issue_number="266")
    session.add(iss)
    session.commit()
    session.refresh(iss)
    return iss


def _legacy_copy(session: Session, *, series: str, issue: str, publisher: str) -> InventoryCopy:
    pub = Publisher(name=publisher)
    session.add(pub)
    session.flush()
    title = ComicTitle(publisher_id=pub.id, name=series)
    session.add(title)
    session.flush()
    ci = ComicIssue(comic_title_id=title.id, issue_number=issue)
    session.add(ci)
    session.flush()
    variant = Variant(comic_issue_id=ci.id, cover_name="Cover A")
    session.add(variant)
    session.flush()
    copy = InventoryCopy(user_id=1, variant_id=variant.id, copy_number=1, acquisition_cost=Decimal("0"))
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return copy


def test_backfill_matches_and_is_idempotent(session: Session) -> None:
    cat = _seed_catalog(session)
    match = _legacy_copy(session, series="Uncanny X-Men", issue="266", publisher="Marvel")
    miss = _legacy_copy(session, series="Totally Unknown Series", issue="1", publisher="Nobody")

    dry = backfill_catalog_links(session, dry_run=True, user_id=1)
    assert dry.scanned == 2
    assert dry.matched == 1
    assert dry.unmatched == 1
    # Dry run does not persist.
    session.refresh(match)
    assert match.catalog_issue_id is None

    applied = backfill_catalog_links(session, dry_run=False, user_id=1)
    assert applied.matched == 1
    session.refresh(match)
    assert match.catalog_issue_id == int(cat.id)
    session.refresh(miss)
    assert miss.catalog_issue_id is None

    # Idempotent: already-linked copies are skipped on a second run.
    again = backfill_catalog_links(session, dry_run=False, user_id=1)
    assert again.matched == 0
    assert again.already_linked == 1
