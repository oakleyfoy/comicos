from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from app.models import (
    MarketAcquisitionCandidate,
    MarketAcquisitionIngestionBatch,
    MarketAcquisitionNormalizationEvent,
    MarketAcquisitionNormalizationIssue,
    MarketAcquisitionNormalizationRun,
    MarketAcquisitionNormalizedCandidate,
)
from app.services.market_feed import append_market_feed_event
from app.schemas.market_normalization import (
    MarketAcquisitionNormalizedCandidateListResponse,
    MarketAcquisitionNormalizedCandidateRead,
    MarketNormalizationEventRead,
    MarketNormalizationHealthRead,
    MarketNormalizationIssueListResponse,
    MarketNormalizationIssueRead,
    MarketNormalizationRunCreatePayload,
    MarketNormalizationRunDetailRead,
    MarketNormalizationRunListResponse,
    MarketNormalizationRunSummaryRead,
)

MONEY_QUANT = Decimal("0.01")

# Deterministic longest-first prefixes (applied iteratively until no match).
_TITLE_PREFIX_RULES = (
    "spectacular spider-man ",
    "amazing spider-man ",
    "the spectacular ",
    "the amazing ",
    "ultimate ",
    "incredible ",
    "detective comics ",
    "the ",
    "a ",
    "an ",
)

_PUBLISHER_EXACT_LOWER = {
    "marvel comics": "Marvel",
    "marvel entertainment": "Marvel",
    "marvel": "Marvel",
    "dc comics": "DC",
    "d.c. comics": "DC",
    "d c comics": "DC",
}

_VARIANT_LOOKUP_LOWER = {
    "a": "A",
    "b": "B",
    "c": "C",
    "cover a": "A",
    "cover b": "B",
    "cover c": "C",
    "cover ed": None,
    "direct": "Direct",
    "direct edition": "Direct",
    "newsstand": "Newsstand",
    "newsstand edition": "Newsstand",
}

# Longest substring match first — first win.
_CONDITION_TERMS_ORDERED: tuple[tuple[str, str], ...] = (
    ("very fine/near mint", "VF"),
    ("vf/nm", "VF"),
    ("near mint/mint", "NM"),
    ("near mint+", "NM"),
    ("near mint", "NM"),
    ("mint/near mint", "NM"),
    ("near-mint", "NM"),
    ("nm+", "NM"),
    (" nm", "NM"),
    ("very fine+", "VF"),
    ("fine/very fine", "FINE"),
    ("fine/ vf", "FINE"),
    ("fine/vf", "FINE"),
    ("very fine", "VF"),
    ("vf+", "VF"),
    ("fine+", "FINE"),
    ("very good+", "VERY_GOOD"),
    ("very good", "VERY_GOOD"),
    ("vg+", "VERY_GOOD"),
    ("vg-", "VERY_GOOD"),
    ("vg/", "VERY_GOOD"),
    ("vg", "VERY_GOOD"),
    ("fine", "FINE"),
    ("fn", "FINE"),
    ("fair", "POOR"),
    ("poor", "POOR"),
    ("readable", "POOR"),
    (" vf", "VF"),
    (" nm", "NM"),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_market_normalization_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def compute_canonical_key(
    *,
    canonical_title: str,
    canonical_publisher: str | None,
    canonical_issue_number: str | None,
    canonical_variant: str | None,
) -> str:
    pub = canonical_publisher or ""
    issue = canonical_issue_number or ""
    variant = canonical_variant or ""
    raw = f"{canonical_title}{pub}{issue}{variant}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _squash_spaces(s: str) -> str:
    return " ".join(s.split())


def _strip_special_keep_alnum_spaces(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    return _squash_spaces(s)


def deterministic_normalize_title(raw_title: str) -> str:
    s = raw_title.strip().lower()
    s = _strip_special_keep_alnum_spaces(s)
    changed = True
    safety = 0
    while changed and safety < 32:
        safety += 1
        changed = False
        for prefix in _TITLE_PREFIX_RULES:
            if s.startswith(prefix):
                s = _squash_spaces(s[len(prefix) :])
                changed = True
                break
    return s


def deterministic_normalize_publisher(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    key = _squash_spaces(raw.lower()).strip()
    if key in _PUBLISHER_EXACT_LOWER:
        return _PUBLISHER_EXACT_LOWER[key]
    return raw.strip()


def _normalize_issue_number(raw: str | None) -> tuple[str | None, bool]:
    """Return canonical issue token and ambiguous flag."""
    if raw is None or not raw.strip():
        return None, False
    t = raw.strip()
    lowered = t.lower().replace("#", "")
    chunks = [m.group(1) for m in re.finditer(r"(\d+)", lowered)]
    if len(chunks) == 1:
        return chunks[0], False
    if len(chunks) == 0:
        return lowered, False
    return lowered, True


def _normalize_variant(raw: str | None) -> tuple[str | None, bool]:
    """Canonical variant label and unmappable-nonempty flag."""
    if raw is None or not raw.strip():
        return None, False
    key = _squash_spaces(raw.lower())
    if key in _VARIANT_LOOKUP_LOWER:
        return _VARIANT_LOOKUP_LOWER[key], False
    return None, True


def _normalize_condition_band(raw: str | None) -> tuple[str, bool]:
    """Return band and unmapped-if-raw-provided."""
    if raw is None or not raw.strip():
        return "UNKNOWN", False
    hay = raw.lower().replace("-", "/").strip()
    for needle, band in _CONDITION_TERMS_ORDERED:
        if needle.replace("-", "/") in hay:
            return band, False
    return "UNKNOWN", True


def _parse_optional_money(raw: Decimal | Any | None) -> tuple[Decimal | None, bool]:
    invalid = False
    if raw is None:
        return None, invalid
    if isinstance(raw, Decimal):
        try:
            return raw.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP), invalid
        except (InvalidOperation, ValueError):
            return None, True
    text = str(raw).strip()
    if not text:
        return None, invalid
    cleaned = re.sub(r"[^0-9\.\-]", "", text.replace(",", ""))
    try:
        return Decimal(cleaned).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP), invalid
    except (InvalidOperation, ValueError):
        return None, True


def _canonical_currency(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    c = raw.strip().upper()[:8]
    return c or None


def _candidate_snapshot_for_checksum(candidate: MarketAcquisitionCandidate) -> dict[str, Any]:
    cid = candidate.id if candidate.id is not None else 0
    return {
        "id": cid,
        "title": candidate.title,
        "publisher": candidate.publisher,
        "issue_number": candidate.issue_number,
        "variant": candidate.variant,
        "condition_raw": candidate.condition_raw,
        "asking_price": _json_safe(candidate.asking_price),
        "currency": candidate.currency,
        "external_fmv_estimate": _json_safe(candidate.external_fmv_estimate),
        "external_source_type": candidate.external_source_type,
        "external_listing_id": candidate.external_listing_id,
    }


def compute_run_checksum(candidates_sorted: list[MarketAcquisitionCandidate]) -> str:
    snapshots = [_json_safe(_candidate_snapshot_for_checksum(c)) for c in candidates_sorted]
    payload = bytes(
        json.dumps(snapshots, sort_keys=False, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return hashlib.sha256(payload).hexdigest()


def deterministic_normalize_candidate(
    candidate: MarketAcquisitionCandidate,
) -> dict[str, Any]:
    canonical_title = deterministic_normalize_title(candidate.title)
    raw_pub = candidate.publisher
    canonical_publisher = deterministic_normalize_publisher(raw_pub)

    canon_issue, issue_ambiguous = _normalize_issue_number(candidate.issue_number)

    canon_var, variant_conflict = _normalize_variant(candidate.variant)

    cond_band, cond_unmapped = _normalize_condition_band(candidate.condition_raw)

    price_dec, invalid_asking = _parse_optional_money(candidate.asking_price)

    currency = _canonical_currency(candidate.currency)

    fmv_dec, invalid_fmv = _parse_optional_money(candidate.external_fmv_estimate)

    flags: dict[str, bool] = {
        "missing_publisher": canonical_publisher is None,
        "ambiguous_title": len(candidate.title.strip()) >= 6 and len(canonical_title) < 4,
        "invalid_price": invalid_asking or invalid_fmv,
        "variant_conflict": variant_conflict,
        "condition_unmapped": cond_unmapped,
    }

    issues: list[dict[str, Any]] = []

    if flags["missing_publisher"]:
        issues.append(
            {
                "issue_type": "MISSING_FIELD",
                "severity": "MEDIUM",
                "detail": {"field": "publisher"},
            },
        )
    if issue_ambiguous:
        issues.append(
            {
                "issue_type": "AMBIGUOUS_MATCH",
                "severity": "LOW",
                "detail": {"field": "issue_number", "raw": candidate.issue_number},
            },
        )
    if flags["variant_conflict"]:
        issues.append(
            {
                "issue_type": "VARIANT_CONFLICT",
                "severity": "MEDIUM",
                "detail": {"raw": candidate.variant},
            },
        )
    if flags["invalid_price"]:
        issues.append(
            {
                "issue_type": "INVALID_PRICE",
                "severity": "LOW",
                "detail": {},
            },
        )
    if flags["condition_unmapped"] and candidate.condition_raw:
        issues.append(
            {
                "issue_type": "CONDITION_PARSE_ERROR",
                "severity": "LOW",
                "detail": {"raw": candidate.condition_raw},
            },
        )

    if not canonical_title:
        norm_status = "FAILED"
    elif issues and any(i["severity"] == "HIGH" for i in issues):
        norm_status = "FAILED"
    elif flags["missing_publisher"] or flags["invalid_price"] or flags["variant_conflict"] or flags["condition_unmapped"] or flags["ambiguous_title"]:
        norm_status = "PARTIAL"
    else:
        norm_status = "SUCCESS"

    title_for_key_display = canonical_title if canonical_title else "(unresolved)"
    canon_key = compute_canonical_key(
        canonical_title=title_for_key_display,
        canonical_publisher=canonical_publisher,
        canonical_issue_number=canon_issue,
        canonical_variant=canon_var,
    )

    row = {
        "canonical_title": title_for_key_display,
        "canonical_publisher": canonical_publisher,
        "canonical_issue_number": canon_issue,
        "canonical_variant": canon_var,
        "normalized_condition_band": cond_band,
        "normalized_price": price_dec,
        "normalized_currency": currency,
        "normalized_fmv_estimate": fmv_dec if not invalid_fmv else None,
        "normalized_liquidity_hint": None,
        "normalized_grade_potential": None,
        "canonical_key": canon_key,
        "normalization_flags_json": _json_safe(flags),
        "normalization_status": norm_status,
        "issues": issues,
    }
    return row


def _get_owner_batch_or_404(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
) -> MarketAcquisitionIngestionBatch:
    row = session.get(MarketAcquisitionIngestionBatch, batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market ingestion batch not found")
    if row.owner_user_id is not None and row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Market ingestion batch not found")
    if row.owner_user_id is None:
        raise HTTPException(status_code=404, detail="Market ingestion batch not found")
    return row


def _get_ops_batch_or_404(session: Session, *, batch_id: int) -> MarketAcquisitionIngestionBatch:
    row = session.get(MarketAcquisitionIngestionBatch, batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market ingestion batch not found")
    return row


def _append_event(
    session: Session,
    *,
    run_id: int,
    event_type: str,
    metadata_json: dict[str, Any],
    created_at: datetime,
) -> None:
    session.add(
        MarketAcquisitionNormalizationEvent(
            normalization_run_id=run_id,
            event_type=event_type,
            metadata_json=dict(_json_safe(metadata_json)),
            created_at=created_at,
        )
    )


def _wipe_children_for_failed_run(session: Session, *, run_id: int) -> None:
    session.exec(delete(MarketAcquisitionNormalizedCandidate).where(MarketAcquisitionNormalizedCandidate.normalization_run_id == run_id))
    session.exec(delete(MarketAcquisitionNormalizationIssue).where(MarketAcquisitionNormalizationIssue.normalization_run_id == run_id))
    session.exec(delete(MarketAcquisitionNormalizationEvent).where(MarketAcquisitionNormalizationEvent.normalization_run_id == run_id))


def run_detail(session: Session, *, run_row: MarketAcquisitionNormalizationRun) -> MarketNormalizationRunDetailRead:
    rid = run_row.id
    assert rid is not None
    events = list(
        session.exec(
            select(MarketAcquisitionNormalizationEvent)
            .where(MarketAcquisitionNormalizationEvent.normalization_run_id == rid)
            .order_by(
                col(MarketAcquisitionNormalizationEvent.created_at).asc(),
                col(MarketAcquisitionNormalizationEvent.id).asc(),
            )
        ).all(),
    )
    return MarketNormalizationRunDetailRead(
        **MarketNormalizationRunSummaryRead.model_validate(run_row).model_dump(),
        events=[
            MarketNormalizationEventRead.model_validate(e, from_attributes=True) for e in events
        ],
    )


def execute_market_normalization_run_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketNormalizationRunCreatePayload,
) -> tuple[MarketNormalizationRunDetailRead, bool]:
    batch = _get_owner_batch_or_404(session, owner_user_id=owner_user_id, batch_id=payload.ingestion_batch_id)

    cand_rows = list(
        session.exec(
            select(MarketAcquisitionCandidate)
            .where(MarketAcquisitionCandidate.ingestion_batch_id == payload.ingestion_batch_id)
            .order_by(col(MarketAcquisitionCandidate.id).asc())
        ).all(),
    )

    chk = compute_run_checksum(cand_rows)

    existing = session.exec(
        select(MarketAcquisitionNormalizationRun)
        .where(
            MarketAcquisitionNormalizationRun.ingestion_batch_id == payload.ingestion_batch_id,
            MarketAcquisitionNormalizationRun.run_checksum == chk,
        )
        .order_by(col(MarketAcquisitionNormalizationRun.id).desc())
    ).first()

    now = utc_now()

    if existing is not None and existing.run_status == "COMPLETED":
        return run_detail(session, run_row=existing), False

    if existing is not None and existing.run_status == "RUNNING":
        raise HTTPException(status_code=409, detail="Normalization already running for this checksum.")

    if existing is not None and existing.run_status == "FAILED":
        rid_fail = existing.id or 0
        _wipe_children_for_failed_run(session, run_id=rid_fail)
        existing.run_status = "RUNNING"
        existing.total_records = len(cand_rows)
        existing.successful_records = existing.partial_records = existing.failed_records = 0
        existing.started_at = now
        existing.completed_at = None
        session.add(existing)
        session.flush()
        run_row = existing
    elif existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Unhandled normalization state: {existing.run_status}",
        )
    else:
        run_row = MarketAcquisitionNormalizationRun(
            ingestion_batch_id=payload.ingestion_batch_id,
            owner_user_id=batch.owner_user_id,
            run_status="RUNNING",
            total_records=len(cand_rows),
            successful_records=0,
            partial_records=0,
            failed_records=0,
            run_checksum=chk,
            started_at=now,
            completed_at=None,
            created_at=now,
        )
        session.add(run_row)
        session.flush()

    rid = run_row.id
    if rid is None:
        raise ValueError("normalization run must have id after flush")

    cand_pk_list = [int(c.id or 0) for c in cand_rows if (c.id is not None)]
    if cand_pk_list:
        session.exec(
            delete(MarketAcquisitionNormalizedCandidate).where(
                MarketAcquisitionNormalizedCandidate.ingestion_candidate_id.in_(cand_pk_list)
            ),
        )

    _append_event(session, run_id=int(rid), event_type="RUN_STARTED", metadata_json={"run_checksum": chk}, created_at=now)
    append_market_feed_event(
        session,
        owner_user_id=int(batch.owner_user_id) if batch.owner_user_id is not None else None,
        event_type="NORMALIZATION_RUN_STARTED",
        severity="INFO",
        snapshot_date=now.date(),
        event_payload_json={
            "normalization_run_id": int(rid),
            "ingestion_batch_id": int(batch.id or 0),
            "run_checksum": chk,
        },
        normalization_run_id=int(rid),
        ingestion_batch_id=int(batch.id or 0),
    )

    success = partial = failed = 0

    for candidate in cand_rows:
        cid = candidate.id if candidate.id is not None else 0
        out = deterministic_normalize_candidate(candidate)

        nc = MarketAcquisitionNormalizedCandidate(
            ingestion_candidate_id=int(cid),
            normalization_run_id=int(rid),
            owner_user_id=candidate.owner_user_id,
            canonical_title=out["canonical_title"],
            canonical_publisher=out["canonical_publisher"],
            canonical_issue_number=out["canonical_issue_number"],
            canonical_variant=out["canonical_variant"],
            normalized_condition_band=out["normalized_condition_band"],
            normalized_price=out["normalized_price"],
            normalized_currency=out["normalized_currency"],
            normalized_fmv_estimate=out["normalized_fmv_estimate"],
            normalized_liquidity_hint=None,
            normalized_grade_potential=None,
            canonical_key=out["canonical_key"],
            normalization_flags_json=out["normalization_flags_json"],
            normalization_status=out["normalization_status"],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(nc)

        for iss in out["issues"]:
            session.add(
                MarketAcquisitionNormalizationIssue(
                    normalization_run_id=int(rid),
                    ingestion_candidate_id=int(cid),
                    issue_type=str(iss["issue_type"]),
                    severity=str(iss["severity"]),
                    issue_detail_json=_json_safe(iss.get("detail", {})),
                    created_at=utc_now(),
                )
            )

        st = str(out["normalization_status"])
        if st == "SUCCESS":
            success += 1
            ev = "RECORD_NORMALIZED"
        elif st == "PARTIAL":
            partial += 1
            ev = "RECORD_PARTIAL"
        else:
            failed += 1
            ev = "RECORD_FAILED"
        _append_event(
            session,
            run_id=int(rid),
            event_type=ev,
            metadata_json={"ingestion_candidate_id": cid, "canonical_key": out["canonical_key"]},
            created_at=utc_now(),
        )

    run_row.total_records = len(cand_rows)
    run_row.successful_records = success
    run_row.partial_records = partial
    run_row.failed_records = failed
    run_row.run_status = "COMPLETED" if len(cand_rows) else "COMPLETED"
    run_row.completed_at = utc_now()
    session.add(run_row)

    _append_event(
        session,
        run_id=int(rid),
        event_type="RUN_COMPLETED",
        metadata_json={
            "successful_records": success,
            "partial_records": partial,
            "failed_records": failed,
            "total_records": len(cand_rows),
        },
        created_at=utc_now(),
    )
    append_market_feed_event(
        session,
        owner_user_id=int(run_row.owner_user_id) if run_row.owner_user_id is not None else None,
        event_type="NORMALIZATION_RUN_COMPLETED",
        severity="CRITICAL" if failed == len(cand_rows) and len(cand_rows) > 0 else ("WARNING" if failed > 0 else "INFO"),
        snapshot_date=now.date(),
        event_payload_json={
            "normalization_run_id": int(rid),
            "ingestion_batch_id": int(batch.id or 0),
            "run_checksum": chk,
            "successful_records": success,
            "partial_records": partial,
            "failed_records": failed,
            "total_records": len(cand_rows),
        },
        normalization_run_id=int(rid),
        ingestion_batch_id=int(batch.id or 0),
    )

    session.commit()
    session.refresh(run_row)
    return run_detail(session, run_row=run_row), True


def _norm_run_summaries_where_owner(
    session: Session,
    *,
    owner_user_id: int,
    ingestion_batch_id: int | None = None,
):
    stmt = select(MarketAcquisitionNormalizationRun).where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id)
    if ingestion_batch_id is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    return stmt


def _norm_run_summaries_where_ops(
    session: Session,
    *,
    owner_user_id_filter: int | None = None,
    ingestion_batch_id: int | None = None,
):
    stmt = select(MarketAcquisitionNormalizationRun)
    if ingestion_batch_id is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    if owner_user_id_filter is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id_filter)
    return stmt


def list_normalization_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    ingestion_batch_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketNormalizationRunListResponse:
    limit, offset = clamp_market_normalization_pagination(limit=limit, offset=offset)
    stmt = _norm_run_summaries_where_owner(session, owner_user_id=owner_user_id, ingestion_batch_id=ingestion_batch_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionNormalizationRun.created_at).desc(),
                col(MarketAcquisitionNormalizationRun.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    counts_stmt = (
        select(MarketAcquisitionNormalizationRun.run_status, func.count())
        .where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id)
        .group_by(MarketAcquisitionNormalizationRun.run_status)
    )
    if ingestion_batch_id is not None:
        counts_stmt = counts_stmt.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    status_rows = list(session.exec(counts_stmt).all())
    health = _health_aggregate_for_owner(session, owner_user_id=owner_user_id)
    return MarketNormalizationRunListResponse(
        items=[MarketNormalizationRunSummaryRead.model_validate(r, from_attributes=True) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
        status_counts={str(s): int(c) for s, c in status_rows},
        health=health,
    )


def list_normalization_runs_ops(
    session: Session,
    *,
    owner_user_id_filter: int | None = None,
    ingestion_batch_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketNormalizationRunListResponse:
    limit, offset = clamp_market_normalization_pagination(limit=limit, offset=offset)
    stmt = _norm_run_summaries_where_ops(
        session, owner_user_id_filter=owner_user_id_filter, ingestion_batch_id=ingestion_batch_id,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionNormalizationRun.created_at).desc(),
                col(MarketAcquisitionNormalizationRun.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    counts_base = select(MarketAcquisitionNormalizationRun.run_status, func.count()).group_by(
        MarketAcquisitionNormalizationRun.run_status
    )
    if ingestion_batch_id is not None:
        counts_base = counts_base.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    if owner_user_id_filter is not None:
        counts_base = counts_base.where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id_filter)
    status_rows = list(session.exec(counts_base).all())
    health = _health_aggregate_for_ops(session, owner_user_id_filter=owner_user_id_filter)
    return MarketNormalizationRunListResponse(
        items=[MarketNormalizationRunSummaryRead.model_validate(r, from_attributes=True) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
        status_counts={str(s): int(c) for s, c in status_rows},
        health=health,
    )


def get_normalization_run_owner(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int,
) -> MarketNormalizationRunDetailRead:
    row = session.get(MarketAcquisitionNormalizationRun, run_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Normalization run not found")
    return run_detail(session, run_row=row)


def get_normalization_run_ops(session: Session, *, run_id: int) -> MarketNormalizationRunDetailRead:
    row = session.get(MarketAcquisitionNormalizationRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Normalization run not found")
    return run_detail(session, run_row=row)


def _health_aggregate_for_owner(session: Session, *, owner_user_id: int) -> MarketNormalizationHealthRead:
    run_where = MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id
    return _health_aggregate_where(session, run_where_clause=run_where)


def _health_aggregate_for_ops(session: Session, *, owner_user_id_filter: int | None) -> MarketNormalizationHealthRead:
    if owner_user_id_filter is None:
        return _health_aggregate_where(session, run_where_clause=None)
    return _health_aggregate_where(
        session, run_where_clause=MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id_filter,
    )


def _health_aggregate_where(
    session: Session,
    *,
    run_where_clause: Any | None,
) -> MarketNormalizationHealthRead:
    cand_stmt = select(MarketAcquisitionNormalizedCandidate)
    if run_where_clause is not None:
        cand_stmt = cand_stmt.join(
            MarketAcquisitionNormalizationRun,
            MarketAcquisitionNormalizedCandidate.normalization_run_id == MarketAcquisitionNormalizationRun.id,
        ).where(run_where_clause)
    rows = list(session.exec(cand_stmt).all())
    status_counts: dict[str, int] = {}
    issue_type_counts: dict[str, int] = {}
    norm_flag_counts: dict[str, int] = {}
    for r in rows:
        status_counts[r.normalization_status] = status_counts.get(r.normalization_status, 0) + 1
        fj = r.normalization_flags_json or {}
        if fj.get("missing_publisher"):
            norm_flag_counts["missing_publisher"] = norm_flag_counts.get("missing_publisher", 0) + 1
        if fj.get("ambiguous_title"):
            norm_flag_counts["ambiguous_title"] = norm_flag_counts.get("ambiguous_title", 0) + 1
        if fj.get("invalid_price"):
            norm_flag_counts["invalid_price"] = norm_flag_counts.get("invalid_price", 0) + 1

    stmt_runs = select(MarketAcquisitionNormalizationRun)
    if run_where_clause is not None:
        stmt_runs = stmt_runs.where(run_where_clause)
    runs = list(session.exec(stmt_runs).all())

    completed_at = [
        rr.completed_at
        for rr in runs
        if rr.completed_at is not None and rr.run_status == "COMPLETED"
    ]
    completed_at_sorted = sorted([d for d in completed_at if d is not None], reverse=True)
    last_at = completed_at_sorted[0] if completed_at_sorted else None

    issue_stmt = select(MarketAcquisitionNormalizationIssue)
    if run_where_clause is not None:
        issue_stmt = (
            select(MarketAcquisitionNormalizationIssue)
            .join(
                MarketAcquisitionNormalizationRun,
                MarketAcquisitionNormalizationIssue.normalization_run_id == MarketAcquisitionNormalizationRun.id,
            )
            .where(run_where_clause)
        )
    issue_rows = list(session.exec(issue_stmt).all())
    for ir in issue_rows:
        issue_type_counts[ir.issue_type] = issue_type_counts.get(ir.issue_type, 0) + 1

    total_candidates = sum(status_counts.values())
    pct: Decimal | None = None
    if total_candidates:
        succ = Decimal(status_counts.get("SUCCESS", 0))
        pct = (succ / Decimal(total_candidates)) * Decimal("100")
        pct = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return MarketNormalizationHealthRead(
        candidate_status_counts=status_counts,
        issue_type_counts=issue_type_counts,
        normalization_flag_counts=norm_flag_counts,
        canonical_full_success_rate_pct=pct,
        last_normalization_completed_at=last_at,
    )


def list_normalized_candidates_owner(
    session: Session,
    *,
    owner_user_id: int,
    normalization_status: str | None = None,
    canonical_publisher: str | None = None,
    condition_band: str | None = None,
    ingestion_batch_id: int | None = None,
    created_since: datetime | None = None,
    created_until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionNormalizedCandidateListResponse:
    limit, offset = clamp_market_normalization_pagination(limit=limit, offset=offset)
    stmt = (
        select(MarketAcquisitionNormalizedCandidate)
        .join(
            MarketAcquisitionNormalizationRun,
            MarketAcquisitionNormalizedCandidate.normalization_run_id == MarketAcquisitionNormalizationRun.id,
        )
        .where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id)
    )
    if normalization_status is not None:
        stmt = stmt.where(MarketAcquisitionNormalizedCandidate.normalization_status == normalization_status)
    if canonical_publisher is not None:
        stmt = stmt.where(MarketAcquisitionNormalizedCandidate.canonical_publisher == canonical_publisher)
    if condition_band is not None:
        stmt = stmt.where(MarketAcquisitionNormalizedCandidate.normalized_condition_band == condition_band)
    if ingestion_batch_id is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    if created_since is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizedCandidate.created_at) >= created_since)
    if created_until is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizedCandidate.created_at) <= created_until)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionNormalizedCandidate.created_at).desc(),
                col(MarketAcquisitionNormalizedCandidate.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionNormalizedCandidateListResponse(
        items=[MarketAcquisitionNormalizedCandidateRead.model_validate(r, from_attributes=True) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_normalized_candidates_ops(
    session: Session,
    *,
    owner_user_id_filter: int | None = None,
    normalization_status: str | None = None,
    canonical_publisher: str | None = None,
    condition_band: str | None = None,
    ingestion_batch_id: int | None = None,
    created_since: datetime | None = None,
    created_until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionNormalizedCandidateListResponse:
    limit, offset = clamp_market_normalization_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionNormalizedCandidate).join(
        MarketAcquisitionNormalizationRun,
        MarketAcquisitionNormalizedCandidate.normalization_run_id == MarketAcquisitionNormalizationRun.id,
    )
    if owner_user_id_filter is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id_filter)
    if normalization_status is not None:
        stmt = stmt.where(MarketAcquisitionNormalizedCandidate.normalization_status == normalization_status)
    if canonical_publisher is not None:
        stmt = stmt.where(MarketAcquisitionNormalizedCandidate.canonical_publisher == canonical_publisher)
    if condition_band is not None:
        stmt = stmt.where(MarketAcquisitionNormalizedCandidate.normalized_condition_band == condition_band)
    if ingestion_batch_id is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    if created_since is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizedCandidate.created_at) >= created_since)
    if created_until is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizedCandidate.created_at) <= created_until)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionNormalizedCandidate.created_at).desc(),
                col(MarketAcquisitionNormalizedCandidate.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionNormalizedCandidateListResponse(
        items=[MarketAcquisitionNormalizedCandidateRead.model_validate(r, from_attributes=True) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_normalization_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    issue_type: str | None = None,
    severity: str | None = None,
    ingestion_batch_id: int | None = None,
    created_since: datetime | None = None,
    created_until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketNormalizationIssueListResponse:
    limit, offset = clamp_market_normalization_pagination(limit=limit, offset=offset)
    stmt = (
        select(MarketAcquisitionNormalizationIssue)
        .join(
            MarketAcquisitionNormalizationRun,
            MarketAcquisitionNormalizationIssue.normalization_run_id == MarketAcquisitionNormalizationRun.id,
        )
        .where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id)
    )
    if issue_type is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationIssue.issue_type == issue_type)
    if severity is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationIssue.severity == severity)
    if ingestion_batch_id is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    if created_since is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizationIssue.created_at) >= created_since)
    if created_until is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizationIssue.created_at) <= created_until)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionNormalizationIssue.created_at).desc(),
                col(MarketAcquisitionNormalizationIssue.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketNormalizationIssueListResponse(
        items=[MarketNormalizationIssueRead.model_validate(r, from_attributes=True) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_normalization_issues_ops(
    session: Session,
    *,
    owner_user_id_filter: int | None = None,
    issue_type: str | None = None,
    severity: str | None = None,
    ingestion_batch_id: int | None = None,
    created_since: datetime | None = None,
    created_until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketNormalizationIssueListResponse:
    limit, offset = clamp_market_normalization_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionNormalizationIssue).join(
        MarketAcquisitionNormalizationRun,
        MarketAcquisitionNormalizationIssue.normalization_run_id == MarketAcquisitionNormalizationRun.id,
    )
    if owner_user_id_filter is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.owner_user_id == owner_user_id_filter)
    if issue_type is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationIssue.issue_type == issue_type)
    if severity is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationIssue.severity == severity)
    if ingestion_batch_id is not None:
        stmt = stmt.where(MarketAcquisitionNormalizationRun.ingestion_batch_id == ingestion_batch_id)
    if created_since is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizationIssue.created_at) >= created_since)
    if created_until is not None:
        stmt = stmt.where(col(MarketAcquisitionNormalizationIssue.created_at) <= created_until)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionNormalizationIssue.created_at).desc(),
                col(MarketAcquisitionNormalizationIssue.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketNormalizationIssueListResponse(
        items=[MarketNormalizationIssueRead.model_validate(r, from_attributes=True) for r in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )

