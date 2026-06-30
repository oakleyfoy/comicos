"""Structured P106.1 intake execution trace (fingerprint search + suppression + persist)."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_active_trace: ContextVar["IntakeP1061Trace | None"] = ContextVar("intake_p106_1_trace", default=None)


@dataclass
class IntakeP1061Trace:
    intake_item_id: int
    events: list[dict[str, Any]] = field(default_factory=list)
    fingerprint_search_called: bool = False
    fingerprint_search_skipped: bool = False
    skip_fingerprint_search: bool = False
    full_cover_followup_required: bool = False
    fingerprint_region_safe: bool = False
    fingerprint_image_region: str = "unknown"
    barcode: str | None = None

    def record(self, tag: str, payload: dict[str, Any]) -> None:
        row = {"tag": tag, **payload}
        self.events.append(row)
        logger.info("%s %s", tag, json.dumps(payload, default=str))


def log_p106_1_before_fingerprint(
    *,
    intake_item_id: int,
    fingerprint_region_safe: bool,
    fingerprint_image_region: str,
    full_cover_followup_required: bool,
) -> None:
    trace = _active_trace.get()
    if trace is not None:
        trace.fingerprint_region_safe = fingerprint_region_safe
        trace.fingerprint_image_region = fingerprint_image_region
        trace.full_cover_followup_required = full_cover_followup_required
    payload = {
        "intake_item_id": int(intake_item_id),
        "fingerprint_region_safe": fingerprint_region_safe,
        "fingerprint_image_region": fingerprint_image_region,
        "full_cover_followup_required": full_cover_followup_required,
    }
    trace = _active_trace.get()
    if trace is not None:
        trace.record("P106_1_BEFORE_FINGERPRINT", payload)
    else:
        logger.info("P106_1_BEFORE_FINGERPRINT %s", json.dumps(payload, default=str))


def log_p106_1_after_suppression(
    *,
    review_candidates_count: int,
    fingerprint_candidates_count: int,
    final_status: str,
) -> None:
    payload = {
        "review_candidates_count": int(review_candidates_count),
        "fingerprint_candidates_count": int(fingerprint_candidates_count),
        "final_status": str(final_status),
    }
    trace = _active_trace.get()
    if trace is not None:
        trace.record("P106_1_AFTER_SUPPRESSION", payload)
    else:
        logger.info("P106_1_AFTER_SUPPRESSION %s", json.dumps(payload, default=str))


def log_p106_1_persist(*, candidates_written: int, status_written: str) -> None:
    payload = {
        "candidates_written": int(candidates_written),
        "status_written": str(status_written),
    }
    trace = _active_trace.get()
    if trace is not None:
        trace.record("P106_1_PERSIST", payload)
    else:
        logger.info("P106_1_PERSIST %s", json.dumps(payload, default=str))


def set_fingerprint_search_gate(
    *,
    skip_fingerprint_search: bool,
    full_cover_followup_required: bool,
    fingerprint_region_safe: bool,
    fingerprint_image_region: str,
) -> None:
    trace = _active_trace.get()
    if trace is None:
        return
    trace.skip_fingerprint_search = skip_fingerprint_search
    trace.full_cover_followup_required = full_cover_followup_required
    trace.fingerprint_region_safe = fingerprint_region_safe
    trace.fingerprint_image_region = fingerprint_image_region


def gated_search_catalog_fingerprint_hits_for_crop_path(session, *, crop_path, limit: int = 5):
    """Call fingerprint search unless this intake trace gate forbids it."""
    from app.services.photo_import_fingerprint_service import search_catalog_fingerprint_hits_for_crop_path

    trace = _active_trace.get()
    if trace is not None and (
        trace.skip_fingerprint_search
        or not trace.fingerprint_region_safe
        or trace.full_cover_followup_required
    ):
        trace.fingerprint_search_skipped = True
        logger.info(
            "P106_1_FINGERPRINT_SEARCH_SKIPPED %s",
            json.dumps(
                {
                    "intake_item_id": trace.intake_item_id,
                    "skip_fingerprint_search": trace.skip_fingerprint_search,
                    "fingerprint_region_safe": trace.fingerprint_region_safe,
                    "full_cover_followup_required": trace.full_cover_followup_required,
                },
                default=str,
            ),
        )
        return []
    if trace is not None:
        trace.fingerprint_search_called = True
    from app.services.intake_fingerprint_search_debug_service import (
        FingerprintSearchDebugContext,
        fingerprint_search_debug_context,
        get_fingerprint_search_debug_context,
    )

    existing = get_fingerprint_search_debug_context()
    if existing is not None:
        return search_catalog_fingerprint_hits_for_crop_path(session, crop_path=crop_path, limit=limit)
    if trace is not None:
        ctx = FingerprintSearchDebugContext(
            intake_item_id=trace.intake_item_id,
            barcode=trace.barcode,
            fingerprint_image_region=trace.fingerprint_image_region,
            fingerprint_region_safe=trace.fingerprint_region_safe,
        )
        with fingerprint_search_debug_context(ctx):
            return search_catalog_fingerprint_hits_for_crop_path(session, crop_path=crop_path, limit=limit)
    return search_catalog_fingerprint_hits_for_crop_path(session, crop_path=crop_path, limit=limit)


@contextmanager
def activate_intake_p106_1_trace(intake_item_id: int) -> Iterator[IntakeP1061Trace]:
    trace = IntakeP1061Trace(intake_item_id=int(intake_item_id))
    token = _active_trace.set(trace)
    try:
        yield trace
    finally:
        _active_trace.reset(token)


def intake_p106_1_trace_snapshot() -> dict[str, Any] | None:
    trace = _active_trace.get()
    if trace is None:
        return None
    return {
        "intake_item_id": trace.intake_item_id,
        "fingerprint_search_called": trace.fingerprint_search_called,
        "fingerprint_search_skipped": trace.fingerprint_search_skipped,
        "events": list(trace.events),
    }


def format_execution_trace(trace: IntakeP1061Trace | None) -> str:
    if trace is None:
        return "(no trace)"
    lines = [
        f"intake_item_id={trace.intake_item_id}",
        f"fingerprint_search_called={trace.fingerprint_search_called}",
        f"fingerprint_search_skipped={trace.fingerprint_search_skipped}",
    ]
    for event in trace.events:
        lines.append(f"{event.get('tag')}: {json.dumps({k: v for k, v in event.items() if k != 'tag'}, default=str)}")
    return "\n".join(lines)
