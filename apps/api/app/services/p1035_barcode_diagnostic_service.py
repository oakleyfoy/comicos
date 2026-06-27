"""Per-barcode diagnostics for P103.5 GCD identity + UPC backfill."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogUpc
from app.models.intake_queue import ComicIssueBarcode
from app.services.catalog_ingestion_service import normalize_upc
from app.services.p101_catalog_cache_service import CatalogCacheContext, YEAR_MAX, YEAR_MIN
from app.services.p103_gcd_enrichment_fast import (
    _CATALOG_ENRICHMENT_SELECT,
    _snapshot_from_enrichment_row,
    load_gcd_index_for_enrichment,
)
from app.services.p103_gcd_enrichment_helpers import (
    extract_gcd_issue_id,
    gcd_row_to_plan_inputs,
    resolve_catalog_issue_id_for_gcd_match,
)
from app.services.p1035_gcd_identity_backfill_service import (
    _comicvine_ids,
    _expand_scope_for_gcd_index,
    build_comicvine_duplicate_index,
    lookup_gcd_for_catalog,
    plan_identity_backfill,
)
from app.services.p1035_gcd_identity_exception_service import (
    P1035_EXCEPTION_FILES,
    explain_ambiguous_gcd_lookup,
)


@dataclass
class P1035BarcodeDiagnosticContext:
    gcd_path: Path
    cache_path: Path
    cache_ctx: CatalogCacheContext
    gcd_index: Any
    dup_index: dict[str, list[int]]
    exception_dir: Path | None = None


def _load_enrichment_snap(cache_path: Path, issue_id: int):
    conn = sqlite3.connect(cache_path)
    row = conn.execute(
        _CATALOG_ENRICHMENT_SELECT + " WHERE issue_id = ?",
        (int(issue_id),),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _snapshot_from_enrichment_row(row)


from app.services.gcd_barcode_search_service import find_gcd_rows_by_normalized_barcode
def _resolve_catalog_issue_from_gcd_match(
    cache_path: Path,
    gcd_match: dict[str, Any],
) -> int | None:
    return resolve_catalog_issue_id_for_gcd_match(
        cache_path,
        publisher=str(gcd_match.get("publisher") or ""),
        series=str(gcd_match.get("series") or ""),
        issue_number=str(gcd_match.get("issue_number") or ""),
    )


def _conflict_detail(skip: str | None) -> str | None:
    if skip in ("learned_barcode_conflict", "upc_mapped_elsewhere", "barcode_validation_failed"):
        return skip
    return None


def classify_p1035_for_snap(
    *,
    catalog_issue_id: int | None,
    snap,
    ctx: CatalogCacheContext,
    gcd_index,
    dup_index: dict[str, list[int]],
) -> dict[str, Any]:
    if catalog_issue_id is None:
        return {
            "skipped": True,
            "category": "missing_catalog_issue",
            "detail": None,
        }
    if snap is None:
        return {
            "skipped": True,
            "category": "missing_catalog_issue",
            "detail": "catalog_issue_not_in_enrichment_cache",
        }
    if extract_gcd_issue_id(snap.external_source_ids) is not None:
        return {
            "skipped": True,
            "category": "already_has_gcd",
            "detail": str(extract_gcd_issue_id(snap.external_source_ids)),
        }
    from app.services.p1035_gcd_identity_backfill_service import _cv_duplicate_conflict

    if _cv_duplicate_conflict(snap, dup_index):
        peers: list[int] = []
        for cv_id in _comicvine_ids(snap.external_source_ids):
            peers.extend(dup_index.get(cv_id, []))
        return {
            "skipped": True,
            "category": "duplicate_cv",
            "detail": None,
            "comicvine_peer_issue_ids": sorted(set(peers)),
        }
    gcd_row = lookup_gcd_for_catalog(gcd_index, snap)
    if gcd_row is None:
        reason, candidates = explain_ambiguous_gcd_lookup(gcd_index, snap)
        return {
            "skipped": True,
            "category": "ambiguous",
            "detail": reason,
            "gcd_candidate_count": len(candidates),
        }
    planned, plan_skip, upc_n = plan_identity_backfill(snap, gcd_row, ctx=ctx)
    if plan_skip == "already_has_gcd":
        return {"skipped": True, "category": "already_has_gcd", "detail": None}
    if plan_skip is not None:
        return {
            "skipped": True,
            "category": "conflict",
            "detail": _conflict_detail(plan_skip) or plan_skip,
        }
    return {
        "skipped": False,
        "category": "eligible",
        "detail": None,
        "planned_field_count": len(planned),
        "projected_upc_inserts": upc_n,
        "matched_gcd_issue_id": int(gcd_row_to_plan_inputs(gcd_row)["gcd_issue_id"]),
    }


def scan_exception_backlog(exception_dir: Path, normalized: str) -> list[dict[str, str]]:
    if not exception_dir.is_dir():
        return []
    hits: list[dict[str, str]] = []
    for stem in P1035_EXCEPTION_FILES:
        for path in sorted(exception_dir.glob(f"{stem}.*")):
            if path.suffix.lower() == ".json":
                try:
                    rows = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    blob = json.dumps(row, ensure_ascii=False)
                    if normalized in blob or normalized in str(row.get("conflicting_barcode") or ""):
                        hits.append({"file": path.name, "catalog_issue_id": str(row.get("catalog_issue_id") or "")})
            elif path.suffix.lower() == ".csv":
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                if normalized in text:
                    hits.append({"file": path.name, "catalog_issue_id": ""})
    return hits


def build_p1035_barcode_diagnostic_context(
    *,
    gcd_path: Path,
    cache_path: Path,
    exception_dir: Path | None = None,
) -> P1035BarcodeDiagnosticContext:
    from app.services.p103_gcd_enrichment_fast import load_catalog_enrichment_scope
    from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters

    cache_ctx = CatalogCacheContext.load(cache_path)
    filters = EnrichmentFilters(
        publisher=None,
        year_from=YEAR_MIN,
        year_to=YEAR_MAX,
        limit=None,
        all_catalog=True,
        year_filter_explicit=False,
    )
    full_scope = load_catalog_enrichment_scope(cache_path, filters=filters)
    dup_index = build_comicvine_duplicate_index(full_scope)
    expanded = _expand_scope_for_gcd_index(full_scope)
    gcd_index = load_gcd_index_for_enrichment(
        gcd_path,
        year_from=YEAR_MIN,
        year_to=YEAR_MAX,
        focus_publisher=None,
        all_catalog=True,
        year_filter_explicit=False,
        catalog_scope=expanded,
    )
    return P1035BarcodeDiagnosticContext(
        gcd_path=gcd_path,
        cache_path=cache_path,
        cache_ctx=cache_ctx,
        gcd_index=gcd_index,
        dup_index=dup_index,
        exception_dir=exception_dir,
    )


def diagnose_barcode(
    session: Session,
    raw_barcode: str,
    diag_ctx: P1035BarcodeDiagnosticContext,
) -> dict[str, Any]:
    normalized = normalize_upc(raw_barcode) or raw_barcode.strip()
    upc_row = session.exec(
        select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized).limit(1)
    ).first()
    learned_row = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized).limit(1)
    ).first()
    in_cache_upc = normalized in diag_ctx.cache_ctx.upc_to_issue
    in_cache_learned = normalized in diag_ctx.cache_ctx.learned_barcodes

    gcd_matches = find_gcd_rows_by_normalized_barcode(diag_ctx.gcd_path, normalized)
    for m in gcd_matches:
        m["catalog_issue_id_resolved"] = _resolve_catalog_issue_from_gcd_match(diag_ctx.cache_path, m)

    catalog_issue_id: int | None = None
    if upc_row is not None and upc_row.issue_id is not None:
        catalog_issue_id = int(upc_row.issue_id)
    elif learned_row is not None:
        catalog_issue_id = int(learned_row.catalog_issue_id)
    elif in_cache_upc:
        catalog_issue_id = int(diag_ctx.cache_ctx.upc_to_issue[normalized])
    elif gcd_matches:
        for m in gcd_matches:
            rid = m.get("catalog_issue_id_resolved")
            if rid is not None:
                catalog_issue_id = int(rid)
                break

    catalog_issue_summary: dict[str, Any] | None = None
    if catalog_issue_id is not None:
        issue = session.get(CatalogIssue, catalog_issue_id)
        if issue is not None:
            catalog_issue_summary = {
                "issue_id": catalog_issue_id,
                "title": issue.title,
                "issue_number": issue.issue_number,
                "gcd_issue_id": extract_gcd_issue_id(issue.external_source_ids),
            }

    snap = _load_enrichment_snap(diag_ctx.cache_path, catalog_issue_id) if catalog_issue_id else None
    p1035 = classify_p1035_for_snap(
        catalog_issue_id=catalog_issue_id,
        snap=snap,
        ctx=diag_ctx.cache_ctx,
        gcd_index=diag_ctx.gcd_index,
        dup_index=diag_ctx.dup_index,
    )

    exception_hits: list[dict[str, str]] = []
    if diag_ctx.exception_dir is not None:
        exception_hits = scan_exception_backlog(diag_ctx.exception_dir, normalized)

    return {
        "barcode_raw": raw_barcode,
        "normalized_barcode": normalized,
        "in_catalog_upc": upc_row is not None or in_cache_upc,
        "catalog_upc_issue_id": int(upc_row.issue_id) if upc_row and upc_row.issue_id else diag_ctx.cache_ctx.upc_to_issue.get(normalized),
        "in_learned_barcode": learned_row is not None or in_cache_learned,
        "learned_barcode_issue_id": int(learned_row.catalog_issue_id) if learned_row else None,
        "learned_barcode_source": learned_row.source if learned_row else None,
        "in_gcd": len(gcd_matches) > 0,
        "gcd_matches": gcd_matches,
        "matching_catalog_issue": catalog_issue_summary,
        "p1035_skipped": p1035.get("skipped"),
        "p1035_skip_category": p1035.get("category"),
        "p1035_skip_detail": p1035.get("detail"),
        "p1035": p1035,
        "exception_backlog_hits": exception_hits,
    }
