from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import (
    CatalogImage,
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
    CatalogUpc,
    CatalogVariant,
    utc_now,
)
from app.services.catalog_sources import CATALOG_SOURCE_PRIORITY

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ISSUE_FRACTION = re.compile(r"^(\d+)\s*/\s*(\d+)$")
_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+")


def normalize_series_name(name: str) -> str:
    """Lowercase series key: trim, collapse punctuation/spaces, drop leading the/a/an."""
    cleaned = _NON_ALNUM.sub(" ", (name or "").lower()).strip()
    collapsed = " ".join(cleaned.split())
    while collapsed:
        stripped = _LEADING_ARTICLE.sub("", collapsed, count=1)
        if stripped == collapsed:
            break
        collapsed = stripped.strip()
    return collapsed


def normalize_issue_number(raw: str) -> str:
    text = (raw or "").strip().lower()
    if not text:
        return ""
    fraction = _ISSUE_FRACTION.match(text)
    if fraction:
        return f"{int(fraction.group(1))}/{int(fraction.group(2))}"
    text = text.lstrip("#")
    if text.replace(".", "", 1).isdigit():
        value = float(text)
        if value.is_integer():
            return str(int(value))
        return str(value)
    return text


def normalize_upc(raw: str) -> str:
    return re.sub(r"[\s\-]", "", (raw or "").strip())


def merge_external_ids(existing: dict | None, source: str, external_id: str | int) -> dict:
    payload = dict(existing or {})
    bucket = dict(payload.get(source) or {})
    bucket[str(external_id)] = True
    payload[source] = bucket
    return payload


def source_priority(source: str) -> int:
    return CATALOG_SOURCE_PRIORITY.get(source.upper(), 99)


def _should_overwrite(*, incoming_source: str, existing_source: str | None, field_empty: bool) -> bool:
    if field_empty:
        return True
    if not existing_source:
        return True
    return source_priority(incoming_source) <= source_priority(existing_source)


def _merge_field(
    current: Any,
    incoming: Any,
    *,
    incoming_source: str,
    existing_source: str | None,
) -> Any:
    if incoming is None or incoming == "":
        return current
    if _should_overwrite(incoming_source=incoming_source, existing_source=existing_source, field_empty=not current):
        return incoming
    return current


def deduplicate_candidates(candidates: list[CatalogIssue]) -> list[CatalogIssue]:
    seen: set[int] = set()
    unique: list[CatalogIssue] = []
    for row in candidates:
        issue_id = int(row.id or 0)
        if issue_id in seen:
            continue
        seen.add(issue_id)
        unique.append(row)
    return unique


def upsert_publisher(
    session: Session,
    *,
    name: str,
    source: str,
    external_id: str | int | None = None,
    aliases: dict | None = None,
) -> CatalogPublisher:
    normalized = normalize_series_name(name)
    row = session.exec(select(CatalogPublisher).where(CatalogPublisher.normalized_name == normalized)).first()
    if row is None:
        row = CatalogPublisher(name=name.strip(), normalized_name=normalized, aliases=aliases)
        session.add(row)
        session.flush()
    else:
        row.name = _merge_field(row.name, name.strip(), incoming_source=source, existing_source=None)
        if aliases:
            row.aliases = {**(row.aliases or {}), **aliases}
    if external_id is not None:
        row.external_source_ids = merge_external_ids(row.external_source_ids, source, external_id)
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return row


def upsert_series(
    session: Session,
    *,
    name: str,
    publisher_id: int | None,
    source: str,
    external_id: str | int | None = None,
    volume_number: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> CatalogSeries:
    normalized = normalize_series_name(name)
    statement = select(CatalogSeries).where(CatalogSeries.normalized_name == normalized)
    if publisher_id is not None:
        statement = statement.where(CatalogSeries.publisher_id == publisher_id)
    row = session.exec(statement).first()
    if row is None:
        row = CatalogSeries(
            name=name.strip(),
            normalized_name=normalized,
            publisher_id=publisher_id,
            volume_number=volume_number,
            start_year=start_year,
            end_year=end_year,
        )
        session.add(row)
        session.flush()
    else:
        row.volume_number = _merge_field(row.volume_number, volume_number, incoming_source=source, existing_source=None)
        row.start_year = _merge_field(row.start_year, start_year, incoming_source=source, existing_source=None)
        row.end_year = _merge_field(row.end_year, end_year, incoming_source=source, existing_source=None)
    if external_id is not None:
        row.external_source_ids = merge_external_ids(row.external_source_ids, source, external_id)
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return row


def upsert_issue(
    session: Session,
    *,
    series_id: int,
    publisher_id: int | None,
    issue_number: str,
    source: str,
    external_id: str | int | None = None,
    title: str | None = None,
    description: str | None = None,
    cover_date=None,
    store_date=None,
    release_date=None,
    page_count: int | None = None,
    cover_price: Decimal | None = None,
    source_confidence: Decimal | None = None,
) -> CatalogIssue:
    normalized_number = normalize_issue_number(issue_number)
    row = session.exec(
        select(CatalogIssue)
        .where(CatalogIssue.series_id == series_id)
        .where(CatalogIssue.normalized_issue_number == normalized_number)
    ).first()
    existing_source = (row.external_source_ids or {}).get("_primary_source") if row else None
    if row is None:
        row = CatalogIssue(
            series_id=series_id,
            publisher_id=publisher_id,
            issue_number=issue_number.strip(),
            normalized_issue_number=normalized_number,
            title=title,
            description=description,
            cover_date=cover_date,
            store_date=store_date,
            release_date=release_date,
            page_count=page_count,
            cover_price=cover_price,
            source_confidence=source_confidence,
            external_source_ids={"_primary_source": source},
        )
        session.add(row)
        session.flush()
    else:
        row.title = _merge_field(row.title, title, incoming_source=source, existing_source=existing_source)
        row.description = _merge_field(row.description, description, incoming_source=source, existing_source=existing_source)
        row.cover_date = _merge_field(row.cover_date, cover_date, incoming_source=source, existing_source=existing_source)
        row.store_date = _merge_field(row.store_date, store_date, incoming_source=source, existing_source=existing_source)
        row.release_date = _merge_field(row.release_date, release_date, incoming_source=source, existing_source=existing_source)
        row.page_count = _merge_field(row.page_count, page_count, incoming_source=source, existing_source=existing_source)
        row.cover_price = _merge_field(row.cover_price, cover_price, incoming_source=source, existing_source=existing_source)
        if source_confidence is not None and (
            row.source_confidence is None
            or source_priority(source) <= source_priority(str(existing_source or source))
        ):
            row.source_confidence = source_confidence
    if external_id is not None:
        row.external_source_ids = merge_external_ids(row.external_source_ids, source, external_id)
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return row


def upsert_variant(
    session: Session,
    *,
    issue_id: int,
    source: str,
    variant_name: str | None = None,
    cover_artist: str | None = None,
    ratio: str | None = None,
    print_run: int | None = None,
    printing: str | None = None,
    format: str | None = None,
    sku: str | None = None,
    external_id: str | int | None = None,
) -> CatalogVariant:
    label = (variant_name or "Standard").strip()
    row = session.exec(
        select(CatalogVariant).where(CatalogVariant.issue_id == issue_id).where(CatalogVariant.variant_name == label)
    ).first()
    if row is None:
        row = CatalogVariant(
            issue_id=issue_id,
            variant_name=label,
            cover_artist=cover_artist,
            ratio=ratio,
            print_run=print_run,
            printing=printing,
            format=format,
            sku=sku,
        )
        session.add(row)
        session.flush()
    else:
        row.cover_artist = row.cover_artist or cover_artist
        row.ratio = row.ratio or ratio
        row.print_run = row.print_run or print_run
        row.printing = row.printing or printing
        row.format = row.format or format
        row.sku = row.sku or sku
    if external_id is not None:
        row.external_source_ids = merge_external_ids(row.external_source_ids, source, external_id)
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    return row


def upsert_upc(
    session: Session,
    *,
    raw_upc: str,
    issue_id: int | None,
    variant_id: int | None,
    source: str,
    confidence: Decimal | None = None,
    barcode_type: str | None = None,
) -> CatalogUpc:
    normalized = normalize_upc(raw_upc)
    row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    conf = confidence if confidence is not None else Decimal("1.0")
    if row is None:
        row = CatalogUpc(
            upc=raw_upc.strip(),
            normalized_upc=normalized,
            issue_id=issue_id,
            variant_id=variant_id,
            source=source,
            confidence=conf,
            barcode_type=barcode_type,
        )
        session.add(row)
    else:
        if issue_id is not None:
            row.issue_id = issue_id
        if variant_id is not None:
            row.variant_id = variant_id
        if conf >= row.confidence:
            row.confidence = conf
            row.source = source
        row.updated_at = utc_now()
        session.add(row)
    session.flush()
    return row


def upsert_image(
    session: Session,
    *,
    issue_id: int | None,
    variant_id: int | None,
    source_url: str | None,
    source: str,
    image_type: str = "cover",
    external_image_id: str | None = None,
    local_path: str | None = None,
    checksum: str | None = None,
) -> CatalogImage:
    if checksum:
        existing = session.exec(select(CatalogImage).where(CatalogImage.checksum == checksum)).first()
        if existing is not None:
            return existing
    if source_url:
        existing = session.exec(
            select(CatalogImage)
            .where(CatalogImage.issue_id == issue_id)
            .where(CatalogImage.source_url == source_url)
        ).first()
        if existing is not None:
            return existing
    row = CatalogImage(
        issue_id=issue_id,
        variant_id=variant_id,
        source_url=source_url,
        local_path=local_path,
        image_type=image_type,
        checksum=checksum,
        source=source,
        external_image_id=external_image_id,
    )
    session.add(row)
    session.flush()
    return row
