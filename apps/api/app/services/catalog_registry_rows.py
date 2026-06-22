"""Catalog master registry rows (replaces legacy comic_issue registry reads post–Phase D)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries


@dataclass(frozen=True)
class CatalogRegistryIssueRow:
    catalog_issue_id: int
    catalog_series_id: int
    publisher: str
    series: str
    issue_number: str
    cover_date: str | None = None


def load_catalog_registry_issue_rows(
    session: Session,
    *,
    series: str | None = None,
    issue_number: str | None = None,
    publisher: str | None = None,
) -> list[CatalogRegistryIssueRow]:
    stmt = (
        select(
            CatalogIssue.id,
            CatalogSeries.id,
            CatalogPublisher.name,
            CatalogSeries.name,
            CatalogIssue.issue_number,
            CatalogIssue.cover_date,
        )
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
        .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id, isouter=True)
    )
    if series is not None:
        stmt = stmt.where(CatalogSeries.name == series)
    if issue_number is not None:
        stmt = stmt.where(CatalogIssue.issue_number == issue_number)
    if publisher is not None:
        stmt = stmt.where(CatalogPublisher.name == publisher)
    stmt = stmt.order_by(
        CatalogPublisher.name.asc(),
        CatalogSeries.name.asc(),
        CatalogIssue.issue_number.asc(),
        CatalogIssue.id.asc(),
    )
    rows = session.exec(stmt).all()
    return [
        CatalogRegistryIssueRow(
            catalog_issue_id=int(iid),
            catalog_series_id=int(sid),
            publisher=str(pub or ""),
            series=str(ser),
            issue_number=str(num or ""),
            cover_date=str(cover) if cover else None,
        )
        for iid, sid, pub, ser, num, cover in rows
    ]
