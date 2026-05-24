"""Deterministic scan QA routing — signals + recommendations only (no OCR enqueue)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from sqlalchemy import delete
from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import CoverImage, CoverImageOcrQualityAnalysis, ScanQaResult, ScanSession, ScanSessionItem
from app.models.asset_ledger import utc_now
from app.schemas.scan_qa import (
    InventoryCoverScanQaRow,
    InventoryScanQaPanelRead,
    OpsScanQaFleetSummaryRead,
    ScanQaItemRead,
    ScanSessionQaSummaryRead,
)

ALLOWED_IMAGE_MIME = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff"},
)

EXTENSION_MIME_HINT: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

QA_CLASS_RANK: dict[str, int] = {
    "corrupt_or_unreadable": 0,
    "needs_rescan": 5,
    "review_required": 15,
    "duplicate_scan": 25,
    "needs_high_res_review": 30,
    "blurry": 35,
    "low_contrast": 36,
    "low_resolution": 40,
    "already_processed": 80,
    "ready_for_ocr": 95,
}

SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}

PHONE_PROFILE_KEYS = frozenset({"phone", "phone_camera"})


def _infer_mime_from_filename(filename: str | None, cover_mime: str | None = None) -> str | None:
    if cover_mime:
        val = cover_mime.strip().lower()
        return val if val else None
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    if ext == "":
        return None
    return EXTENSION_MIME_HINT.get(f".{ext}")


def _max_severity(existing: str, candidate: str) -> str:
    return candidate if SEVERITY_RANK.get(candidate, 0) > SEVERITY_RANK.get(existing, 0) else existing


def _quality_map(rows: Sequence[CoverImageOcrQualityAnalysis]) -> MutableMapping[str, CoverImageOcrQualityAnalysis]:
    """Latest row per quality_type by id tie-break."""

    buckets: MutableMapping[str, CoverImageOcrQualityAnalysis] = {}
    for row in rows:
        cur = buckets.get(row.quality_type)
        if cur is None or int(row.id or 0) > int(cur.id or 0):
            buckets[row.quality_type] = row
    return buckets


def _contains_corrupt_token(message: str | None) -> bool:
    if not message:
        return False
    m = message.lower()
    needles = ("corrupt", "cannot identify", "invalid image", "decode error", "truncated", "not a valid image")
    return any(n in m for n in needles)


def _effective_dimensions(
    item: ScanSessionItem,
    cover: CoverImage | None,
) -> tuple[int | None, int | None]:
    cw, ch = item.image_width, item.image_height
    if cover and cover.image_width and cover.image_height:
        return cover.image_width, cover.image_height
    return cw, ch


def _scanner_bucket(profile: str | None, source_device: str | None) -> str:
    hay = " ".join(
        fragment
        for fragment in ((profile or "").lower(), (source_device or "").lower())
        if fragment
    )
    if any(k in hay for k in PHONE_PROFILE_KEYS):
        return "phone_camera"
    return "flatbed_consumer"


def _build_evidence(
    *,
    item: ScanSessionItem,
    sess: ScanSession,
    mime_inferred: str | None,
    sha_dup_excess_participant: bool,
    quality_buckets: Mapping[str, CoverImageOcrQualityAnalysis] | None,
    cover: CoverImage | None,
) -> tuple[set[str], str, MutableMapping[str, Any]]:
    """Return classifications triggered, aggregated severity (worst wins), deterministic evidence."""

    triggers: set[str] = set()
    severity = "info"
    evidence_signals: list[MutableMapping[str, Any]] = []

    w, h = _effective_dimensions(item, cover)

    mime_ok = mime_inferred is None or mime_inferred in ALLOWED_IMAGE_MIME
    if mime_inferred and not mime_ok:
        triggers.add("corrupt_or_unreadable")
        severity = _max_severity(severity, "warning")
        evidence_signals.append({"kind": "unsupported_mime", "mime_type": mime_inferred})

    if item.ingest_status == "review_required":
        triggers.add("review_required")
        severity = _max_severity(severity, "critical")
        evidence_signals.append({"kind": "ingest_status_review_required"})

    if item.ingest_status == "ocr_complete":
        triggers.add("already_processed")
        severity = _max_severity(severity, "info")
        evidence_signals.append({"kind": "ingest_status_ocr_complete"})

    if item.ingest_status == "failed":
        err_text = item.ingest_error or ""
        if err_text.upper() == "NEEDS_PHYSICAL_RESCAN":
            triggers.add("needs_rescan")
            severity = _max_severity(severity, "warning")
            evidence_signals.append({"kind": "explicit_physical_rescan_marker"})
        elif _contains_corrupt_token(err_text) or mime_ok is False:
            triggers.add("corrupt_or_unreadable")
            severity = _max_severity(severity, "critical")
            evidence_signals.append({"kind": "ingest_failure", "ingest_error": err_text[:500]})
        else:
            triggers.add("corrupt_or_unreadable")
            severity = _max_severity(severity, "warning")
            evidence_signals.append({"kind": "ingest_failure_unknown", "ingest_error": err_text[:500]})

    scan_bucket = _scanner_bucket(sess.scanner_profile, sess.source_device)
    if scan_bucket == "phone_camera" and mime_ok and item.ingest_status not in {"failed"}:
        if w and h and max(w, h) < 900:
            triggers.add("needs_rescan")
            severity = _max_severity(severity, "warning")
            evidence_signals.append({"kind": "phone_camera_under_target_resolution", "width": w, "height": h})

    if cover is not None and cover.processing_status == "failed":
        triggers.add("corrupt_or_unreadable")
        severity = _max_severity(severity, "critical")
        evidence_signals.append(
            {"kind": "cover_processing_failed", "processing_error": (cover.processing_error or "")[:500]},
        )

    if sha_dup_excess_participant and mime_ok and item.ingest_status != "failed":
        triggers.add("duplicate_scan")
        severity = _max_severity(severity, "warning")
        evidence_signals.append({"kind": "duplicate_sha256_within_session"})

    if quality_buckets:
        blur = quality_buckets.get("blur_detection")
        if blur and blur.severity in {"warning", "critical"}:
            triggers.add("blurry")
            severity = _max_severity(severity, blur.severity)
            evidence_signals.append(
                {"kind": "ocr_quality_signal", "quality_type": "blur_detection", "severity": blur.severity},
            )

        lc = quality_buckets.get("low_contrast")
        if lc and lc.severity in {"warning", "critical"}:
            triggers.add("low_contrast")
            severity = _max_severity(severity, lc.severity)
            evidence_signals.append(
                {"kind": "ocr_quality_signal", "quality_type": "low_contrast", "severity": lc.severity},
            )

        lr = quality_buckets.get("low_resolution")
        if lr and lr.severity in {"warning", "critical"}:
            triggers.add("low_resolution")
            severity = _max_severity(severity, lr.severity)
            evidence_signals.append(
                {"kind": "ocr_quality_signal", "quality_type": "low_resolution", "severity": lr.severity},
            )

        overall = quality_buckets.get("overall_quality")
        if overall and overall.severity == "critical":
            triggers.add("needs_high_res_review")
            severity = _max_severity(severity, "critical")
            evidence_signals.append(
                {"kind": "ocr_quality_signal", "quality_type": "overall_quality", "severity": overall.severity},
            )
        elif overall and overall.severity == "warning" and mime_ok:
            dims_for_rule = True
            if w and h and max(w, h) >= 1400:
                dims_for_rule = False
            if dims_for_rule:
                triggers.add("needs_high_res_review")
                severity = _max_severity(severity, "warning")
                evidence_signals.append(
                    {
                        "kind": "overall_quality_escalated_by_dimensions",
                        "quality_type": "overall_quality",
                        "severity": overall.severity,
                        "width": w,
                        "height": h,
                    },
                )

        unreadable = quality_buckets.get("unreadable_ocr")
        if unreadable and unreadable.severity == "critical":
            triggers.add("corrupt_or_unreadable")
            severity = _max_severity(severity, "critical")
            evidence_signals.append(
                {"kind": "ocr_quality_signal", "quality_type": "unreadable_ocr", "severity": unreadable.severity},
            )

    if (
        mime_ok
        and w
        and h
        and max(w, h) < 560
        and item.ingest_status not in {"failed", "skipped"}
        and "low_resolution" not in triggers
    ):
        triggers.add("low_resolution")
        severity = _max_severity(severity, "warning")
        evidence_signals.append({"kind": "dimension_below_minimum", "width": w, "height": h, "threshold": 560})

    if "already_processed" in triggers:
        triggers.discard("duplicate_scan")
        triggers.discard("ready_for_ocr")

    if not triggers:
        if item.ingest_status in {"imported", "pending", "queued_for_ocr"} and mime_ok:
            triggers.add("ready_for_ocr")
            severity = _max_severity(severity, "info")
            evidence_signals.append({"kind": "ready_for_manual_ocr_enqueue"})
        else:
            triggers.add("corrupt_or_unreadable")
            severity = _max_severity(severity, "warning")
            evidence_signals.append({"kind": "unclassified_fallback_state", "ingest_status": item.ingest_status})

    evidence_signals_sorted = sorted(
        evidence_signals,
        key=lambda row: (
            row.get("kind", ""),
            str(row),
        ),
    )

    envelope: MutableMapping[str, Any] = {
        "signals": evidence_signals_sorted,
        "deterministic_notes": sorted(triggers),
        "scan_session_scanner_profile": sess.scanner_profile,
        "scan_session_source_device": sess.source_device,
        "inferred_scanner_bucket": scan_bucket,
        "inferred_source_mime": mime_inferred,
        "effective_width": w,
        "effective_height": h,
    }
    return triggers, severity, envelope


def _choose_primary_classification(triggers: set[str]) -> str:
    return min(triggers, key=lambda label: (QA_CLASS_RANK[label], label))


def routing_for_primary(primary: str, *, severity_worst: str) -> tuple[str, str]:
    routing: str = "queue_for_ocr"
    routed_severity = severity_worst
    match primary:
        case "already_processed":
            routing = "no_action_needed"
        case "duplicate_scan":
            routing = "no_action_needed"
        case "corrupt_or_unreadable":
            routing = "hold_for_manual_review"
            routed_severity = _max_severity(routed_severity, "critical")
        case "review_required":
            routing = "hold_for_manual_review"
        case "needs_high_res_review":
            routing = "send_to_high_res_review"
        case "needs_rescan":
            routing = "request_rescan"
        case "low_resolution":
            routing = (
                "request_rescan"
                if severity_worst == "critical"
                else ("send_to_high_res_review" if severity_worst == "warning" else "queue_for_ocr")
            )
        case "blurry":
            routing = "send_to_high_res_review" if severity_worst == "critical" else "queue_for_ocr"
        case "low_contrast":
            routing = "send_to_high_res_review" if severity_worst == "critical" else "queue_for_ocr"
        case "ready_for_ocr":
            routing = "queue_for_ocr"
        case _:
            routing = "hold_for_manual_review"
    return routing, routed_severity


def _session_hash_dup_flags(items: Sequence[ScanSessionItem]) -> dict[str, bool]:
    hashes = [r.image_sha256 for r in items if r.image_sha256]
    ctr = Counter(hashes)
    return {digest: ctr[digest] > 1 for digest in ctr.keys()}


def compute_qa_items_for_scan_session(session: Session, *, scan_session: ScanSession) -> list[ScanQaItemRead]:
    stmt = (
        select(ScanSessionItem)
        .where(ScanSessionItem.scan_session_id == int(scan_session.id or 0))
        .order_by(ScanSessionItem.sequence_index.asc(), ScanSessionItem.id.asc())
    )
    ordered = list(session.exec(stmt).all())
    dup_sha = _session_hash_dup_flags(ordered)

    cover_ids = {int(r.cover_image_id) for r in ordered if r.cover_image_id is not None}
    covers_by_id: dict[int, CoverImage] = {}
    if cover_ids:
        cover_rows = session.exec(select(CoverImage).where(CoverImage.id.in_(sorted(cover_ids)))).all()
        covers_by_id = {int(c.id): c for c in cover_rows if c.id is not None}

    quality_cover_ids = sorted(cover_ids)
    quality_buckets_by_cover: dict[int, Mapping[str, CoverImageOcrQualityAnalysis]] = {}
    if quality_cover_ids:
        q_stmt = (
            select(CoverImageOcrQualityAnalysis).where(CoverImageOcrQualityAnalysis.cover_image_id.in_(quality_cover_ids))
            # Stable analysis fetch; per-cover bucketing prefers highest id afterwards.
        )
        all_q = session.exec(q_stmt).all()
        grouped: MutableMapping[int, list[CoverImageOcrQualityAnalysis]] = {}
        for row in all_q:
            grouped.setdefault(row.cover_image_id, []).append(row)
        for cid, lst in grouped.items():
            quality_buckets_by_cover[int(cid)] = _quality_map(lst)

    summaries: list[ScanQaItemRead] = []
    if int(scan_session.id or 0) == 0:
        return summaries

    for item in ordered:
        item_id = int(item.id or 0)
        if item_id == 0:
            continue
        cid = int(item.cover_image_id) if item.cover_image_id is not None else None
        cover = covers_by_id.get(cid) if cid is not None else None
        mime = _infer_mime_from_filename(item.source_filename, cover.mime_type.lower() if cover else None)

        qa_map_for_item = quality_buckets_by_cover.get(cid) if cid is not None else None

        sha_flag = False
        if item.image_sha256:
            sha_flag = bool(dup_sha.get(item.image_sha256, False))

        triggers, envelope_severity, evidence = _build_evidence(
            item=item,
            sess=scan_session,
            mime_inferred=mime,
            sha_dup_excess_participant=sha_flag,
            quality_buckets=qa_map_for_item,
            cover=cover,
        )
        primary = _choose_primary_classification(triggers)

        routed, routed_severity = routing_for_primary(primary, severity_worst=envelope_severity)
        evidence_final = dict(evidence)
        evidence_final.update(
            {
                "qa_classification_primary": primary,
                "severity_worst_signal": routed_severity,
                "routing_recommendation_rationale": f"routing_from_classification:{primary}:{routed}",
            },
        )

        summaries.append(
            ScanQaItemRead(
                scan_session_item_id=item_id,
                cover_image_id=cid,
                qa_classification=primary,
                routing_recommendation=routed,
                severity=routed_severity,
                evidence_json=evidence_final,
            ),
        )
    return summaries


def summarize_items(items_read: Sequence[ScanQaItemRead]) -> tuple[dict[str, int], dict[str, int]]:
    by_cls: dict[str, int] = Counter()
    by_route: dict[str, int] = Counter()
    for row in items_read:
        by_cls[row.qa_classification] += 1
        by_route[row.routing_recommendation] += 1
    return dict(sorted(by_cls.items())), dict(sorted(by_route.items()))


def get_scan_session_qa(session: Session, *, owner_user_id: int | None, scan_session_id: int) -> ScanSessionQaSummaryRead:
    sess = session.get(ScanSession, scan_session_id)
    if sess is None or (owner_user_id is not None and sess.owner_user_id != owner_user_id):
        raise HTTPException(status_code=404, detail="Scan session not found")
    assert sess.id is not None
    items = compute_qa_items_for_scan_session(session, scan_session=sess)
    persisted = session.exec(
        select(ScanQaResult).where(ScanQaResult.scan_session_id == int(sess.id)).limit(1)
    ).first()
    totals_cls, totals_route = summarize_items(items)
    return ScanSessionQaSummaryRead(
        scan_session_id=int(sess.id),
        owner_user_id=int(sess.owner_user_id),
        scanner_profile=sess.scanner_profile,
        persisted_run=bool(persisted),
        items=items,
        totals_by_classification=totals_cls,
        totals_by_routing=totals_route,
    )


def get_scan_session_item_qa(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_session_id: int,
    item_id: int,
) -> ScanQaItemRead:
    summary = get_scan_session_qa(session, owner_user_id=owner_user_id, scan_session_id=scan_session_id)
    for row in summary.items:
        if row.scan_session_item_id == item_id:
            return row
    raise HTTPException(status_code=404, detail="Scan session item not found")


def run_scan_session_qa(
    session: Session,
    *,
    owner_user_id: int,
    scan_session_id: int,
) -> ScanSessionQaSummaryRead:
    sess = session.get(ScanSession, scan_session_id)
    if sess is None or sess.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan session not found")
    sid = int(sess.id or 0)
    summaries = compute_qa_items_for_scan_session(session, scan_session=sess)

    stmt_delete = delete(ScanQaResult).where(ScanQaResult.scan_session_id == sid)
    session.execute(stmt_delete)

    now = utc_now()
    for row in summaries:
        session.add(
            ScanQaResult(
                scan_session_id=sid,
                scan_session_item_id=row.scan_session_item_id,
                cover_image_id=row.cover_image_id,
                qa_classification=row.qa_classification,
                routing_recommendation=row.routing_recommendation,
                severity=row.severity,
                evidence_json=row.evidence_json,
                created_at=now,
                updated_at=now,
            ),
        )

    session.commit()
    persisted_summary = get_scan_session_qa(session, owner_user_id=owner_user_id, scan_session_id=sid)
    # Force persisted snapshot flag True after committing new rows.

    persisted_summary = persisted_summary.model_copy(update={"persisted_run": True})
    return persisted_summary


def fleet_scan_qa_summary(session: Session) -> OpsScanQaFleetSummaryRead:
    rows = session.exec(select(ScanQaResult)).all()
    totals_cls = Counter(row.qa_classification for row in rows)
    totals_route = Counter(row.routing_recommendation for row in rows)
    failure_bundle = Counter(
        {
            "corrupt_or_unreadable": totals_cls.get("corrupt_or_unreadable", 0),
            "needs_rescan": totals_cls.get("needs_rescan", 0),
            "duplicate_scan": totals_cls.get("duplicate_scan", 0),
            "review_required_hold": totals_route.get("hold_for_manual_review", 0),
        }
    )
    return OpsScanQaFleetSummaryRead(
        totals_by_classification=dict(sorted(totals_cls.items())),
        totals_by_routing=dict(sorted(totals_route.items())),
        failure_and_rescan=dict(sorted(failure_bundle.items())),
    )


def inventory_cover_scan_qa(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
) -> InventoryScanQaPanelRead:
    from app.models import InventoryCopy  # Lazy import avoids cycles

    inv = session.get(InventoryCopy, inventory_copy_id)
    if inv is None or inv.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    cover_rows = session.exec(
        select(CoverImage).where(CoverImage.inventory_copy_id == inventory_copy_id),
    ).all()
    out: list[InventoryCoverScanQaRow] = []
    sorted_covers = sorted(cover_rows, key=lambda row: int(row.id or 0))

    ghost_session = ScanSession(
        owner_user_id=owner_user_id,
        session_type="manual_upload",
        status="completed",
        scanner_profile=None,
        source_device=None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    for cover in sorted_covers:
        cid = int(cover.id or 0)
        if cid == 0:
            continue

        qa_stmt = select(CoverImageOcrQualityAnalysis).where(CoverImageOcrQualityAnalysis.cover_image_id == cid)
        q_all = session.exec(qa_stmt).all()
        q_map = _quality_map(q_all)

        synthetic_item = ScanSessionItem(
            scan_session_id=0,
            inventory_copy_id=inventory_copy_id,
            cover_image_id=cid,
            source_filename=cover.original_filename,
            sequence_index=0,
            ingest_status="imported",
            ingest_error=None,
            image_width=cover.image_width,
            image_height=cover.image_height,
            image_sha256=cover.sha256_hash,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        triggers, envelope_severity, evidence = _build_evidence(
            item=synthetic_item,
            sess=ghost_session,
            mime_inferred=cover.mime_type.lower(),
            sha_dup_excess_participant=False,
            quality_buckets=q_map,
            cover=cover,
        )
        primary = _choose_primary_classification(triggers)
        routed, routed_severity = routing_for_primary(primary, severity_worst=envelope_severity)
        evidence_final = dict(evidence)
        evidence_final.update({"qa_classification_primary": primary, "cover_only_eval": True})
        out.append(
            InventoryCoverScanQaRow(
                cover_image_id=cid,
                qa_classification=primary,
                routing_recommendation=routed,
                severity=routed_severity,
                evidence_json=evidence_final,
            ),
        )

    return InventoryScanQaPanelRead(inventory_copy_id=inventory_copy_id, covers=out)
