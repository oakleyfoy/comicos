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


_YEAR_IN_PARENS = re.compile(r"\(\s*(19|20)\d{2}\s*\)")


def comicvine_catalog_series_name(volume_metadata: dict[str, Any]) -> str:
    """Distinct catalog series name per ComicVine volume (avoids merging 1960 vs 2016 runs)."""
    name = str(volume_metadata.get("name") or "Unknown").strip()
    start_year = volume_metadata.get("start_year")
    if start_year is None:
        return name
    try:
        year_int = int(start_year)
    except (TypeError, ValueError):
        return name
    if _YEAR_IN_PARENS.search(name):
        return name
    return f"{name} ({year_int})"


def catalog_series_id_for_comicvine_volume(
    session: Session,
    *,
    volume_id: int,
    publisher_id: int | None = None,
    prefer_start_year: int | None = None,
) -> int | None:
    """Resolve catalog series row linked to a ComicVine volume id (newest / closest year if ambiguous)."""
    statement = select(CatalogSeries)
    if publisher_id is not None:
        statement = statement.where(CatalogSeries.publisher_id == publisher_id)
    vol_key = str(volume_id)
    matches: list[CatalogSeries] = []
    for row in session.exec(statement):
        bucket = (row.external_source_ids or {}).get("COMICVINE") or {}
        if isinstance(bucket, dict) and vol_key in bucket:
            matches.append(row)
    if not matches:
        return None
    if len(matches) == 1:
        sid = matches[0].id
        return int(sid) if sid is not None else None

    def sort_key(series: CatalogSeries) -> tuple[int, int]:
        sy = series.start_year
        if sy is None:
            sy = 0
        if prefer_start_year is not None:
            return (abs(int(sy) - prefer_start_year), -int(sy))
        return (0, -int(sy))

    matches.sort(key=sort_key)
    sid = matches[0].id
    return int(sid) if sid is not None else None


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


def _is_year_token(token: str) -> bool:
    return bool(re.fullmatch(r"(19|20)\d{2}", token))


def series_names_compatible(vision_norm: str, catalog_norm: str) -> bool:
    """True when normalized names are the same run (not e.g. superman vs superman batman)."""
    if not vision_norm or not catalog_norm:
        return False
    if vision_norm == catalog_norm:
        return True
    v_parts = vision_norm.split()
    c_parts = catalog_norm.split()
    if len(c_parts) > len(v_parts) and c_parts[: len(v_parts)] == v_parts:
        extra = c_parts[len(v_parts) :]
        return bool(extra) and all(_is_year_token(t) for t in extra)
    if len(v_parts) > len(c_parts) and v_parts[: len(c_parts)] == c_parts:
        extra = v_parts[len(c_parts) :]
        return bool(extra) and all(_is_year_token(t) for t in extra)
    return False


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


def comic_barcode_lookup_variants(raw: str) -> list[str]:
    """Candidate keys for catalog / ComicVine (12-digit UPC, full UPC+supplement, etc.)."""
    normalized = normalize_upc(raw)
    if not normalized.isdigit():
        return []
    variants: list[str] = []

    def add(value: str) -> None:
        if value and value not in variants:
            variants.append(value)

    add(normalized)
    if len(normalized) >= 17:
        add(normalized[:17])
    if len(normalized) >= 12:
        add(normalized[:12])
    return variants


def merge_comic_upc_decodes(candidates: list[str]) -> str | None:
    """Merge 1D decode results into one key (12-digit UPC-A + optional 5-digit supplement)."""
    digit_strings: list[str] = []
    for raw in candidates:
        normalized = normalize_upc(raw)
        if normalized.isdigit():
            digit_strings.append(normalized)
    if not digit_strings:
        return None

    for digits in sorted(digit_strings, key=len, reverse=True):
        if len(digits) >= 17 and upc_check_digit_valid(digits[:12]):
            return digits[:17]
        if len(digits) in (16, 15, 14) and upc_check_digit_valid(digits[:12]):
            return digits[:12] + digits[12:].zfill(5)[-5:]

    upc12: str | None = None
    supplement5: str | None = None
    for digits in digit_strings:
        if len(digits) == 12 and upc_check_digit_valid(digits):
            upc12 = digits
        elif len(digits) == 13 and upc_check_digit_valid(digits) and digits.startswith("0"):
            upc12 = digits[1:]
        elif len(digits) == 5:
            supplement5 = digits
        elif len(digits) == 4 and digits.isdigit():
            supplement5 = digits.zfill(5)

    if upc12 and supplement5:
        return f"{upc12}{supplement5}"
    if upc12:
        return upc12

    for digits in sorted(digit_strings, key=len, reverse=True):
        if barcode_usable_for_lookup(digits):
            return digits
    return None


def barcode_usable_for_lookup(digits: str) -> bool:
    if not digits.isdigit():
        return False
    if len(digits) >= 17:
        return True
    if len(digits) in (12, 13):
        return upc_check_digit_valid(digits)
    return 11 <= len(digits) <= 18


def upc_check_digit_valid(raw: str) -> bool:
    """True when normalized UPC-A (12) or EAN-13 passes the standard check digit."""
    digits = normalize_upc(raw)
    if not digits.isdigit():
        return False
    if len(digits) == 12:
        digits = "0" + digits
    if len(digits) != 13:
        return False
    total = sum(int(ch) * (1 if idx % 2 == 0 else 3) for idx, ch in enumerate(digits[:12]))
    check = (10 - (total % 10)) % 10
    return check == int(digits[12])


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
