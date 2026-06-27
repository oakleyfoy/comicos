"""Structured logging and reporting for intake scanner barcode resolution (field tests)."""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import REPO_ROOT
from app.models.catalog_master import CatalogUpc
from app.models.intake_queue import (
    ITEM_FAILED,
    ITEM_AUTO_MATCHED,
    ComicIssueBarcode,
    IntakeSessionItem,
    MATCH_SOURCE_CATALOG_UPC,
    MATCH_SOURCE_COMICVINE,
    MATCH_SOURCE_LEARNED,
)
from app.models.p106_barcode_gap import (
    P106_STATUS_AUTO_ATTACHED,
    P106_STATUS_AUTO_IMPORTED,
    P106_STATUS_CONFLICT,
    P106_STATUS_REVIEW_REQUIRED,
    P106_STATUS_UNRESOLVED,
)
from app.services.catalog_ingestion_service import (
    comic_barcode_lookup_keys_for_search,
    direct_market_requires_supplement_key,
)
from app.services.p106_barcode_gap_resolver_service import barcode_gap_payload_from_diagnosis

logger = logging.getLogger(__name__)

_WRITE_LOCK = threading.Lock()

BUCKET_INSTANT_LOCAL = "instant_local_match"
BUCKET_LEARNED = "learned_barcode_match"
BUCKET_P106_ATTACH = "p106_auto_attached"
BUCKET_P106_IMPORT = "p106_auto_imported"
BUCKET_COMICVINE = "comicvine_fallback"
BUCKET_NO_GCD = "unresolved_no_gcd_match"
BUCKET_REVIEW = "review_required_conflict"
BUCKET_DECODE_FAILED = "barcode_decode_failed"
BUCKET_OTHER = "other_error"

ALL_BUCKETS = (
    BUCKET_INSTANT_LOCAL,
    BUCKET_LEARNED,
    BUCKET_P106_ATTACH,
    BUCKET_P106_IMPORT,
    BUCKET_COMICVINE,
    BUCKET_NO_GCD,
    BUCKET_REVIEW,
    BUCKET_DECODE_FAILED,
    BUCKET_OTHER,
)


def default_field_test_log_path() -> Path:
    override = os.environ.get("SCANNER_BARCODE_FIELD_TEST_LOG", "").strip()
    if override:
        return Path(override).expanduser()
    return REPO_ROOT / "data" / "scanner" / "barcode_field_test.jsonl"


def gcd_database_metadata(gcd_path: Path | None) -> tuple[str | None, str | None]:
    if gcd_path is None or not gcd_path.is_file():
        return (str(gcd_path) if gcd_path else None, None)
    resolved = gcd_path.resolve()
    mtime = datetime.fromtimestamp(resolved.stat().st_mtime, tz=timezone.utc).isoformat()
    return (str(resolved), mtime)


def probe_local_barcode_hits(session: Session, *, normalized_barcode: str) -> tuple[bool, bool]:
    """Instrumentation-only: learned row present vs catalog_upc row present."""
    learned_hit = (
        session.exec(
            select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalized_barcode)
        ).first()
        is not None
    )
    upc_hit = False
    for key in comic_barcode_lookup_keys_for_search(normalized_barcode):
        if len(key) < 17 and direct_market_requires_supplement_key(normalized_barcode):
            continue
        row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == key)).first()
        if row is not None and row.issue_id is not None:
            upc_hit = True
            break
    return learned_hit, upc_hit


@dataclass
class ScannerBarcodeResolutionTrace:
    intake_item_id: int
    session_id: int | None = None
    scanned_barcode_raw: str | None = None
    normalized_barcode: str | None = None
    local_catalog_upc_hit: bool = False
    learned_barcode_hit: bool = False
    p106_called: bool = False
    p106_status: str | None = None
    p106_action: str | None = None
    p106_gcd_match_count: int | None = None
    p106_gcd_issue_id: int | None = None
    p106_gcd_series: str | None = None
    p106_gcd_issue_number: str | None = None
    p106_gcd_database_path: str | None = None
    p106_gcd_database_modified_at: str | None = None
    p106_auto_imported: bool = False
    p106_auto_attached: bool = False
    comicvine_fallback_called: bool = False
    gap_diagnosis: dict[str, Any] | None = field(default=None, repr=False)
    match_source: str | None = None

    def apply_p106_diagnosis(self, diagnosis: dict[str, Any] | None, *, gcd_path: Path | None) -> None:
        if not diagnosis:
            return
        self.gap_diagnosis = diagnosis
        path_str, mtime = gcd_database_metadata(gcd_path)
        self.p106_gcd_database_path = path_str
        self.p106_gcd_database_modified_at = mtime
        self.p106_status = diagnosis.get("status")
        if diagnosis.get("reason"):
            self.p106_status = self.p106_status or str(diagnosis.get("reason"))
        payload = barcode_gap_payload_from_diagnosis(diagnosis)
        self.p106_action = payload.get("action") or diagnosis.get("proposed_action")
        self.p106_gcd_match_count = diagnosis.get("gcd_match_count")
        self.p106_gcd_issue_id = diagnosis.get("gcd_issue_id")
        self.p106_gcd_series = payload.get("gcd_series")
        self.p106_gcd_issue_number = payload.get("gcd_issue_number")

    def apply_p106_resolve_outcome(self, outcome: dict[str, Any] | None) -> None:
        if not outcome or not outcome.get("written"):
            return
        result = outcome.get("result") or {}
        action = result.get("action")
        if action == "auto_import":
            self.p106_auto_imported = True
            self.p106_status = P106_STATUS_AUTO_IMPORTED
        elif action == "auto_attach":
            self.p106_auto_attached = True
            self.p106_status = P106_STATUS_AUTO_ATTACHED


def build_scanner_barcode_event(
    *,
    trace: ScannerBarcodeResolutionTrace,
    item: IntakeSessionItem,
    final_status: str,
    final_reason: str | None,
) -> dict[str, Any]:
    diag = trace.gap_diagnosis or {}
    event: dict[str, Any] = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "intake_item_id": trace.intake_item_id,
        "intake_session_id": trace.session_id,
        "scanned_barcode_raw": trace.scanned_barcode_raw,
        "normalized_barcode": trace.normalized_barcode or item.normalized_barcode,
        "local_catalog_upc_hit": trace.local_catalog_upc_hit,
        "learned_barcode_hit": trace.learned_barcode_hit,
        "p106_called": trace.p106_called,
        "p106_status": trace.p106_status,
        "p106_action": trace.p106_action,
        "p106_gcd_match_count": trace.p106_gcd_match_count,
        "p106_gcd_issue_id": trace.p106_gcd_issue_id,
        "p106_gcd_series": trace.p106_gcd_series,
        "p106_gcd_issue_number": trace.p106_gcd_issue_number,
        "p106_gcd_database_path": trace.p106_gcd_database_path,
        "p106_gcd_database_modified_at": trace.p106_gcd_database_modified_at,
        "p106_auto_imported": trace.p106_auto_imported,
        "p106_auto_attached": trace.p106_auto_attached,
        "comicvine_fallback_called": trace.comicvine_fallback_called,
        "match_source": trace.match_source or item.match_source,
        "final_status": final_status,
        "final_catalog_issue_id": item.selected_catalog_issue_id,
        "final_title": item.matched_series,
        "final_issue_number": item.matched_issue_number,
        "final_reason": final_reason or item.reason or item.error,
    }
    no_gcd = (
        diag.get("final_reason") == "no_gcd_barcode_match"
        or diag.get("reason") == "no_gcd_barcode_match"
        or diag.get("gcd_lookup_final_reason") == "no_gcd_barcode_match"
    )
    if trace.p106_called and (no_gcd or int(diag.get("gcd_match_count") or 0) == 0):
        event["searched_full_barcode"] = diag.get("searched_full_barcode")
        event["searched_upc12"] = diag.get("searched_upc12")
        event["searched_supplement"] = diag.get("searched_supplement")
        event["gcd_exact_hits"] = diag.get("gcd_exact_hits")
        event["gcd_prefix_hits"] = diag.get("gcd_prefix_hits")
        event["gcd_notes_hits"] = diag.get("gcd_notes_hits")
        event["gcd_lookup_final_reason"] = diag.get("gcd_lookup_final_reason")
        event["p106_gcd_lookup_final_reason"] = diag.get("gcd_lookup_final_reason")
    elif diag.get("gcd_lookup_final_reason"):
        event["p106_gcd_lookup_final_reason"] = diag.get("gcd_lookup_final_reason")
    event["bucket"] = classify_scanner_barcode_bucket(event)
    return event


def classify_scanner_barcode_bucket(event: dict[str, Any]) -> str:
    status = event.get("final_status")
    reason = str(event.get("final_reason") or "")
    normalized = event.get("normalized_barcode")

    if status == ITEM_FAILED:
        if not normalized or "Could not read a barcode" in reason or "check digit" in reason.lower():
            return BUCKET_DECODE_FAILED
        if "too small" in reason.lower():
            return BUCKET_DECODE_FAILED
        return BUCKET_OTHER

    if event.get("p106_auto_imported"):
        return BUCKET_P106_IMPORT
    if event.get("p106_auto_attached"):
        return BUCKET_P106_ATTACH

    match_source = event.get("match_source") or ""
    if status == ITEM_AUTO_MATCHED and match_source == MATCH_SOURCE_LEARNED:
        return BUCKET_LEARNED
    if status == ITEM_AUTO_MATCHED and match_source == MATCH_SOURCE_CATALOG_UPC:
        return BUCKET_INSTANT_LOCAL
    if event.get("learned_barcode_hit") and status == ITEM_AUTO_MATCHED:
        return BUCKET_LEARNED
    if event.get("local_catalog_upc_hit") and status == ITEM_AUTO_MATCHED:
        return BUCKET_INSTANT_LOCAL

    if event.get("comicvine_fallback_called") or match_source == MATCH_SOURCE_COMICVINE:
        return BUCKET_COMICVINE

    p106_status = event.get("p106_status")
    p106_action = event.get("p106_action")
    if p106_status in {P106_STATUS_REVIEW_REQUIRED, P106_STATUS_CONFLICT} or p106_action == "review_required":
        return BUCKET_REVIEW
    if (
        event.get("p106_gcd_lookup_final_reason") == "no_gcd_barcode_match"
        or (
            p106_status == P106_STATUS_UNRESOLVED
            and int(event.get("p106_gcd_match_count") or 0) == 0
        )
    ):
        return BUCKET_NO_GCD
    if event.get("p106_called") and int(event.get("p106_gcd_match_count") or 0) == 0:
        return BUCKET_NO_GCD

    if status == ITEM_AUTO_MATCHED:
        return BUCKET_INSTANT_LOCAL

    return BUCKET_OTHER


def append_scanner_barcode_event(event: dict[str, Any], *, log_path: Path | None = None) -> Path:
    path = log_path or default_field_test_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, default=str, ensure_ascii=False)
    with _WRITE_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    logger.info("scanner.barcode.field_test %s", line)
    return path


def record_scanner_barcode_resolution(
    *,
    trace: ScannerBarcodeResolutionTrace | None,
    item: IntakeSessionItem,
    final_status: str,
    final_reason: str | None,
    log_path: Path | None = None,
) -> dict[str, Any] | None:
    if trace is None:
        return None
    try:
        event = build_scanner_barcode_event(
            trace=trace,
            item=item,
            final_status=final_status,
            final_reason=final_reason,
        )
        append_scanner_barcode_event(event, log_path=log_path)
        return event
    except Exception:
        logger.warning("scanner.barcode.field_test_record_failed item_id=%s", item.id, exc_info=True)
        return None


def load_recent_scanner_barcode_events(*, log_path: Path | None = None, limit: int = 100) -> list[dict[str, Any]]:
    path = log_path or default_field_test_log_path()
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    tail = lines[-max(1, limit) :] if limit else lines
    out: list[dict[str, Any]] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def summarize_scanner_barcode_field_test(events: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in ALL_BUCKETS}
    for ev in events:
        bucket = ev.get("bucket") or classify_scanner_barcode_bucket(ev)
        if bucket not in buckets:
            bucket = BUCKET_OTHER
        buckets[bucket].append(ev)
    counts = {k: len(v) for k, v in buckets.items()}
    return {"counts": counts, "buckets": buckets, "total": len(events)}
