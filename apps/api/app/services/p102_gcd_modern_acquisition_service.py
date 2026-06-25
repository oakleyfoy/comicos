"""P102 — GCD modern catalog + barcode acquisition dry-run (read-only)."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.services.barcode_validation_service import validate_barcode_catalog_match
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_upc, normalize_series_name
from app.services.gcd_barcode_import_service import FULL_BARCODE_MIN_LEN, _year_from_key_date, extract_barcodes
from app.services.p101_catalog_cache_service import CatalogCacheContext, YEAR_MAX, YEAR_MIN
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label

GcdClass = Literal[
    "clean_primary_candidate",
    "variant_candidate",
    "reprint_or_digest",
    "foreign_or_international",
    "duplicate_or_conflict",
    "low_confidence",
]

FOCUS_PUBLISHERS: tuple[str, ...] = (
    "Marvel",
    "DC",
    "Image",
    "Boom",
    "IDW",
    "Dark Horse",
    "Dynamite",
    "Valiant",
)

YEAR_EXPR = """
CASE
  WHEN i.key_date IS NOT NULL AND length(trim(i.key_date)) >= 4
       AND substr(i.key_date, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'
    THEN CAST(substr(i.key_date, 1, 4) AS INTEGER)
  WHEN s.year_began BETWEEN 1900 AND 2100 THEN s.year_began
  ELSE NULL
END
"""

_REPRINT_DIGEST = re.compile(
    r"(digest|facsimile|reprint|ashcan|preview|sneak\s*peek|newsstand|magazine|annual\b|one\s*shot|one-shot)",
    re.IGNORECASE,
)
_VARIANT = re.compile(
    r"(cover\s+[a-z]|variant|\[.*\]|#\d+\s*cover|\.\d+\b|store\s+exclusive|ratio\b|foil\b|virgin\b)",
    re.IGNORECASE,
)
_FOREIGN = re.compile(
    r"(panini|egmont|hachette|carlsen|editorial|ediciones|presse|faraos|hjemmet|novaro|vid\b|magazine\s+pub|"
    r"comic\s+shop|uk\b|canada\b|australia\b|deutschland\b|france\b|spain\b|italy\b|mexico\b)",
    re.IGNORECASE,
)


@dataclass
class _Bucket:
    rows: int = 0
    clean: int = 0
    with_barcode: int = 0
    projected_issues: int = 0
    projected_upc: int = 0
    conflicts: int = 0
    rejected: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "rows": self.rows,
            "clean_primary_candidate": self.clean,
            "with_barcode": self.with_barcode,
            "projected_catalog_issue_inserts": self.projected_issues,
            "projected_catalog_upc_inserts": self.projected_upc,
            "conflicts": self.conflicts,
            "rejected": self.rejected,
        }


@dataclass
class P102DryRunReport:
    report_at: str
    gcd_database: str
    catalog_cache: str
    scope_years: tuple[int, int]
    scope_publishers: tuple[str, ...]
    total_gcd_rows_in_scope: int = 0
    already_in_comicos: int = 0
    classified_missing: int = 0
    clean_primary_candidate: int = 0
    candidates_with_barcode: int = 0
    projected_catalog_issue_inserts: int = 0
    projected_catalog_upc_inserts: int = 0
    conflicts: int = 0
    rejection_count: int = 0
    by_class: dict[str, int] = field(default_factory=dict)
    by_publisher: dict[str, dict[str, int]] = field(default_factory=dict)
    by_year: dict[str, dict[str, int]] = field(default_factory=dict)
    samples_clean: list[dict[str, Any]] = field(default_factory=list)
    samples_rejected: list[dict[str, Any]] = field(default_factory=list)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        return {
            "report_at": self.report_at,
            "gcd_database": self.gcd_database,
            "catalog_cache": self.catalog_cache,
            "scope_years": list(self.scope_years),
            "scope_publishers": list(self.scope_publishers),
            "total_gcd_rows_in_scope": self.total_gcd_rows_in_scope,
            "already_in_comicos": self.already_in_comicos,
            "classified_missing": self.classified_missing,
            "clean_primary_candidate": self.clean_primary_candidate,
            "candidates_with_barcode": self.candidates_with_barcode,
            "projected_catalog_issue_inserts": self.projected_catalog_issue_inserts,
            "projected_catalog_upc_inserts": self.projected_catalog_upc_inserts,
            "conflicts": self.conflicts,
            "rejection_count": self.rejection_count,
            "by_class": self.by_class,
            "by_publisher": self.by_publisher,
            "by_year": self.by_year,
            "samples_clean": self.samples_clean,
            "samples_rejected": self.samples_rejected,
            "notes": list(self.notes),
            "next_phase": {
                "write_batch": "After review: --write-batch with 100, then 1000, then publisher/year chunks.",
                "comicvine_role": "Enrichment only (covers/API ids), not primary discovery.",
            },
        }


def _gcd_identity_key(focus: str, series: str, issue: str) -> tuple[str, str, str]:
    return (
        focus,
        normalize_series_name(series),
        normalize_issue_number(issue),
    )


def _classify_missing_row(
    *,
    focus_label: str,
    publisher_raw: str,
    series: str,
    issue_number: str,
    year: int,
    barcode_raw: str | None,
    barcodes: list[str],
    ctx: CatalogCacheContext,
    seen_gcd_keys: Counter[tuple[str, str, str]],
) -> tuple[GcdClass, str, str | None, bool, bool]:
    """Returns class, reason, best_barcode, project_issue, project_upc."""
    ident = _gcd_identity_key(focus_label, series, issue_number)
    if seen_gcd_keys[ident] > 0:
        return "duplicate_or_conflict", "duplicate_gcd_identity_in_scope", barcodes[0] if barcodes else None, False, False
    seen_gcd_keys[ident] += 1

    series_text = series or ""
    pub_text = publisher_raw or ""

    if _REPRINT_DIGEST.search(series_text):
        return "reprint_or_digest", "series_title_digest_or_reprint_pattern", barcodes[0] if barcodes else None, False, False

    if _FOREIGN.search(pub_text) or _FOREIGN.search(series_text):
        return "foreign_or_international", "foreign_publisher_or_edition_marker", barcodes[0] if barcodes else None, False, False

    if _VARIANT.search(series_text) or _VARIANT.search(issue_number or ""):
        return "variant_candidate", "variant_or_cover_indicator", barcodes[0] if barcodes else None, False, False

    best_bc: str | None = None
    validation_ok = True
    validation_reason = ""
    for bc in barcodes:
        if len(bc) >= FULL_BARCODE_MIN_LEN:
            best_bc = bc
            break
    if best_bc is None and barcodes:
        best_bc = barcodes[0]

    if best_bc:
        norm_bc = normalize_upc(best_bc)
        validation = validate_barcode_catalog_match(
            best_bc,
            publisher=focus_label,
            issue_number=issue_number,
            year=str(year),
        )
        if validation.status != "exact_match":
            validation_ok = False
            validation_reason = validation.reason
        existing_issue = ctx.upc_to_issue.get(norm_bc) or ctx.upc_to_issue.get(best_bc)
        if existing_issue is not None:
            return (
                "duplicate_or_conflict",
                "barcode_already_on_catalog_upc",
                best_bc,
                False,
                False,
            )
        if norm_bc in ctx.learned_barcodes or best_bc in ctx.learned_barcodes:
            return (
                "duplicate_or_conflict",
                "barcode_user_confirmed_learned_mapping",
                best_bc,
                True,
                False,
            )

    if best_bc and not validation_ok:
        return "low_confidence", validation_reason[:200], best_bc, False, False

    if not issue_number or not normalize_issue_number(issue_number):
        return "low_confidence", "unparseable_issue_number", best_bc, False, False

    project_upc = bool(
        best_bc
        and validation_ok
        and normalize_upc(best_bc) not in ctx.upc_to_issue
        and best_bc not in ctx.upc_to_issue
        and normalize_upc(best_bc) not in ctx.learned_barcodes
        and best_bc not in ctx.learned_barcodes
    )
    return "clean_primary_candidate", "primary_us_direct_market_candidate", best_bc, True, project_upc


def run_p102_gcd_modern_dryrun(
    *,
    gcd_path: Path,
    cache_path: Path,
    max_clean_samples: int = 100,
    max_rejected_samples: int = 100,
) -> P102DryRunReport:
    ctx = CatalogCacheContext.load(cache_path)
    report = P102DryRunReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        gcd_database=str(gcd_path),
        catalog_cache=str(cache_path),
        scope_years=(YEAR_MIN, YEAR_MAX),
        scope_publishers=FOCUS_PUBLISHERS,
    )

    by_class: Counter[str] = Counter()
    pub_buckets: dict[str, _Bucket] = defaultdict(_Bucket)
    year_buckets: dict[str, _Bucket] = defaultdict(_Bucket)
    seen_gcd_keys: Counter[tuple[str, str, str]] = Counter()

    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    cur = conn.execute(
        f"""
        SELECT p.name, s.name, i.number, i.barcode, i.key_date, s.year_began
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE {YEAR_EXPR} BETWEEN ? AND ?
        """,
        (YEAR_MIN, YEAR_MAX),
    )

    while True:
        batch = cur.fetchmany(25000)
        if not batch:
            break
        for publisher, series, number, barcode, key_date, year_began in batch:
            year_val = _year_from_key_date(key_date, year_began)
            if year_val is None or not (YEAR_MIN <= year_val <= YEAR_MAX):
                continue
            year = int(year_val)
            focus = canonical_focus_publisher_label(str(publisher or ""))
            if focus is None or focus not in FOCUS_PUBLISHERS:
                continue

            report.total_gcd_rows_in_scope += 1
            pub_buckets[focus].rows += 1
            year_buckets[str(year)].rows += 1

            if ctx.matcher.matches(
                publisher=str(publisher or focus),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
            ):
                report.already_in_comicos += 1
                continue

            barcodes = extract_barcodes(barcode)
            if barcodes:
                pub_buckets[focus].with_barcode += 1
                year_buckets[str(year)].with_barcode += 1

            cls, reason, best_bc, project_issue, project_upc = _classify_missing_row(
                focus_label=focus,
                publisher_raw=str(publisher or ""),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
                barcode_raw=str(barcode) if barcode else None,
                barcodes=barcodes,
                ctx=ctx,
                seen_gcd_keys=seen_gcd_keys,
            )
            report.classified_missing += 1
            by_class[cls] += 1

            sample_row = {
                "class": cls,
                "reason": reason,
                "year": year,
                "publisher": publisher,
                "focus_publisher": focus,
                "series": series,
                "issue_number": number,
                "barcode": best_bc,
                "key_date": key_date,
            }

            if cls == "clean_primary_candidate":
                report.clean_primary_candidate += 1
                pub_buckets[focus].clean += 1
                year_buckets[str(year)].clean += 1
                if barcodes:
                    report.candidates_with_barcode += 1
                if project_issue:
                    report.projected_catalog_issue_inserts += 1
                    pub_buckets[focus].projected_issues += 1
                    year_buckets[str(year)].projected_issues += 1
                if project_upc:
                    report.projected_catalog_upc_inserts += 1
                    pub_buckets[focus].projected_upc += 1
                    year_buckets[str(year)].projected_upc += 1
                if len(report.samples_clean) < max_clean_samples:
                    report.samples_clean.append(sample_row)
            elif cls in ("duplicate_or_conflict",):
                report.conflicts += 1
                pub_buckets[focus].conflicts += 1
                year_buckets[str(year)].conflicts += 1
                if len(report.samples_rejected) < max_rejected_samples:
                    report.samples_rejected.append(sample_row)
            elif cls in ("low_confidence",):
                report.rejection_count += 1
                pub_buckets[focus].rejected += 1
                year_buckets[str(year)].rejected += 1
                if len(report.samples_rejected) < max_rejected_samples:
                    report.samples_rejected.append(sample_row)
            elif cls == "variant_candidate" and barcodes and len(report.samples_rejected) < max_rejected_samples:
                report.samples_rejected.append(sample_row)
            elif cls in ("reprint_or_digest", "foreign_or_international") and len(report.samples_rejected) < max_rejected_samples:
                report.samples_rejected.append(sample_row)

    conn.close()

    report.by_class = dict(by_class)
    report.by_publisher = {k: v.as_dict() for k, v in sorted(pub_buckets.items())}
    report.by_year = {k: year_buckets[k].as_dict() for k in sorted(year_buckets.keys())}
    report.notes = (
        "Dry-run only: no catalog_issue or catalog_upc writes.",
        "Scope: GCD rows 2009-2026 with P101 focus publisher mapping.",
        "GCD is intended as catalog spine + barcode source; ComicVine for enrichment.",
        "User-confirmed comic_issue_barcodes never overwritten (skipped for UPC insert).",
        "Next: --write-batch 100 after review, then scale.",
    )
    return report
