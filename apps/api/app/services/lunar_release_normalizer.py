from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.schemas.release_intelligence import (
    ReleaseImportFeedRequest,
    ReleaseIssueImport,
    ReleaseSeriesImport,
    ReleaseVariantImport,
)
from app.services.lunar_csv_parser import row_product_code
from app.services.lunar_issue_identity import normalize_lunar_issue_number, parse_issue_number_from_title
from app.services.lunar_variant_classifier import classify_lunar_variant
from app.services.lunar_variant_identity import (
    build_canonical_issue_title,
    build_issue_release_uuid,
    build_variant_uuid,
)

DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y")


def _pick(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if row.get(key):
            return row[key]
    return ""


def _parse_date(value: str) -> date | None:
    from datetime import datetime

    cleaned = value.strip()
    if not cleaned:
        return None
    for fmt in DATE_FORMATS:
        try:
            if fmt == "%Y-%m-%d":
                return date.fromisoformat(cleaned)
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(value: str) -> float:
    cleaned = value.strip().replace("$", "")
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _issue_group_key(row: dict[str, str]) -> tuple[str, str, str]:
    publisher = _pick(row, "PublisherName", "Publisher", "publisher")
    series_name = _pick(row, "SeriesName", "MainDesc", "Series Name", "Series", "series_name")
    title = _pick(row, "Title", "ProductName", "FULL_TITLE", "full_title", "title")
    issue_number = _pick(row, "IssueNumber", "Issue Number", "issue_number", "Number", "IssueNo", "ISSUE_NO")
    if not issue_number and title:
        parsed = parse_issue_number_from_title(title)
        if parsed:
            issue_number = parsed
    issue_number = normalize_lunar_issue_number(issue_number or "1")
    return publisher, series_name, issue_number


def normalize_lunar_rows(rows: list[dict[str, str]]) -> tuple[ReleaseImportFeedRequest, list[tuple[str, str, str]]]:
    errors: list[tuple[str, str, str]] = []
    series_groups: dict[tuple[str, str], dict[tuple[str, str, str], list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))

    for index, row in enumerate(rows, start=1):
        publisher, series_name, issue_number = _issue_group_key(row)
        product_code = row_product_code(row)
        if not publisher or not series_name:
            errors.append((product_code or f"row:{index}", "MISSING_SERIES", "Publisher and series are required"))
            continue
        series_groups[(publisher, series_name)][(publisher, series_name, issue_number)].append(row)

    series_payloads: list[ReleaseSeriesImport] = []
    for (publisher, series_name), issue_map in series_groups.items():
        issues: list[ReleaseIssueImport] = []
        for (_pub, _series, issue_number), issue_rows in issue_map.items():
            release_uuid = build_issue_release_uuid(
                publisher=publisher,
                series_name=series_name,
                issue_number=issue_number,
            )
            canonical_title = build_canonical_issue_title(series_name=series_name, issue_number=issue_number)
            foc_date = None
            release_date = None
            cover_price = 0.0
            variants: list[ReleaseVariantImport] = []
            seen_variant_uuids: set[str] = set()

            for row in issue_rows:
                title = _pick(row, "Title", "ProductName", "FULL_TITLE", "full_title", "title")
                variant_desc = _pick(row, "VariantDesc", "VARIANT_DESC", "VariantDescription", "Variant Name", "VariantName")
                upc = _pick(row, "UPC", "UPC_NO", "UPCNo", "ISBN", "EAN")
                source_code = row_product_code(row) or upc
                classification = classify_lunar_variant(
                    title=title,
                    variant_desc=variant_desc,
                    full_title=_pick(row, "FULL_TITLE", "FullTitle"),
                )
                variant_uuid = build_variant_uuid(
                    source_item_code=source_code,
                    upc=upc,
                    classification=classification,
                )
                if variant_uuid in seen_variant_uuids:
                    continue
                seen_variant_uuids.add(variant_uuid)
                variants.append(
                    ReleaseVariantImport(
                        variant_uuid=variant_uuid,
                        variant_name=classification.variant_name,
                        ratio_value=classification.ratio_value,
                        ratio_type=classification.ratio_type,
                        is_incentive_variant=classification.is_incentive_variant,
                        variant_type=classification.variant_type,
                        cover_artist=classification.cover_artist,
                        source_item_code=source_code,
                    )
                )
                row_foc = _parse_date(_pick(row, "FOCDate", "FOC Date", "foc_date"))
                row_release = _parse_date(_pick(row, "InStoreDate", "In-Store Date", "In Store Date", "release_date"))
                row_price = _parse_float(_pick(row, "CoverPrice", "Cover Price", "Retail", "cover_price"))
                if row_foc is not None:
                    foc_date = row_foc
                if row_release is not None:
                    release_date = row_release
                if row_price > 0:
                    cover_price = row_price

            if not variants:
                errors.append((release_uuid, "MISSING_VARIANT", "No variants extracted for issue group"))
                continue

            issues.append(
                ReleaseIssueImport(
                    release_uuid=release_uuid,
                    issue_number=issue_number,
                    title=canonical_title,
                    foc_date=foc_date,
                    release_date=release_date,
                    cover_price=cover_price,
                    release_status="SCHEDULED",
                    variants=variants,
                )
            )
        if issues:
            series_payloads.append(
                ReleaseSeriesImport(
                    publisher=publisher,
                    series_name=series_name,
                    series_type="ONGOING",
                    status="ACTIVE",
                    issues=issues,
                )
            )
    return ReleaseImportFeedRequest(series=series_payloads), errors
