"""P106 — automatic barcode gap resolver (GCD exact barcode match)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_cover_assets import COVER_ASSET_STATUS_PENDING, CatalogCoverAsset
from app.models.catalog_master import CatalogIssue, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode
from app.models.p105_barcode_repair import P105MissingBarcodeQueue, P105_QUEUE_PENDING
from app.models.p106_barcode_gap import (
    P106_STATUS_AUTO_ATTACHED,
    P106_STATUS_AUTO_IMPORTED,
    P106_STATUS_CONFLICT,
    P106_STATUS_REVIEW_REQUIRED,
    P106_STATUS_UNRESOLVED,
    BarcodeGapResolutionQueue,
    utc_now,
)
from app.services.barcode_scan_consensus_service import normalize_scan_preserving_supplement
from app.services.catalog_ingestion_service import (
    merge_external_ids,
    normalize_issue_number,
    normalize_series_name,
    normalize_upc,
    upsert_issue,
    upsert_publisher,
    upsert_series,
)
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.gcd_catalog_upc_insert_service import insert_catalog_upc_if_absent, preload_catalog_upc_guards
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.gcd_barcode_search_service import (
    find_gcd_rows_by_normalized_barcode,
    probe_gcd_sql_barcode_counts,
    search_gcd_barcode_fields,
)
from app.services.p1035_gcd_identity_backfill_service import _attach_gcd_meta
from app.services.p1035_gcd_identity_exception_service import fetch_gcd_issue_row
from app.services.p103_gcd_enrichment_helpers import (
    extract_gcd_issue_id,
    gcd_row_to_plan_inputs,
    parse_key_date,
    resolve_catalog_issue_id_for_gcd_match,
)
from app.services.p104_cover_hydration_service import compute_priority_for_issue, resolve_cover_url_for_issue

P106_IMPORT_REASON = "barcode_gap_auto_import"
P106_META_KEY = "_p106_barcode_gap"
P106_P1035_BATCH_SOURCE = "p1035_upc_conflicts"
DEFAULT_P1035_BATCH_REPORT = Path("data/p106/p1035_upc_conflict_resolution.json")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_scanned_barcode(raw: str) -> str:
    return normalize_scan_preserving_supplement(raw) or normalize_upc(raw) or raw.strip()


def _p106_metadata(*, scanned_barcode: str) -> dict[str, Any]:
    return {
        "source": GCD_SOURCE,
        "import_reason": P106_IMPORT_REASON,
        "scanned_barcode": scanned_barcode,
    }


def _attach_p106_metadata(issue: CatalogIssue, *, scanned_barcode: str) -> None:
    ext = dict(issue.external_source_ids or {})
    ext[P106_META_KEY] = _p106_metadata(scanned_barcode=scanned_barcode)
    issue.external_source_ids = ext


def _catalog_issue_ids_for_gcd(session: Session, gcd_issue_id: int) -> list[int]:
    out: list[int] = []
    for issue_id, ext in session.exec(select(CatalogIssue.id, CatalogIssue.external_source_ids)).all():
        if issue_id is None:
            continue
        if extract_gcd_issue_id(ext) == int(gcd_issue_id):
            out.append(int(issue_id))
    return sorted(set(out))


def resolve_catalog_issue_for_gcd_barcode(
    session: Session,
    *,
    cache_path: Path | None,
    gcd_match: dict[str, Any],
    gcd_issue_id: int,
) -> int | None:
    by_gcd = _catalog_issue_ids_for_gcd(session, int(gcd_issue_id))
    if len(by_gcd) == 1:
        return by_gcd[0]
    if len(by_gcd) > 1:
        return None
    if cache_path is not None and cache_path.is_file():
        resolved = resolve_catalog_issue_id_for_gcd_match(
            cache_path,
            publisher=str(gcd_match.get("publisher") or ""),
            series=str(gcd_match.get("series") or ""),
            issue_number=str(gcd_match.get("issue_number") or ""),
        )
        if resolved is not None:
            issue_id = int(resolved)
            if session.get(CatalogIssue, issue_id) is not None:
                return issue_id
    from app.models.catalog_master import CatalogSeries

    number = str(gcd_match.get("issue_number") or "")
    series = str(gcd_match.get("series") or "")
    if not series or not number:
        return None
    series_norm = normalize_series_name(series)
    iss_norm = normalize_issue_number(number)
    candidates = list(
        session.exec(
            select(CatalogIssue.id)
            .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
            .where(CatalogSeries.normalized_name == series_norm)
            .where(CatalogIssue.normalized_issue_number == iss_norm)
        ).all()
    )
    if len(candidates) == 1:
        return int(candidates[0])
    return None


def _upc_conflict(session: Session, normalized: str, target_issue_id: int) -> str | None:
    upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    if upc is not None and upc.issue_id is not None and int(upc.issue_id) != int(target_issue_id):
        return f"catalog_upc maps to issue #{upc.issue_id}"
    learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized)
    ).first()
    if learned is not None and int(learned.catalog_issue_id) != int(target_issue_id):
        return f"learned_barcode maps to issue #{learned.catalog_issue_id}"
    return None


def _already_in_catalog(session: Session, normalized: str) -> dict[str, Any] | None:
    upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    if upc is not None and upc.issue_id is not None:
        return {"kind": "catalog_upc", "catalog_issue_id": int(upc.issue_id), "catalog_upc_id": upc.id}
    learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized)
    ).first()
    if learned is not None:
        return {"kind": "learned_barcode", "catalog_issue_id": int(learned.catalog_issue_id)}
    return None


def queue_barcode_gap_review(
    session: Session,
    *,
    barcode: str,
    status: str,
    reason: str,
    gcd_issue_id: int | None = None,
    catalog_issue_id: int | None = None,
    details: dict[str, Any] | None = None,
    scanner_session_id: int | None = None,
    photo_import_id: int | None = None,
) -> BarcodeGapResolutionQueue:
    normalized = _normalize_scanned_barcode(barcode)
    row = BarcodeGapResolutionQueue(
        barcode=barcode.strip(),
        normalized_barcode=normalized,
        status=status,
        reason=reason,
        gcd_issue_id=gcd_issue_id,
        catalog_issue_id=catalog_issue_id,
        scanner_session_id=scanner_session_id,
        photo_import_id=photo_import_id,
        details_json=details or {},
    )
    session.add(row)
    session.flush()
    return row


def _queue_cover_hydration_if_url(session: Session, issue_id: int) -> bool:
    issue = session.get(CatalogIssue, int(issue_id))
    if issue is None:
        return False
    url, source = resolve_cover_url_for_issue(session, issue)
    if not url:
        return False
    existing = session.exec(
        select(CatalogCoverAsset).where(
            CatalogCoverAsset.catalog_issue_id == int(issue_id),
            CatalogCoverAsset.source_url == url,
        )
    ).first()
    if existing is not None:
        return False
    score, tier = compute_priority_for_issue(session, issue)
    now = utc_now()
    session.add(
        CatalogCoverAsset(
            catalog_issue_id=int(issue_id),
            source=source or GCD_SOURCE,
            source_url=url,
            status=COVER_ASSET_STATUS_PENDING,
            priority_score=score,
            priority_tier=tier,
            created_at=now,
            updated_at=now,
        )
    )
    session.flush()
    return True


def auto_attach_gcd_identity_for_barcode(
    session: Session,
    *,
    catalog_issue_id: int,
    gcd_issue_id: int,
    barcode: str,
    gcd_path: Path,
    rollback_collector: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Exact-barcode attach: GCD ids + catalog_upc without P103.5 series/publisher text matching."""
    normalized = _normalize_scanned_barcode(barcode)
    issue = session.get(CatalogIssue, int(catalog_issue_id))
    if issue is None:
        raise ValueError(f"catalog_issue_id {catalog_issue_id} not found")

    existing_gcd = extract_gcd_issue_id(issue.external_source_ids)
    if existing_gcd is not None and int(existing_gcd) != int(gcd_issue_id):
        raise ValueError(f"catalog issue already has GCD id {existing_gcd}")

    conflict = _upc_conflict(session, normalized, int(catalog_issue_id))
    if conflict:
        raise ValueError(conflict)

    gcd_raw = fetch_gcd_issue_row(gcd_path, int(gcd_issue_id))
    if gcd_raw is None:
        raise ValueError(f"gcd_issue_id {gcd_issue_id} not found")

    inputs = gcd_row_to_plan_inputs(gcd_raw)
    if dry_run:
        return {
            "action": "auto_attach",
            "catalog_issue_id": int(catalog_issue_id),
            "gcd_issue_id": int(gcd_issue_id),
            "normalized_barcode": normalized,
            "dry_run": True,
        }

    before = {"external_source_ids": dict(issue.external_source_ids or {})}
    variant = session.exec(
        select(CatalogVariant).where(CatalogVariant.issue_id == int(catalog_issue_id)).order_by(CatalogVariant.id.asc())
    ).first()

    issue.external_source_ids = merge_external_ids(issue.external_source_ids, GCD_SOURCE, int(gcd_issue_id))
    issue.external_source_ids = _attach_gcd_meta(
        issue.external_source_ids,
        series_id=inputs.get("gcd_series_id"),
        publisher_id=inputs.get("gcd_publisher_id"),
    )
    _attach_p106_metadata(issue, scanned_barcode=normalized)
    session.add(issue)

    learned = {str(b) for b in session.exec(select(ComicIssueBarcode.normalized_barcode)).all() if b}
    upc_map, upc_id_by_normalized = preload_catalog_upc_guards(session)
    upc_id, upc_created = insert_catalog_upc_if_absent(
        session,
        raw_upc=normalized,
        issue_id=int(catalog_issue_id),
        variant_id=int(variant.id) if variant and variant.id is not None else None,
        learned=learned,
        upc_map=upc_map,
        upc_id_by_normalized=upc_id_by_normalized,
    )
    if upc_id is None and normalized not in upc_map:
        raise ValueError("catalog_upc insert blocked (conflict or learned guard)")

    if rollback_collector is not None:
        rollback_collector.setdefault("issue_snapshots", []).append(
            {"catalog_issue_id": int(catalog_issue_id), "before": before, "p106": True}
        )
        if upc_created and upc_id is not None:
            rollback_collector.setdefault("upc_ids", []).append(int(upc_id))

    return {
        "action": "auto_attach",
        "catalog_issue_id": int(catalog_issue_id),
        "gcd_issue_id": int(gcd_issue_id),
        "catalog_upc_id": upc_id,
        "catalog_upc_created": upc_created,
        "normalized_barcode": normalized,
    }


def auto_import_gcd_issue_for_barcode(
    session: Session,
    *,
    barcode: str,
    gcd_issue_id: int,
    gcd_path: Path,
    rollback_collector: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized = _normalize_scanned_barcode(barcode)
    gcd_raw = fetch_gcd_issue_row(gcd_path, int(gcd_issue_id))
    if gcd_raw is None:
        raise ValueError(f"gcd_issue_id {gcd_issue_id} not found")
    inputs = gcd_row_to_plan_inputs(gcd_raw)

    existing = _catalog_issue_ids_for_gcd(session, int(gcd_issue_id))
    if existing:
        raise ValueError(f"catalog issue already exists for gcd_issue_id {gcd_issue_id}")

    if dry_run:
        return {
            "action": "auto_import",
            "gcd_issue_id": int(gcd_issue_id),
            "normalized_barcode": normalized,
            "dry_run": True,
            "series": inputs.get("series"),
            "issue_number": inputs.get("issue_number"),
        }

    pub_name = str(inputs.get("publisher") or "Unknown")
    focus = canonical_focus_publisher_label(pub_name) or pub_name
    pub_row = upsert_publisher(
        session,
        name=focus,
        source=GCD_SOURCE,
        external_id=inputs.get("gcd_publisher_id"),
    )
    cal, _year, _ = parse_key_date(str(inputs.get("key_date") or ""), inputs.get("year"))
    series_row = upsert_series(
        session,
        name=str(inputs.get("series") or "Unknown"),
        publisher_id=int(pub_row.id or 0),
        source=GCD_SOURCE,
        external_id=inputs.get("gcd_series_id"),
        start_year=inputs.get("year"),
    )
    issue_row = upsert_issue(
        session,
        series_id=int(series_row.id or 0),
        publisher_id=int(pub_row.id or 0),
        issue_number=str(inputs.get("issue_number") or "?"),
        source=GCD_SOURCE,
        external_id=int(gcd_issue_id),
        title=inputs.get("title"),
        cover_date=cal,
        source_confidence=Decimal("0.95"),
    )
    issue_row.external_source_ids = _attach_gcd_meta(
        issue_row.external_source_ids,
        series_id=inputs.get("gcd_series_id"),
        publisher_id=inputs.get("gcd_publisher_id"),
    )
    _attach_p106_metadata(issue_row, scanned_barcode=normalized)
    session.add(issue_row)
    session.flush()

    variant = CatalogVariant(
        issue_id=int(issue_row.id or 0),
        variant_name="Standard",
        external_source_ids={"_primary_source": GCD_SOURCE},
    )
    session.add(variant)
    session.flush()

    learned = {str(b) for b in session.exec(select(ComicIssueBarcode.normalized_barcode)).all() if b}
    upc_map, upc_id_by_normalized = preload_catalog_upc_guards(session)
    upc_id, upc_created = insert_catalog_upc_if_absent(
        session,
        raw_upc=normalized,
        issue_id=int(issue_row.id or 0),
        variant_id=int(variant.id) if variant.id is not None else None,
        learned=learned,
        upc_map=upc_map,
        upc_id_by_normalized=upc_id_by_normalized,
    )

    cover_queued = _queue_cover_hydration_if_url(session, int(issue_row.id or 0))

    if rollback_collector is not None:
        rollback_collector.setdefault("created_issue_ids", []).append(int(issue_row.id or 0))
        rollback_collector.setdefault("created_variant_ids", []).append(int(variant.id or 0))
        if upc_created and upc_id is not None:
            rollback_collector.setdefault("upc_ids", []).append(int(upc_id))

    return {
        "action": "auto_import",
        "catalog_issue_id": int(issue_row.id or 0),
        "gcd_issue_id": int(gcd_issue_id),
        "catalog_upc_id": upc_id,
        "catalog_upc_created": upc_created,
        "cover_hydration_queued": cover_queued,
        "normalized_barcode": normalized,
        "rollback": rollback_collector,
    }


def diagnose_barcode_gap(
    session: Session,
    *,
    barcode: str,
    gcd_path: Path,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    normalized = _normalize_scanned_barcode(barcode)
    known = _already_in_catalog(session, normalized)
    sql_probe = probe_gcd_sql_barcode_counts(gcd_path, normalized)

    if not gcd_path.is_file():
        if known:
            return {
                "normalized_barcode": normalized,
                "already_resolved": True,
                "ready_to_auto_import": False,
                "resolution": known,
            }
        return {
            "normalized_barcode": normalized,
            "ready_to_auto_import": False,
            "gcd_match_count": 0,
            "status": P106_STATUS_UNRESOLVED,
            "reason": "gcd_database_missing",
            **sql_probe,
        }

    gcd_search = search_gcd_barcode_fields(gcd_path, normalized)
    gcd_matches = find_gcd_rows_by_normalized_barcode(gcd_path, normalized)
    count = len(gcd_matches)
    lookup = gcd_search.to_dict()
    base: dict[str, Any] = {
        "normalized_barcode": normalized,
        "already_resolved": False,
        "gcd_match_count": count,
        "gcd_matches": gcd_matches,
        "exact_barcode_path": True,
        "bypass_p1035_text_matching": count == 1,
        "searched_full_barcode": lookup["searched_full_barcode"],
        "searched_upc12": lookup["searched_upc12"],
        "searched_supplement": lookup["searched_supplement"],
        "gcd_exact_hits": lookup["gcd_exact_hits"],
        "gcd_prefix_hits": lookup["gcd_prefix_hits"],
        "gcd_notes_hits": lookup["gcd_notes_hits"],
        "gcd_lookup_final_reason": lookup["final_reason"],
        **sql_probe,
    }

    if count == 0:
        if known:
            base.update(
                {
                    "already_resolved": True,
                    "ready_to_auto_import": False,
                    "resolution": known,
                }
            )
            return base
        base.update(
            {
                "ready_to_auto_import": False,
                "status": P106_STATUS_UNRESOLVED,
                "reason": "no_gcd_barcode_match",
                "final_reason": "no_gcd_barcode_match",
                "next_source": "comicvine_fallback_or_external_import",
                "proposed_action": None,
            }
        )
        return base

    if count > 1:
        base.update(
            {
                "ready_to_auto_import": False,
                "status": P106_STATUS_REVIEW_REQUIRED,
                "reason": "multiple_gcd_issues_same_barcode",
                "proposed_action": None,
            }
        )
        return base

    match = gcd_matches[0]
    gcd_issue_id = int(match["gcd_issue_id"])
    catalog_id = resolve_catalog_issue_for_gcd_barcode(
        session,
        cache_path=cache_path,
        gcd_match=match,
        gcd_issue_id=gcd_issue_id,
    )
    by_gcd = _catalog_issue_ids_for_gcd(session, gcd_issue_id)
    if len(by_gcd) > 1:
        base.update(
            {
                "ready_to_auto_import": False,
                "status": P106_STATUS_REVIEW_REQUIRED,
                "reason": "multiple_catalog_issues_same_gcd_id",
                "proposed_action": None,
            }
        )
        return base

    if known:
        known_issue = int(known["catalog_issue_id"])
        if catalog_id is None or known_issue == int(catalog_id):
            return {
                "normalized_barcode": normalized,
                "already_resolved": True,
                "ready_to_auto_import": False,
                "resolution": known,
                "gcd_issue_id": gcd_issue_id,
                "catalog_issue_id": known_issue,
            }
        base.update(
            {
                "ready_to_auto_import": False,
                "status": P106_STATUS_CONFLICT,
                "reason": f"{known['kind']} maps to issue #{known_issue}",
                "catalog_issue_id": catalog_id,
                "gcd_issue_id": gcd_issue_id,
                "proposed_action": "auto_attach" if catalog_id else "auto_import",
            }
        )
        return base

    if catalog_id is not None:
        conflict = _upc_conflict(session, normalized, int(catalog_id))
        if conflict:
            base.update(
                {
                    "ready_to_auto_import": False,
                    "status": P106_STATUS_CONFLICT,
                    "reason": conflict,
                    "catalog_issue_id": catalog_id,
                    "gcd_issue_id": gcd_issue_id,
                    "proposed_action": "auto_attach",
                }
            )
            return base
        base.update(
            {
                "ready_to_auto_import": True,
                "status": P106_STATUS_AUTO_ATTACHED,
                "reason": "unique_gcd_barcode_match",
                "catalog_issue_id": catalog_id,
                "gcd_issue_id": gcd_issue_id,
                "proposed_action": "auto_attach",
            }
        )
        return base

    base.update(
        {
            "ready_to_auto_import": True,
            "status": P106_STATUS_AUTO_IMPORTED,
            "reason": "unique_gcd_barcode_match_no_catalog_issue",
            "gcd_issue_id": gcd_issue_id,
            "proposed_action": "auto_import",
        }
    )
    return base


def resolve_barcode_gap(
    session: Session,
    *,
    barcode: str,
    gcd_path: Path,
    cache_path: Path | None = None,
    confirm_write: bool = False,
    scanner_session_id: int | None = None,
    photo_import_id: int | None = None,
    intake_item_id: int | None = None,
    diagnosis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diag = diagnosis or diagnose_barcode_gap(session, barcode=barcode, gcd_path=gcd_path, cache_path=cache_path)
    if diag.get("already_resolved"):
        return {"diagnosis": diag, "written": False, "result": diag.get("resolution")}

    if not diag.get("ready_to_auto_import"):
        if confirm_write:
            row = queue_barcode_gap_review(
                session,
                barcode=barcode,
                status=str(diag.get("status") or P106_STATUS_UNRESOLVED),
                reason=str(diag.get("reason") or "not_ready"),
                gcd_issue_id=diag.get("gcd_issue_id"),
                catalog_issue_id=diag.get("catalog_issue_id"),
                details={"diagnosis": diag, "intake_item_id": intake_item_id},
                scanner_session_id=scanner_session_id,
                photo_import_id=photo_import_id,
            )
            session.commit()
            return {"diagnosis": diag, "written": True, "queue_id": row.id}
        return {"diagnosis": diag, "written": False}

    action = diag.get("proposed_action")
    gcd_issue_id = int(diag["gcd_issue_id"])
    rollback: dict[str, Any] = {"import_reason": P106_IMPORT_REASON, "scanned_barcode": diag["normalized_barcode"]}

    if not confirm_write:
        if action == "auto_attach":
            preview = auto_attach_gcd_identity_for_barcode(
                session,
                catalog_issue_id=int(diag["catalog_issue_id"]),
                gcd_issue_id=gcd_issue_id,
                barcode=barcode,
                gcd_path=gcd_path,
                dry_run=True,
            )
        else:
            preview = auto_import_gcd_issue_for_barcode(
                session,
                barcode=barcode,
                gcd_issue_id=gcd_issue_id,
                gcd_path=gcd_path,
                dry_run=True,
            )
        return {"diagnosis": diag, "written": False, "preview": preview}

    if action == "auto_attach":
        result = auto_attach_gcd_identity_for_barcode(
            session,
            catalog_issue_id=int(diag["catalog_issue_id"]),
            gcd_issue_id=gcd_issue_id,
            barcode=barcode,
            gcd_path=gcd_path,
            rollback_collector=rollback,
        )
        status = P106_STATUS_AUTO_ATTACHED
    else:
        result = auto_import_gcd_issue_for_barcode(
            session,
            barcode=barcode,
            gcd_issue_id=gcd_issue_id,
            gcd_path=gcd_path,
            rollback_collector=rollback,
        )
        status = P106_STATUS_AUTO_IMPORTED

    row = queue_barcode_gap_review(
        session,
        barcode=barcode,
        status=status,
        reason=str(diag.get("reason") or "resolved"),
        gcd_issue_id=gcd_issue_id,
        catalog_issue_id=result.get("catalog_issue_id"),
        details={"diagnosis": diag, "result": result, "rollback": rollback, "intake_item_id": intake_item_id},
        scanner_session_id=scanner_session_id,
        photo_import_id=photo_import_id,
    )
    row.resolved_at = _utc_now()
    row.catalog_upc_id = result.get("catalog_upc_id")
    session.add(row)
    session.commit()
    return {"diagnosis": diag, "written": True, "result": result, "queue_id": row.id, "rollback": rollback}


def resolve_barcode_gaps_from_scanner_queue(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path | None,
    limit: int,
    confirm_write: bool,
) -> dict[str, Any]:
    rows = list(
        session.exec(
            select(P105MissingBarcodeQueue)
            .where(P105MissingBarcodeQueue.status == P105_QUEUE_PENDING)
            .order_by(P105MissingBarcodeQueue.id.asc())
            .limit(max(1, limit))
        ).all()
    )
    outcomes: list[dict[str, Any]] = []
    for row in rows:
        outcomes.append(
            resolve_barcode_gap(
                session,
                barcode=row.barcode,
                gcd_path=gcd_path,
                cache_path=cache_path,
                confirm_write=confirm_write,
                intake_item_id=row.intake_item_id,
            )
        )
    return {"processed": len(outcomes), "outcomes": outcomes}


def barcode_gap_action_from_diagnosis(diagnosis: dict[str, Any]) -> str | None:
    if diagnosis.get("ready_to_auto_import"):
        return "auto_import_available"
    status = diagnosis.get("status")
    if status in {P106_STATUS_REVIEW_REQUIRED, P106_STATUS_CONFLICT}:
        return "review_required"
    if status == P106_STATUS_UNRESOLVED or diagnosis.get("gcd_match_count", 0) == 0:
        return "comicvine_fallback"
    return None


_P1061_BARCODE_GAP_RAW_OCR_MAX = 500
_P1061_BARCODE_GAP_CANDIDATE_MAX = 10


def _truncate_barcode_gap_text(value: Any, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _bound_barcode_gap_recovery_hints(hints: Any) -> dict[str, Any] | None:
    if not isinstance(hints, dict):
        return None
    bounded = dict(hints)
    bounded["raw_ocr_text_excerpt"] = _truncate_barcode_gap_text(
        bounded.get("raw_ocr_text_excerpt"),
        max_len=_P1061_BARCODE_GAP_RAW_OCR_MAX,
    )
    return bounded


def _bound_barcode_gap_instrumentation(inst: Any) -> dict[str, Any] | None:
    if not isinstance(inst, dict):
        return None
    bounded = {key: value for key, value in inst.items() if key not in {"image_bytes", "full_image"}}
    for list_key in ("gcd_candidates", "fingerprint_top_hits", "fingerprint_candidates", "candidates_scored"):
        raw_list = bounded.get(list_key)
        if isinstance(raw_list, list):
            bounded[list_key] = raw_list[:_P1061_BARCODE_GAP_CANDIDATE_MAX]
    pick = bounded.get("pick_decision")
    if isinstance(pick, dict):
        pick_copy = dict(pick)
        scored = pick_copy.get("candidates_scored")
        if isinstance(scored, list):
            pick_copy["candidates_scored"] = scored[:_P1061_BARCODE_GAP_CANDIDATE_MAX]
        bounded["pick_decision"] = pick_copy
    return bounded


def _p106_1_observability_from_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    hints = diagnosis.get("recovery_hints") if isinstance(diagnosis.get("recovery_hints"), dict) else {}
    inst = diagnosis.get("p106_1_instrumentation") if isinstance(diagnosis.get("p106_1_instrumentation"), dict) else {}

    fp_count = diagnosis.get("fingerprint_candidate_count")
    if fp_count is None:
        fp_count = inst.get("fingerprint_candidate_count")
    if fp_count is None and isinstance(inst.get("fingerprint_top_hits"), list):
        fp_count = len(inst["fingerprint_top_hits"])

    raw_excerpt = hints.get("raw_ocr_text_excerpt")
    if raw_excerpt is None:
        raw_excerpt = diagnosis.get("raw_ocr_text_excerpt")

    return {
        "recovery_stage": diagnosis.get("recovery_stage"),
        "recovery_reason": diagnosis.get("recovery_reason"),
        "recovery_block_reason": diagnosis.get("recovery_block_reason"),
        "recovery_hints": _bound_barcode_gap_recovery_hints(hints),
        "p106_1_instrumentation": _bound_barcode_gap_instrumentation(inst),
        "p106_1_skipped": diagnosis.get("p106_1_skipped"),
        "ocr_title": hints.get("ocr_title") or diagnosis.get("ocr_title"),
        "ocr_issue_number": hints.get("ocr_issue_number") or diagnosis.get("ocr_issue_number"),
        "ocr_publisher": hints.get("ocr_publisher") or diagnosis.get("ocr_publisher"),
        "ocr_confidence": hints.get("ocr_confidence") if hints.get("ocr_confidence") is not None else diagnosis.get("ocr_confidence"),
        "raw_ocr_text_excerpt": _truncate_barcode_gap_text(raw_excerpt, max_len=_P1061_BARCODE_GAP_RAW_OCR_MAX),
        "facsimile_or_reprint": hints.get("facsimile_or_reprint")
        if hints.get("facsimile_or_reprint") is not None
        else diagnosis.get("facsimile_or_reprint"),
        "series_hint_reliable": hints.get("series_hint_reliable")
        if hints.get("series_hint_reliable") is not None
        else diagnosis.get("series_hint_reliable"),
        "fingerprint_candidate_count": fp_count,
    }


def barcode_gap_payload_from_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "ready_to_auto_import": diagnosis.get("ready_to_auto_import"),
        "status": diagnosis.get("status"),
        "reason": diagnosis.get("reason"),
        "final_reason": diagnosis.get("final_reason") or diagnosis.get("gcd_lookup_final_reason"),
        "proposed_action": diagnosis.get("proposed_action"),
        "action": barcode_gap_action_from_diagnosis(diagnosis),
        "gcd_match_count": diagnosis.get("gcd_match_count"),
        "gcd_issue_id": diagnosis.get("gcd_issue_id"),
        "catalog_issue_id": diagnosis.get("catalog_issue_id"),
        "gcd_series": _gcd_display_series(diagnosis),
        "gcd_issue_number": _gcd_display_issue_number(diagnosis),
        "gcd_publisher": _gcd_display_publisher(diagnosis),
    }
    payload.update(_p106_1_observability_from_diagnosis(diagnosis))
    return payload


def _gcd_display_series(diagnosis: dict[str, Any]) -> str | None:
    matches = diagnosis.get("gcd_matches") or []
    if matches and isinstance(matches[0], dict):
        series = matches[0].get("series")
        return str(series).strip() if series else None
    hits = diagnosis.get("gcd_exact_hits") or []
    if hits and isinstance(hits[0], dict):
        series = hits[0].get("series")
        return str(series).strip() if series else None
    return None


def _gcd_display_issue_number(diagnosis: dict[str, Any]) -> str | None:
    matches = diagnosis.get("gcd_matches") or []
    if matches and isinstance(matches[0], dict):
        num = matches[0].get("issue_number")
        return str(num).strip() if num else None
    hits = diagnosis.get("gcd_exact_hits") or []
    if hits and isinstance(hits[0], dict):
        num = hits[0].get("issue_number")
        return str(num).strip() if num else None
    return None


def _gcd_display_publisher(diagnosis: dict[str, Any]) -> str | None:
    matches = diagnosis.get("gcd_matches") or []
    if matches and isinstance(matches[0], dict):
        pub = matches[0].get("publisher")
        return str(pub).strip() if pub else None
    hits = diagnosis.get("gcd_exact_hits") or []
    if hits and isinstance(hits[0], dict):
        pub = hits[0].get("publisher")
        return str(pub).strip() if pub else None
    return None


def apply_barcode_gap_display_to_intake_item(item: Any, diagnosis: dict[str, Any]) -> None:
    series = _gcd_display_series(diagnosis)
    issue_number = _gcd_display_issue_number(diagnosis)
    publisher = _gcd_display_publisher(diagnosis)
    if series and not (item.matched_series or "").strip():
        item.matched_series = series
    if issue_number and not (item.matched_issue_number or "").strip():
        item.matched_issue_number = issue_number
    if publisher and not (item.matched_publisher or "").strip():
        item.matched_publisher = publisher
    key_date = None
    fallback_year: int | None = None
    matches = diagnosis.get("gcd_matches") or []
    if matches and isinstance(matches[0], dict):
        key_date = matches[0].get("key_date")
        yb = matches[0].get("year_began")
        if yb is not None:
            try:
                fallback_year = int(yb)
            except (TypeError, ValueError):
                fallback_year = None
    if key_date and not (item.matched_year or "").strip():
        _, year, _ = parse_key_date(str(key_date), fallback_year)
        if year is not None:
            item.matched_year = str(year)


def should_auto_resolve_barcode_gap_on_scan(diagnosis: dict[str, Any]) -> bool:
    if not diagnosis.get("ready_to_auto_import"):
        return False
    if int(diagnosis.get("gcd_match_count") or 0) != 1:
        return False
    status = diagnosis.get("status")
    return status in {P106_STATUS_AUTO_IMPORTED, P106_STATUS_AUTO_ATTACHED}


def merge_barcode_gap_into_barcode_read(barcode_read_json: str | None, diagnosis: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    if barcode_read_json:
        try:
            parsed = json.loads(barcode_read_json)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}
    payload["barcode_gap"] = barcode_gap_payload_from_diagnosis(diagnosis)
    return json.dumps(payload)


def _parse_int_field(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _parse_gcd_candidate(raw: str | dict | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw or not str(raw).strip():
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_p1035_upc_conflict_rows(csv_path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"P103.5 UPC conflicts CSV not found: {csv_path}")
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            barcode = (raw.get("conflicting_barcode") or raw.get("barcode") or "").strip()
            catalog_issue_id = _parse_int_field(raw.get("catalog_issue_id"))
            if not barcode and catalog_issue_id is None:
                continue
            gcd_candidate = _parse_gcd_candidate(raw.get("gcd_candidate"))
            gcd_issue_id = _parse_int_field(str(gcd_candidate.get("gcd_issue_id") or ""))
            dedupe_key = (normalize_upc(barcode) or barcode, catalog_issue_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append(
                {
                    "barcode": barcode,
                    "catalog_issue_id": catalog_issue_id,
                    "gcd_issue_id": gcd_issue_id,
                    "p1035_reason": raw.get("reason") or "",
                    "existing_conflicting_catalog_issue_id": _parse_int_field(
                        raw.get("existing_conflicting_catalog_issue_id")
                    ),
                    "raw_row": {k: v for k, v in raw.items()},
                }
            )
            if len(out) >= max(1, limit):
                break
    return out


def classify_p106_batch_outcome(outcome: dict[str, Any], *, dry_run: bool) -> str:
    if outcome.get("error"):
        return "errors"
    diag = outcome.get("diagnosis") or {}
    if diag.get("already_resolved"):
        return "already_resolved"
    status = diag.get("status")
    if status == P106_STATUS_REVIEW_REQUIRED:
        return "review_required"
    if status == P106_STATUS_CONFLICT:
        return "conflicts"
    if status == P106_STATUS_UNRESOLVED:
        return "unresolved"
    if outcome.get("written") and outcome.get("result"):
        action = (outcome.get("result") or {}).get("action")
        if action == "auto_attach":
            return "auto_attached"
        if action == "auto_import":
            return "auto_imported"
    if dry_run and diag.get("ready_to_auto_import"):
        proposed = diag.get("proposed_action")
        if proposed == "auto_attach":
            return "auto_attached"
        if proposed == "auto_import":
            return "auto_imported"
    if outcome.get("written") and not outcome.get("result"):
        if status == P106_STATUS_CONFLICT:
            return "conflicts"
        if status == P106_STATUS_REVIEW_REQUIRED:
            return "review_required"
        return "unresolved"
    return "unresolved"


def _empty_p1035_batch_counts() -> dict[str, int]:
    return {
        "scanned": 0,
        "auto_attached": 0,
        "auto_imported": 0,
        "already_resolved": 0,
        "unresolved": 0,
        "review_required": 0,
        "conflicts": 0,
        "errors": 0,
    }


def resolve_p1035_upc_conflicts_from_csv(
    session: Session,
    *,
    csv_path: Path,
    gcd_path: Path,
    cache_path: Path | None,
    limit: int,
    confirm_write: bool,
    dry_run: bool = False,
    report_path: Path | None = None,
) -> dict[str, Any]:
    rows = load_p1035_upc_conflict_rows(csv_path, limit=limit)
    counts = _empty_p1035_batch_counts()
    outcomes: list[dict[str, Any]] = []
    rollbacks: list[dict[str, Any]] = []
    write_enabled = confirm_write and not dry_run

    for row in rows:
        counts["scanned"] += 1
        barcode = row.get("barcode") or ""
        if not str(barcode).strip():
            bucket = "errors"
            outcome: dict[str, Any] = {"error": "missing_barcode", "p1035": row}
        else:
            try:
                outcome = resolve_barcode_gap(
                    session,
                    barcode=str(barcode),
                    gcd_path=gcd_path,
                    cache_path=cache_path,
                    confirm_write=write_enabled,
                )
                outcome["p1035"] = row
                if row.get("catalog_issue_id") is not None:
                    diag = outcome.get("diagnosis") or {}
                    diag_catalog = diag.get("catalog_issue_id")
                    if diag_catalog is not None and int(diag_catalog) != int(row["catalog_issue_id"]):
                        outcome.setdefault("p1035_warnings", []).append(
                            "csv_catalog_issue_id_differs_from_p106_target"
                        )
            except Exception as exc:  # noqa: BLE001
                outcome = {"error": str(exc), "p1035": row}

            bucket = classify_p106_batch_outcome(outcome, dry_run=dry_run or not write_enabled)
            rb = outcome.get("rollback")
            if isinstance(rb, dict) and rb:
                rollbacks.append({"barcode": barcode, "rollback": rb, "p1035": row})

        counts[bucket] = counts.get(bucket, 0) + 1
        outcomes.append({"bucket": bucket, **outcome})

    report = {
        "report_at": datetime.now(timezone.utc).isoformat(),
        "source": P106_P1035_BATCH_SOURCE,
        "csv_path": str(csv_path),
        "gcd_database": str(gcd_path),
        "dry_run": dry_run or not write_enabled,
        "confirm_write": write_enabled,
        "limit": limit,
        "counts": counts,
        "outcomes": outcomes,
        "rollbacks": rollbacks,
    }
    out_path = report_path or DEFAULT_P1035_BATCH_REPORT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report
