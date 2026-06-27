"""P103.6 — targeted GCD identity exception resolution (no bulk title/year attach)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogUpc
from app.services.p106_barcode_gap_resolver_service import (
    classify_p106_batch_outcome,
    diagnose_barcode_gap,
    resolve_p1035_upc_conflicts_from_csv,
)
from app.services.p1035_gcd_identity_backfill_service import (
    _cv_duplicate_conflict,
    build_comicvine_duplicate_index,
    lookup_gcd_for_catalog,
    plan_identity_backfill,
)
from app.services.p1035_gcd_identity_exception_service import (
    _snap_from_db_issue,
    run_p1035_manual_attach,
    write_p1035_exception_backlog,
)
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p103_gcd_enrichment_fast import load_gcd_index_for_enrichment
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id

P1036_CV_META = "_p1036_cv_duplicate_resolution"
STRONG_AMBIGUOUS_SIGNALS = frozenset(
    {"exact_barcode", "exact_comicvine_crossref", "exact_external_source_id"}
)


@dataclass
class P1036ResolutionCounts:
    duplicate_cv_repaired: int = 0
    duplicate_cv_still_conflict: int = 0
    ambiguous_resolved: int = 0
    ambiguous_still_ambiguous: int = 0
    upc_p106_resolved: int = 0
    upc_review_required: int = 0
    p1035_retry_resolved: int = 0
    p1035_retry_still_blocked: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "duplicate_cv_repaired": self.duplicate_cv_repaired,
            "duplicate_cv_still_conflict": self.duplicate_cv_still_conflict,
            "ambiguous_resolved": self.ambiguous_resolved,
            "ambiguous_still_ambiguous": self.ambiguous_still_ambiguous,
            "upc_p106_resolved": self.upc_p106_resolved,
            "upc_review_required": self.upc_review_required,
            "p1035_retry_resolved": self.p1035_retry_resolved,
            "p1035_retry_still_blocked": self.p1035_retry_still_blocked,
        }


@dataclass
class P1036ResolutionReport:
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dry_run: bool = True
    counts: P1036ResolutionCounts = field(default_factory=P1036ResolutionCounts)
    duplicate_cv_outcomes: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_outcomes: list[dict[str, Any]] = field(default_factory=list)
    upc_outcomes: list[dict[str, Any]] = field(default_factory=list)
    final_exceptions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "dry_run": self.dry_run,
            "counts": self.counts.to_dict(),
            "duplicate_cv_outcomes": self.duplicate_cv_outcomes,
            "ambiguous_outcomes": self.ambiguous_outcomes,
            "upc_outcomes": self.upc_outcomes,
            "final_exceptions": self.final_exceptions,
        }


def _parse_json_cell(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def load_exception_csv(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Exception CSV not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            if not raw:
                continue
            row = dict(raw)
            for key in (
                "gcd_candidates",
                "peer_catalog_issues",
                "catalog_issue_ids",
                "existing_external_source_ids",
                "gcd_candidate",
            ):
                if key in row:
                    row[key] = _parse_json_cell(row.get(key))
            if row.get("has_upc") in ("True", "true", "1"):
                row["has_upc"] = True
            elif row.get("has_upc") in ("False", "false", "0"):
                row["has_upc"] = False
            if row.get("catalog_issue_id"):
                row["catalog_issue_id"] = int(row["catalog_issue_id"])
            if row.get("year") not in (None, ""):
                try:
                    row["year"] = int(row["year"])
                except (TypeError, ValueError):
                    pass
            rows.append(row)
    return rows


def _shared_comicvine_id(row: dict[str, Any]) -> str | None:
    reason = str(row.get("reason") or "")
    if "ComicVine id" in reason:
        parts = reason.split("ComicVine id", 1)[-1].strip().split()
        if parts:
            token = parts[0].strip()
            return token if token.isdigit() else None
    cv = row.get("comicvine_issue_id")
    return str(cv).strip() if cv not in (None, "") else None


def score_duplicate_cv_peer(peer: dict[str, Any], *, shared_cv_id: str) -> int:
    ext = peer.get("existing_external_source_ids") or {}
    if not isinstance(ext, dict):
        ext = {}
    cv_map = ext.get("COMICVINE") or {}
    if not isinstance(cv_map, dict):
        cv_map = {}
    cv_keys = [str(k) for k in cv_map.keys()]
    score = 0
    score += len(cv_keys) * 8
    if peer.get("has_upc"):
        score += 25
    if peer.get("existing_barcode"):
        score += 20
    if extract_gcd_issue_id(ext):
        score += 30
    if cv_keys == [shared_cv_id]:
        score -= 40
    try:
        score += max(0, 5000 - int(peer.get("catalog_issue_id") or 0)) // 500
    except (TypeError, ValueError):
        pass
    return score


def pick_duplicate_cv_keeper_and_bad(
    row: dict[str, Any],
) -> tuple[int | None, int | None, str, int]:
    shared = _shared_comicvine_id(row)
    peers = row.get("peer_catalog_issues") or []
    if not shared or not isinstance(peers, list) or len(peers) < 2:
        return None, None, "insufficient_peer_data", 0
    scored: list[tuple[int, dict[str, Any], int]] = []
    for peer in peers:
        if not isinstance(peer, dict):
            continue
        pid = peer.get("catalog_issue_id")
        if pid is None:
            continue
        scored.append((int(pid), peer, score_duplicate_cv_peer(peer, shared_cv_id=shared)))
    if len(scored) < 2:
        return None, None, "peer_count_lt_2", 0
    scored.sort(key=lambda t: t[2], reverse=True)
    keeper_id, _, keeper_score = scored[0]
    bad_id, _, bad_score = scored[1]
    margin = keeper_score - bad_score
    if margin < 8:
        return None, None, f"ambiguous_peer_scores margin={margin}", margin
    return keeper_id, bad_id, "keeper_clear", margin


def _annotate_keeper_after_cv_dedupe(
    ext: dict[str, Any],
    *,
    comicvine_id: str,
    duplicate_shell_catalog_issue_id: int,
) -> dict[str, Any]:
    out = dict(ext)
    meta = dict(out.get(P1036_CV_META) or {})
    meta["keeper_comicvine_id"] = comicvine_id
    meta["duplicate_shell_catalog_issue_id"] = duplicate_shell_catalog_issue_id
    meta["resolved_at"] = datetime.now(timezone.utc).isoformat()
    out[P1036_CV_META] = meta
    return out


def _relocate_comicvine_id_from_duplicate_shell(
    ext: dict[str, Any],
    *,
    comicvine_id: str,
    keeper_catalog_issue_id: int,
) -> dict[str, Any]:
    out = dict(ext)
    cv = dict(out.get("COMICVINE") or {})
    prior = cv.pop(comicvine_id, None)
    out["COMICVINE"] = cv
    meta = dict(out.get(P1036_CV_META) or {})
    relocated = list(meta.get("relocated_comicvine_ids") or [])
    relocated.append(
        {
            "comicvine_id": comicvine_id,
            "role": "duplicate_shell",
            "keeper_catalog_issue_id": keeper_catalog_issue_id,
            "prior_cv_entry": prior,
            "relocated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    meta["relocated_comicvine_ids"] = relocated
    meta["duplicate_of_catalog_issue_id"] = keeper_catalog_issue_id
    out[P1036_CV_META] = meta
    return out


def repair_duplicate_cv_pair(
    session: Session,
    *,
    keeper_id: int,
    bad_id: int,
    shared_cv_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    keeper = session.get(CatalogIssue, keeper_id)
    bad = session.get(CatalogIssue, bad_id)
    if keeper is None or bad is None:
        return {"status": "error", "reason": "missing_catalog_issue"}

    keeper_ext_before = dict(keeper.external_source_ids or {})
    bad_ext_before = dict(bad.external_source_ids or {})

    keeper_ext = _annotate_keeper_after_cv_dedupe(
        keeper_ext_before,
        comicvine_id=shared_cv_id,
        duplicate_shell_catalog_issue_id=bad_id,
    )
    bad_ext = _relocate_comicvine_id_from_duplicate_shell(
        bad_ext_before,
        comicvine_id=shared_cv_id,
        keeper_catalog_issue_id=keeper_id,
    )

    if not dry_run:
        keeper.external_source_ids = keeper_ext
        bad.external_source_ids = bad_ext
        session.add(keeper)
        session.add(bad)
        session.commit()

    if dry_run:
        still = False
    else:
        keeper_snap = _snap_from_db_issue(session, keeper)
        bad_snap = _snap_from_db_issue(session, bad)
        dup_index = build_comicvine_duplicate_index([keeper_snap, bad_snap])
        still = _cv_duplicate_conflict(keeper_snap, dup_index) or _cv_duplicate_conflict(bad_snap, dup_index)

    return {
        "status": "repaired" if not still else "still_duplicate_cv",
        "keeper_id": keeper_id,
        "bad_id": bad_id,
        "shared_comicvine_id": shared_cv_id,
        "dry_run": dry_run,
    }


def p1035_single_issue_retry(
    session: Session,
    *,
    catalog_issue_id: int,
    gcd_path: Path,
    cache_path: Path,
    gcd_index: Any | None = None,
    ctx: CatalogCacheContext | None = None,
) -> dict[str, Any]:
    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is None:
        return {"status": "missing_issue"}
    snap = _snap_from_db_issue(session, issue)
    dup_index = build_comicvine_duplicate_index([snap])
    if _cv_duplicate_conflict(snap, dup_index):
        return {"status": "still_duplicate_cv", "catalog_issue_id": catalog_issue_id}

    filters = EnrichmentFilters(
        year_from=1900,
        year_to=2100,
        publisher=None,
        all_catalog=True,
        year_filter_explicit=False,
        limit=None,
    )
    if gcd_index is None:
        gcd_index = load_gcd_index_for_enrichment(
            gcd_path,
            year_from=filters.year_from,
            year_to=filters.year_to,
            focus_publisher=filters.publisher,
            all_catalog=True,
            year_filter_explicit=False,
            catalog_scope=[snap],
        )
    if ctx is None:
        ctx = CatalogCacheContext.load(cache_path)
    gcd_row = lookup_gcd_for_catalog(gcd_index, snap)
    if gcd_row is None:
        return {"status": "still_no_gcd_match", "catalog_issue_id": catalog_issue_id}
    planned, skip, _ = plan_identity_backfill(snap, gcd_row, ctx=ctx)
    if skip:
        return {"status": "still_blocked", "catalog_issue_id": catalog_issue_id, "skip": skip}
    if not planned:
        return {"status": "nothing_to_apply", "catalog_issue_id": catalog_issue_id}
    return {
        "status": "ready_for_p1035",
        "catalog_issue_id": catalog_issue_id,
        "gcd_issue_id": int(_normalize_gcd_id(gcd_row)),
        "planned_fields": [p.get("field") for p in planned],
    }


def _normalize_gcd_id(gcd_row: dict[str, Any]) -> int:
    gid = gcd_row.get("gcd_issue_id")
    if gid is not None:
        return int(gid)
    return int(gcd_row.get("issue_id"))


def resolve_duplicate_cv_conflicts(
    session: Session,
    *,
    csv_path: Path,
    gcd_path: Path,
    cache_path: Path,
    dry_run: bool,
    limit: int | None,
    report: P1036ResolutionReport,
) -> None:
    rows = load_exception_csv(csv_path)
    if limit is not None:
        rows = rows[: max(1, limit)]

    ctx = CatalogCacheContext.load(cache_path)
    filters = EnrichmentFilters(
        year_from=1900,
        year_to=2100,
        publisher=None,
        all_catalog=True,
        year_filter_explicit=False,
        limit=None,
    )
    shared_gcd_index = load_gcd_index_for_enrichment(
        gcd_path,
        year_from=filters.year_from,
        year_to=filters.year_to,
        focus_publisher=filters.publisher,
        all_catalog=True,
        year_filter_explicit=False,
        catalog_scope=None,
    )

    still_rows: list[dict[str, Any]] = []
    for row in rows:
        keeper_id, bad_id, pick_reason, margin = pick_duplicate_cv_keeper_and_bad(row)
        outcome: dict[str, Any] = {
            "catalog_issue_id": row.get("catalog_issue_id"),
            "pick_reason": pick_reason,
            "score_margin": margin,
        }
        if keeper_id is None or bad_id is None:
            outcome["status"] = "unresolved"
            still_rows.append(row)
            report.counts.duplicate_cv_still_conflict += 1
            report.duplicate_cv_outcomes.append(outcome)
            continue

        shared = _shared_comicvine_id(row) or ""
        repair = repair_duplicate_cv_pair(
            session,
            keeper_id=keeper_id,
            bad_id=bad_id,
            shared_cv_id=shared,
            dry_run=dry_run,
        )
        outcome.update(repair)
        retry = p1035_single_issue_retry(
            session,
            catalog_issue_id=keeper_id,
            gcd_path=gcd_path,
            cache_path=cache_path,
            gcd_index=shared_gcd_index,
            ctx=ctx,
        )
        outcome["p1035_retry"] = retry
        if not dry_run and retry.get("status") == "ready_for_p1035":
            try:
                outcome["p1035_apply"] = run_p1035_manual_attach(
                    session,
                    catalog_issue_id=keeper_id,
                    gcd_issue_id=int(retry["gcd_issue_id"]),
                    gcd_path=gcd_path,
                )
                retry = {**retry, "status": "applied"}
                outcome["p1035_retry"] = retry
            except Exception as exc:
                outcome["p1035_apply_error"] = str(exc)
                retry = {**retry, "status": "apply_failed"}
                outcome["p1035_retry"] = retry
        if repair.get("status") == "repaired":
            report.counts.duplicate_cv_repaired += 1
            if retry.get("status") in {"ready_for_p1035", "applied"}:
                report.counts.p1035_retry_resolved += 1
            else:
                report.counts.p1035_retry_still_blocked += 1
        else:
            report.counts.duplicate_cv_still_conflict += 1
            still_rows.append(row)
        report.duplicate_cv_outcomes.append(outcome)

    report.final_exceptions["duplicate_cv_conflicts"] = still_rows


def resolve_upc_conflicts_barcode_authority(
    session: Session,
    *,
    csv_path: Path,
    gcd_path: Path,
    cache_path: Path,
    dry_run: bool,
    limit: int | None,
    report: P1036ResolutionReport,
) -> None:
    batch = resolve_p1035_upc_conflicts_from_csv(
        session,
        csv_path=csv_path,
        gcd_path=gcd_path,
        cache_path=cache_path,
        limit=limit or 10_000,
        dry_run=dry_run,
        confirm_write=not dry_run,
    )
    review_rows: list[dict[str, Any]] = []
    for outcome in batch.get("outcomes") or []:
        p1035_row = outcome.get("p1035") or {}
        entry = {
            "barcode": outcome.get("barcode") or p1035_row.get("conflicting_barcode"),
            "catalog_issue_id": p1035_row.get("catalog_issue_id"),
            "classification": classify_p106_upc_outcome(outcome),
            "outcome": outcome,
        }
        report.upc_outcomes.append(entry)
        cls = outcome.get("bucket") or classify_p106_batch_outcome(outcome, dry_run=dry_run)
        if cls in {"auto_imported", "auto_attached", "already_resolved"}:
            report.counts.upc_p106_resolved += 1
        else:
            report.counts.upc_review_required += 1
            review_rows.append(
                {
                    **{k: p1035_row.get(k) for k in p1035_row if k != "raw_row"},
                    "p106_classification": cls,
                    "p106_diagnosis": (outcome.get("diagnosis") or {}),
                }
            )
    report.final_exceptions["upc_conflicts"] = review_rows


def classify_p106_upc_outcome(outcome: dict[str, Any]) -> str:
    if outcome.get("error"):
        return "error"
    diag = outcome.get("diagnosis") or {}
    if diag.get("already_resolved"):
        return "already_resolved"
    if outcome.get("written") and outcome.get("result"):
        action = (outcome.get("result") or {}).get("action")
        if action == "auto_attach":
            return "auto_attached"
        if action == "auto_import":
            return "auto_imported"
    if dry_run_class := outcome.get("classification"):
        return str(dry_run_class)
    status = diag.get("status")
    if status in {"review_required", "conflict"}:
        return "review_required"
    if status == "unresolved":
        return "unresolved"
    if diag.get("ready_to_auto_import"):
        return "ready_to_auto_import"
    return "review_required"


def _catalog_barcode_for_issue(session: Session, issue_id: int) -> str | None:
    row = session.exec(
        select(CatalogUpc.normalized_upc).where(CatalogUpc.issue_id == int(issue_id)).limit(1)
    ).first()
    return str(row) if row else None


def _detect_ambiguous_strong_signals(
    session: Session,
    *,
    row: dict[str, Any],
    gcd_path: Path,
    cache_path: Path | None,
) -> list[tuple[str, dict[str, Any]]]:
    signals: list[tuple[str, dict[str, Any]]] = []
    catalog_id = int(row["catalog_issue_id"])
    candidates = row.get("gcd_candidates") or []
    if not isinstance(candidates, list):
        candidates = []

    issue = session.get(CatalogIssue, catalog_id)
    if issue is None:
        return signals

    catalog_cv = str(row.get("comicvine_issue_id") or "").strip()
    catalog_barcode = row.get("existing_barcode") or _catalog_barcode_for_issue(session, catalog_id)
    catalog_barcode_s = str(catalog_barcode).strip() if catalog_barcode else ""

    if catalog_barcode_s:
        barcode_matches = [
            c
            for c in candidates
            if isinstance(c, dict) and str(c.get("gcd_barcode") or "").strip() == catalog_barcode_s
        ]
        if len(barcode_matches) == 1:
            signals.append(("exact_barcode", barcode_matches[0]))
        elif len(barcode_matches) > 1:
            pass
        elif len(candidates) == 1 and isinstance(candidates[0], dict):
            only_barcode = str(candidates[0].get("gcd_barcode") or "").strip()
            if only_barcode:
                diag = diagnose_barcode_gap(
                    session,
                    barcode=only_barcode,
                    gcd_path=gcd_path,
                    cache_path=cache_path,
                )
                if int(diag.get("gcd_match_count") or 0) == 1:
                    gid = int(candidates[0].get("gcd_issue_id") or 0)
                    if int(diag.get("gcd_issue_id") or 0) == gid and (
                        diag.get("ready_to_auto_import")
                        or int(diag.get("catalog_issue_id") or 0) == catalog_id
                    ):
                        signals.append(("exact_barcode", candidates[0]))

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        notes = str(cand.get("gcd_title") or cand.get("title") or "")
        if catalog_cv and catalog_cv in notes:
            signals.append(("exact_comicvine_crossref", cand))

    if catalog_cv:
        ext = issue.external_source_ids or {}
        cv_map = ext.get("COMICVINE") if isinstance(ext, dict) else {}
        if isinstance(cv_map, dict) and catalog_cv in cv_map and len(candidates) == 1:
            signals.append(("exact_external_source_id", candidates[0]))

    deduped: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, int]] = set()
    for kind, cand in signals:
        if kind not in STRONG_AMBIGUOUS_SIGNALS:
            continue
        gid = int(cand.get("gcd_issue_id") or 0)
        key = (kind, gid)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((kind, cand))
    return deduped


def resolve_ambiguous_matches_with_evidence(
    session: Session,
    *,
    csv_path: Path,
    gcd_path: Path,
    cache_path: Path,
    dry_run: bool,
    limit: int | None,
    report: P1036ResolutionReport,
) -> None:
    rows = load_exception_csv(csv_path)
    if limit is not None:
        rows = rows[: max(1, limit)]

    still_rows: list[dict[str, Any]] = []
    for row in rows:
        catalog_id = int(row["catalog_issue_id"])
        signals = _detect_ambiguous_strong_signals(
            session,
            row=row,
            gcd_path=gcd_path,
            cache_path=cache_path,
        )
        outcome: dict[str, Any] = {
            "catalog_issue_id": catalog_id,
            "signals": [{"kind": k, "gcd_issue_id": c.get("gcd_issue_id")} for k, c in signals],
        }
        if not signals:
            outcome["status"] = "still_ambiguous"
            still_rows.append(row)
            report.counts.ambiguous_still_ambiguous += 1
            report.ambiguous_outcomes.append(outcome)
            continue

        kinds = {k for k, _ in signals}
        gcd_ids = {int(c.get("gcd_issue_id") or 0) for _, c in signals}
        if len(gcd_ids) != 1:
            outcome["status"] = "conflicting_signals"
            still_rows.append(row)
            report.counts.ambiguous_still_ambiguous += 1
            report.ambiguous_outcomes.append(outcome)
            continue

        gcd_issue_id = next(iter(gcd_ids))
        primary_kind = next(iter(kinds))
        outcome["primary_signal"] = primary_kind
        outcome["gcd_issue_id"] = gcd_issue_id

        if dry_run:
            outcome["status"] = "would_attach"
            report.counts.ambiguous_resolved += 1
            report.ambiguous_outcomes.append(outcome)
            continue

        try:
            attach = run_p1035_manual_attach(
                session,
                catalog_issue_id=catalog_id,
                gcd_issue_id=gcd_issue_id,
                gcd_path=gcd_path,
                allow_upc_conflict=primary_kind == "exact_barcode",
            )
            outcome["status"] = "attached"
            outcome["attach"] = attach
            report.counts.ambiguous_resolved += 1
        except Exception as exc:
            outcome["status"] = "attach_failed"
            outcome["error"] = str(exc)
            still_rows.append(row)
            report.counts.ambiguous_still_ambiguous += 1
        report.ambiguous_outcomes.append(outcome)

    report.final_exceptions["ambiguous_matches"] = still_rows


def run_p1036_exception_resolution(
    session: Session,
    *,
    exceptions_dir: Path,
    gcd_path: Path,
    cache_path: Path,
    dry_run: bool = True,
    limit: int | None = None,
    enable_duplicate_cv: bool = True,
    enable_upc: bool = True,
    enable_ambiguous: bool = True,
) -> P1036ResolutionReport:
    report = P1036ResolutionReport(dry_run=dry_run)
    if enable_duplicate_cv:
        dup_csv = exceptions_dir / "duplicate_cv_conflicts.csv"
        if dup_csv.is_file():
            resolve_duplicate_cv_conflicts(
                session,
                csv_path=dup_csv,
                gcd_path=gcd_path,
                cache_path=cache_path,
                dry_run=dry_run,
                limit=limit,
                report=report,
            )
    if enable_upc:
        upc_csv = exceptions_dir / "upc_conflicts.csv"
        if upc_csv.is_file():
            resolve_upc_conflicts_barcode_authority(
                session,
                csv_path=upc_csv,
                gcd_path=gcd_path,
                cache_path=cache_path,
                dry_run=dry_run,
                limit=limit,
                report=report,
            )
    if enable_ambiguous:
        amb_csv = exceptions_dir / "ambiguous_matches.csv"
        if amb_csv.is_file():
            resolve_ambiguous_matches_with_evidence(
                session,
                csv_path=amb_csv,
                gcd_path=gcd_path,
                cache_path=cache_path,
                dry_run=dry_run,
                limit=limit,
                report=report,
            )
    return report


def write_p1036_outputs(report: P1036ResolutionReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "p1036_resolution_report.json"
    summary_path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
    write_p1035_exception_backlog(report.final_exceptions, out_dir / "remaining")
    return summary_path
