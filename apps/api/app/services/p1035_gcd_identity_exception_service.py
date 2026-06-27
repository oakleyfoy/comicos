"""P103.5 manual review backlog — exception rows, export, and manual attach."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode
from app.services.barcode_validation_service import validate_barcode_catalog_match
from app.services.catalog_ingestion_service import merge_external_ids, normalize_upc, series_names_compatible
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.gcd_catalog_upc_insert_service import insert_catalog_upc_if_absent, preload_catalog_upc_guards
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p103_gcd_enrichment_fast import EnrichmentIssueSnapshot, _GcdIndex
from app.services.p103_gcd_enrichment_helpers import (
    extract_gcd_issue_id,
    gcd_row_to_plan_inputs,
    parse_key_date,
)
from app.services.p1035_gcd_identity_backfill_service import (
    _apply_identity_planned,
    _comicvine_ids,
    _normalize_gcd_inputs,
    _series_norm_aliases,
    lookup_gcd_for_catalog,
    plan_identity_backfill,
)

P1035_EXCEPTION_FILES = (
    "ambiguous_matches",
    "duplicate_cv_conflicts",
    "upc_conflicts",
    "validation_failures",
)


def _iso_date(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if str(value).strip() else None


def _primary_comicvine_id(external: dict[str, Any] | None) -> str | None:
    ids = _comicvine_ids(external)
    return ids[0] if ids else None


def _gcd_candidate_payload(row: dict[str, Any]) -> dict[str, Any]:
    inputs = _normalize_gcd_inputs(row)
    cal, year, _ = parse_key_date(str(inputs.get("key_date") or ""), inputs.get("year"))
    return {
        "gcd_issue_id": inputs.get("gcd_issue_id"),
        "gcd_series_name": inputs.get("series"),
        "gcd_issue_number": inputs.get("issue_number"),
        "gcd_publisher": inputs.get("publisher"),
        "gcd_year": inputs.get("year"),
        "gcd_barcode": inputs.get("barcode"),
        "gcd_cover_date": _iso_date(cal),
        "gcd_key_date": inputs.get("key_date"),
        "gcd_title": inputs.get("title"),
    }


def _catalog_context_from_snap(
    snap: EnrichmentIssueSnapshot,
    *,
    ctx: CatalogCacheContext | None = None,
    existing_barcode: str | None = None,
) -> dict[str, Any]:
    ext = snap.external_source_ids if isinstance(snap.external_source_ids, dict) else {}
    barcode = existing_barcode
    if barcode is None and ctx is not None and snap.has_upc:
        for norm, iid in ctx.upc_to_issue.items():
            if int(iid) == int(snap.issue_id):
                barcode = norm
                break
    return {
        "catalog_issue_id": int(snap.issue_id),
        "title": snap.title,
        "issue_number": snap.issue_number,
        "publisher": snap.publisher_name,
        "year": snap.year,
        "cover_date": _iso_date(snap.cover_date),
        "release_date": _iso_date(snap.release_date),
        "comicvine_issue_id": _primary_comicvine_id(ext),
        "existing_external_source_ids": ext,
        "existing_barcode": barcode,
        "has_upc": bool(snap.has_upc),
    }


def explain_ambiguous_gcd_lookup(index: _GcdIndex, snap: EnrichmentIssueSnapshot) -> tuple[str, list[dict[str, Any]]]:
    """Describe why lookup_gcd_for_catalog returned None and list plausible GCD rows."""
    if lookup_gcd_for_catalog(index, snap) is not None:
        return "matched", []

    collected: list[dict[str, Any]] = []
    reason = "no_gcd_match"

    for pub in (snap.publisher_norm,):
        for ser in _series_norm_aliases(snap.series_norm):
            key = (pub, ser, snap.issue_norm)
            if key in index.exact:
                return "matched", [_gcd_candidate_payload(index.exact[key])]

    for ser in _series_norm_aliases(snap.series_norm):
        candidates = index.by_series_issue.get((ser, snap.issue_norm))
        if not candidates:
            continue
        if len(candidates) == 1:
            row = candidates[0][2]
            pub_norm = candidates[0][0]
            if pub_norm != snap.publisher_norm and not series_names_compatible(snap.publisher_norm, pub_norm):
                reason = "publisher_mismatch"
                collected = [_gcd_candidate_payload(row)]
                continue
        pub_matches = [
            c
            for c in candidates
            if c[0] == snap.publisher_norm or series_names_compatible(snap.publisher_norm, c[0])
        ]
        if not pub_matches:
            reason = "publisher_mismatch"
            collected.extend(_gcd_candidate_payload(c[2]) for c in candidates[:10])
            continue
        if len(pub_matches) == 1:
            continue
        year = snap.year
        if year is None:
            reason = "ambiguous_multiple_candidates"
            collected = [_gcd_candidate_payload(c[2]) for c in pub_matches[:10]]
            break
        scored = sorted(pub_matches, key=lambda c: abs((c[1] if c[1] is not None else year) - year))
        if len(scored) >= 2 and abs((scored[0][1] or year) - year) == abs((scored[1][1] or year) - year):
            reason = "ambiguous_year_tie"
            collected = [_gcd_candidate_payload(c[2]) for c in scored[:10]]
            break

    if not collected:
        for ser in _series_norm_aliases(snap.series_norm):
            candidates = index.by_series_issue.get((ser, snap.issue_norm))
            if candidates:
                collected = [_gcd_candidate_payload(c[2]) for c in candidates[:10]]
                break
    return reason, collected


@dataclass
class P1035ExceptionCollector:
    ambiguous_matches: list[dict[str, Any]] = field(default_factory=list)
    duplicate_cv_conflicts: list[dict[str, Any]] = field(default_factory=list)
    upc_conflicts: list[dict[str, Any]] = field(default_factory=list)
    validation_failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ambiguous_matches": list(self.ambiguous_matches),
            "duplicate_cv_conflicts": list(self.duplicate_cv_conflicts),
            "upc_conflicts": list(self.upc_conflicts),
            "validation_failures": list(self.validation_failures),
        }

    def summary(self) -> dict[str, int]:
        return {
            "ambiguous_matches": len(self.ambiguous_matches),
            "duplicate_cv_conflicts": len(self.duplicate_cv_conflicts),
            "upc_conflicts": len(self.upc_conflicts),
            "validation_failures": len(self.validation_failures),
            "total_manual_review": (
                len(self.ambiguous_matches)
                + len(self.duplicate_cv_conflicts)
                + len(self.upc_conflicts)
                + len(self.validation_failures)
            ),
        }


def record_duplicate_cv_conflict(
    collector: P1035ExceptionCollector,
    *,
    snap: EnrichmentIssueSnapshot,
    dup_index: dict[str, list[int]],
    scope_by_id: dict[int, EnrichmentIssueSnapshot],
) -> None:
    for cv_id in _comicvine_ids(snap.external_source_ids):
        peer_ids = dup_index.get(cv_id) or []
        if len(peer_ids) <= 1:
            continue
        peers = []
        for pid in sorted(set(int(x) for x in peer_ids)):
            ps = scope_by_id.get(pid)
            if ps is None:
                peers.append({"catalog_issue_id": pid})
            else:
                peers.append(_catalog_context_from_snap(ps))
        row = {
            **_catalog_context_from_snap(snap),
            "exception_type": "duplicate_cv_conflict",
            "reason": f"ComicVine id {cv_id} shared by {len(peer_ids)} catalog issues",
            "comicvine_issue_id": cv_id,
            "catalog_issue_ids": sorted(set(int(x) for x in peer_ids)),
            "peer_catalog_issues": peers,
        }
        collector.duplicate_cv_conflicts.append(row)
        return


def record_ambiguous_match(
    collector: P1035ExceptionCollector,
    *,
    snap: EnrichmentIssueSnapshot,
    index: _GcdIndex,
    ctx: CatalogCacheContext | None = None,
) -> None:
    reason, candidates = explain_ambiguous_gcd_lookup(index, snap)
    if reason == "matched":
        return
    collector.ambiguous_matches.append(
        {
            **_catalog_context_from_snap(snap, ctx=ctx),
            "exception_type": "ambiguous_match",
            "reason": reason,
            "gcd_candidates": candidates,
            "match_score": None,
        }
    )


def record_upc_conflict(
    collector: P1035ExceptionCollector,
    *,
    snap: EnrichmentIssueSnapshot,
    gcd_row: dict[str, Any],
    ctx: CatalogCacheContext,
    skip_reason: str,
) -> None:
    inputs = _normalize_gcd_inputs(gcd_row)
    barcode = inputs.get("barcode")
    norm = normalize_upc(str(barcode or "")) if barcode else None
    conflicting_issue: int | None = None
    if skip_reason == "upc_mapped_elsewhere" and norm:
        conflicting_issue = int(ctx.upc_to_issue.get(norm) or 0) or None
    row = {
        **_catalog_context_from_snap(snap, ctx=ctx),
        "exception_type": "upc_conflict",
        "reason": skip_reason,
        "conflicting_barcode": norm,
        "existing_conflicting_catalog_issue_id": conflicting_issue,
        "existing_conflicting_upc_id": None,
        "gcd_candidate": _gcd_candidate_payload(gcd_row),
    }
    collector.upc_conflicts.append(row)


def record_validation_failure(
    collector: P1035ExceptionCollector,
    *,
    snap: EnrichmentIssueSnapshot,
    gcd_row: dict[str, Any],
    validation_status: str,
    validation_reason: str,
) -> None:
    collector.validation_failures.append(
        {
            **_catalog_context_from_snap(snap),
            "exception_type": "validation_failure",
            "reason": validation_reason,
            "validation_status": validation_status,
            "gcd_candidate": _gcd_candidate_payload(gcd_row),
            "conflicting_barcode": _normalize_gcd_inputs(gcd_row).get("barcode"),
        }
    )


def _flatten_row_for_csv(row: dict[str, Any]) -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, val in row.items():
        if isinstance(val, (dict, list)):
            flat[key] = json.dumps(val, default=str)
        elif val is None:
            flat[key] = ""
        else:
            flat[key] = str(val)
    return flat


def write_p1035_exception_backlog(exceptions: dict[str, Any], out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int] = {}
    for name in P1035_EXCEPTION_FILES:
        rows = list(exceptions.get(name) or [])
        summary[name] = len(rows)
        (out_dir / f"{name}.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
        csv_path = out_dir / f"{name}.csv"
        if rows:
            fieldnames: list[str] = []
            for row in rows:
                for k in _flatten_row_for_csv(row).keys():
                    if k not in fieldnames:
                        fieldnames.append(k)
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow(_flatten_row_for_csv(row))
        else:
            csv_path.write_text("", encoding="utf-8")
    summary["total_manual_review"] = sum(summary.get(k, 0) for k in P1035_EXCEPTION_FILES)
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }
    (out_dir / "exception_summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return summary


def format_p1035_exception_summary(summary: dict[str, int]) -> str:
    lines = [
        "P103.5 exception backlog:",
        f"  ambiguous_matches: {summary.get('ambiguous_matches', 0):,}",
        f"  duplicate_cv_conflicts: {summary.get('duplicate_cv_conflicts', 0):,}",
        f"  upc_conflicts: {summary.get('upc_conflicts', 0):,}",
        f"  validation_failures: {summary.get('validation_failures', 0):,}",
        f"  total_manual_review: {summary.get('total_manual_review', 0):,}",
    ]
    return "\n".join(lines)


def load_exceptions_from_report_file(report_path: Path) -> dict[str, Any]:
    raw = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("report must be a JSON object")
    if isinstance(raw.get("exceptions"), dict):
        return dict(raw["exceptions"])
    inner = raw.get("report")
    if isinstance(inner, dict) and isinstance(inner.get("exceptions"), dict):
        return dict(inner["exceptions"])
    raise ValueError(
        "report has no exceptions payload; re-run dry-run or write with a current P103.5 build to collect backlog rows"
    )


def fetch_gcd_issue_row(gcd_path: Path, gcd_issue_id: int) -> dict[str, Any] | None:
    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    row = conn.execute(
        """
        SELECT i.id, p.id, p.name, s.id, s.name, i.number, i.barcode, i.key_date, s.year_began, i.title, i.notes
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE i.id = ?
        """,
        (int(gcd_issue_id),),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "issue_id": int(row[0]),
        "gcd_publisher_id": row[1],
        "publisher_name": row[2],
        "gcd_series_id": row[3],
        "series_name": row[4],
        "number": row[5],
        "barcode": row[6],
        "key_date": row[7],
        "year_began": row[8],
        "title": row[9],
        "notes": row[10],
    }


def _snap_from_db_issue(session: Session, issue: CatalogIssue) -> EnrichmentIssueSnapshot:
    series = session.get(CatalogSeries, int(issue.series_id)) if issue.series_id else None
    pub_name: str | None = None
    if issue.publisher_id:
        pub = session.get(CatalogPublisher, int(issue.publisher_id))
        pub_name = pub.name if pub else None
    elif series and series.publisher_id:
        pub = session.get(CatalogPublisher, int(series.publisher_id))
        pub_name = pub.name if pub else None
    from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
    from app.services.p103_gcd_enrichment_helpers import effective_catalog_issue_year

    year = effective_catalog_issue_year(
        year=None,
        cover_date=issue.cover_date,
        release_date=issue.release_date,
    )
    has_upc = (
        session.exec(select(CatalogUpc.id).where(CatalogUpc.issue_id == int(issue.id)).limit(1)).first()
        is not None
    )
    return EnrichmentIssueSnapshot(
        issue_id=int(issue.id or 0),
        year=year,
        publisher_id=int(issue.publisher_id) if issue.publisher_id else None,
        series_id=int(issue.series_id) if issue.series_id else None,
        publisher_norm=normalize_series_name(pub_name or ""),
        series_norm=normalize_series_name(series.name if series else ""),
        issue_norm=normalize_issue_number(issue.normalized_issue_number or issue.issue_number or ""),
        publisher_name=pub_name,
        series_name=series.name if series else None,
        issue_number=issue.issue_number,
        cover_date=issue.cover_date,
        release_date=issue.release_date,
        store_date=None,
        title=issue.title,
        description=issue.description,
        external_source_ids=dict(issue.external_source_ids or {}),
        variant_printing=None,
        variant_variant_name=None,
        has_upc=has_upc,
    )


def run_p1035_manual_attach(
    session: Session,
    *,
    catalog_issue_id: int,
    gcd_issue_id: int,
    gcd_path: Path,
    allow_upc_conflict: bool = False,
    rollback_collector: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue = session.get(CatalogIssue, int(catalog_issue_id))
    if issue is None:
        raise ValueError(f"catalog_issue_id {catalog_issue_id} not found")

    existing_gcd = extract_gcd_issue_id(issue.external_source_ids)
    if existing_gcd is not None and int(existing_gcd) != int(gcd_issue_id):
        raise ValueError(
            f"catalog issue already has GCD id {existing_gcd}; refusing overwrite (requested {gcd_issue_id})"
        )

    gcd_raw = fetch_gcd_issue_row(gcd_path, int(gcd_issue_id))
    if gcd_raw is None:
        raise ValueError(f"gcd_issue_id {gcd_issue_id} not found in {gcd_path}")

    snap = _snap_from_db_issue(session, issue)
    gcd_plan_row = gcd_row_to_plan_inputs(gcd_raw)
    learned = {str(b) for b in session.exec(select(ComicIssueBarcode.normalized_barcode)).all() if b}
    upc_map: dict[str, int] = {}
    for norm, iid in session.exec(select(CatalogUpc.normalized_upc, CatalogUpc.issue_id)).all():
        if norm and iid is not None:
            upc_map[str(norm)] = int(iid)
    from app.services.p101_catalog_cache_service import CatalogCacheMatcher

    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue=upc_map,
        learned_barcodes=learned,
    )

    plan_snap = snap
    if existing_gcd is not None and int(existing_gcd) == int(gcd_issue_id):
        ext = dict(snap.external_source_ids or {})
        ext.pop(GCD_SOURCE, None)
        plan_snap = EnrichmentIssueSnapshot(
            issue_id=snap.issue_id,
            year=snap.year,
            publisher_id=snap.publisher_id,
            series_id=snap.series_id,
            publisher_norm=snap.publisher_norm,
            series_norm=snap.series_norm,
            issue_norm=snap.issue_norm,
            publisher_name=snap.publisher_name,
            series_name=snap.series_name,
            issue_number=snap.issue_number,
            cover_date=snap.cover_date,
            release_date=snap.release_date,
            store_date=snap.store_date,
            title=snap.title,
            description=snap.description,
            external_source_ids=ext,
            variant_printing=snap.variant_printing,
            variant_variant_name=snap.variant_variant_name,
            has_upc=snap.has_upc,
        )

    planned, skip, upc_n = plan_identity_backfill(plan_snap, gcd_plan_row, ctx=ctx)
    if skip == "already_has_gcd" and existing_gcd is not None and int(existing_gcd) == int(gcd_issue_id):
        skip = None
    if skip in ("learned_barcode_conflict", "upc_mapped_elsewhere") and not allow_upc_conflict:
        raise ValueError(f"UPC conflict ({skip}); pass --allow-upc-conflict YES after manual review")
    if skip == "barcode_validation_failed":
        raise ValueError("barcode validation failed for GCD UPC; fix metadata before attach")

    variant = session.exec(
        select(CatalogVariant).where(CatalogVariant.issue_id == int(catalog_issue_id)).order_by(CatalogVariant.id.asc())
    ).first()

    before_issue = {"external_source_ids": dict(issue.external_source_ids or {})}
    learned_set = set(ctx.learned_barcodes)
    upc_map, upc_id_by_normalized = preload_catalog_upc_guards(session)

    fields_updated, upc_id, upc_created = _apply_identity_planned(
        session,
        issue,
        variant,
        planned,
        learned=learned_set,
        upc_map=upc_map,
        upc_id_by_normalized=upc_id_by_normalized,
    )
    session.commit()

    result = {
        "catalog_issue_id": int(catalog_issue_id),
        "gcd_issue_id": int(gcd_issue_id),
        "fields_updated": fields_updated,
        "inserted_upc": upc_created,
        "planned_upc": upc_n,
    }
    if upc_id is not None:
        result["upc_id"] = int(upc_id)

    if rollback_collector is not None:
        rollback_collector.setdefault("issue_snapshots", []).append(
            {
                "catalog_issue_id": int(catalog_issue_id),
                "identity_only": True,
                "before": before_issue,
            }
        )
        if upc_created and upc_id is not None:
            rollback_collector.setdefault("upc_ids", []).append(int(upc_id))

    return result
