"""Dump end-to-end intake trace for one barcode from DB + image replay (read-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session, create_engine, select

from app.core.config import get_settings
from app.models.intake_queue import IntakeSessionItem
from app.services.barcode_validation_service import (
    barcode_encoded_issue_number,
    effective_publisher_for_barcode,
)
from app.services.gcd_catalog_import_dashboard_service import resolve_cache_path, resolve_gcd_path
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.p106_1_gcd_non_barcode_recovery_service import (
    _prepare_scoring_candidates,
    _query_gcd_empty_barcode_candidates,
    _score_candidate_breakdown,
    build_p106_1_intake_hint_snapshot,
    diagnose_gcd_non_barcode_recovery,
    has_reliable_series_hint,
)
from app.services.p106_barcode_gap_resolver_service import (
    barcode_gap_payload_from_diagnosis,
    diagnose_barcode_gap,
)
from app.services.p105_comic_barcode_read_service import read_comic_barcode_from_image_bytes
from app.services.recognition.ocr_matcher import extract_ocr_signal


def _j(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


def main() -> None:
    barcode = sys.argv[1] if len(sys.argv) > 1 else "75960620629200111"
    settings = get_settings()
    engine = create_engine(settings.database_url)
    gcd_path = resolve_gcd_path(None)
    cache_path = resolve_cache_path(None)

    with Session(engine) as session:
        items = list(
            session.exec(
                select(IntakeSessionItem)
                .where(IntakeSessionItem.normalized_barcode == barcode)
                .order_by(IntakeSessionItem.id.desc())
                .limit(5)
            ).all()
        )
        if not items:
            items = list(
                session.exec(
                    select(IntakeSessionItem)
                    .where(IntakeSessionItem.raw_barcode.contains(barcode[:12]))
                    .order_by(IntakeSessionItem.id.desc())
                    .limit(5)
                ).all()
            )

        item = items[0] if items else None
        report: dict = {"barcode_query": barcode, "items_found": len(items)}

        encoded = barcode_encoded_issue_number(barcode)
        inferred_pub = effective_publisher_for_barcode(barcode, None)
        report["stage1_barcode_identity"] = {
            "barcode": barcode,
            "encoded_issue_from_supplement": encoded,
            "inferred_publisher_from_prefix": inferred_pub,
        }

        image_bytes: bytes | None = None
        image_path: Path | None = None
        p105_snapshot = None
        ocr_signal = None

        if item is not None:
            report["intake_item"] = {
                "id": item.id,
                "session_id": item.session_id,
                "status": item.status,
                "match_source": item.match_source,
                "reason": item.reason,
                "error": item.error,
                "matched_series": item.matched_series,
                "matched_issue_number": item.matched_issue_number,
                "matched_publisher": item.matched_publisher,
                "matched_year": item.matched_year,
                "normalized_barcode": item.normalized_barcode,
                "raw_barcode": item.raw_barcode,
                "base_upc": item.base_upc,
                "extension": item.extension,
            }
            try:
                br = json.loads(item.barcode_read_json or "{}")
            except json.JSONDecodeError:
                br = {}
            report["persisted_barcode_read_json"] = br
            report["stage7_barcode_gap_persisted"] = br.get("barcode_gap")

            try:
                image_path = resolve_photo_import_storage_path(item.storage_path, image_id=int(item.id or 0))
                if image_path.is_file():
                    image_bytes = image_path.read_bytes()
                    report["image"] = {"path": str(image_path), "bytes": len(image_bytes)}
                    p105 = read_comic_barcode_from_image_bytes(
                        image_bytes,
                        session=session,
                        cover_path=image_path,
                        intake_item_id=int(item.id or 0),
                        log_context=f"trace item_id={item.id}",
                    )
                    p105_snapshot = json.loads(p105.to_json())
                    ocr_signal = extract_ocr_signal(
                        image_bytes, source_name=f"trace-{item.id}"
                    )
            except Exception as exc:
                report["image_error"] = str(exc)

        if p105_snapshot:
            report["stage1_from_p105"] = {
                "reconstructed_full": p105_snapshot.get("reconstructed_full"),
                "main_upc": p105_snapshot.get("main_upc"),
                "final_supplement": p105_snapshot.get("final_supplement"),
                "decoded_supplement": p105_snapshot.get("decoded_supplement"),
                "supplement_decode_confidence": p105_snapshot.get("supplement_decode_confidence"),
                "inferred_supplement": p105_snapshot.get("inferred_supplement"),
                "barcode_confidence_proxy": p105_snapshot.get("confidence"),
            }
        if ocr_signal:
            report["stage2_ocr"] = {
                "ocr_engine_available": ocr_signal.ocr_engine_available,
                "ocr_error": ocr_signal.ocr_error,
                "title": ocr_signal.title,
                "issue_number": ocr_signal.issue_number,
                "publisher": ocr_signal.publisher,
                "confidence": ocr_signal.confidence,
                "raw_ocr_text_excerpt": (ocr_signal.raw_text or "")[:500],
                "facsimile_from_raw": "facsimile" in (ocr_signal.raw_text or "").lower()
                or "reprint" in (ocr_signal.raw_text or "").lower(),
            }

        p106 = diagnose_barcode_gap(session, barcode=barcode, gcd_path=gcd_path, cache_path=cache_path)
        report["p106_diagnosis_summary"] = {
            "gcd_match_count": p106.get("gcd_match_count"),
            "status": p106.get("status"),
            "reason": p106.get("reason"),
            "gcd_lookup_final_reason": p106.get("gcd_lookup_final_reason"),
        }

        fake_item = item
        if fake_item is None:
            class _Fake:
                id = 0
                matched_publisher = inferred_pub
                matched_series = None
                matched_issue_number = str(encoded) if encoded is not None else None
                matched_year = None

            fake_item = _Fake()

        hints, hint_snapshot = build_p106_1_intake_hint_snapshot(
            session,
            item=fake_item,
            barcode=barcode,
            image_path=image_path,
            image_bytes=image_bytes,
            p105=None,
        )
        report["stage4_hint_snapshot"] = hint_snapshot
        report["stage4_recovery_hints"] = {
            "publisher": hints.publisher,
            "series": hints.series,
            "issue_number": hints.issue_number,
            "year": hints.year,
            "ocr_title": hints.ocr_title,
            "ocr_issue_number": hints.ocr_issue_number,
            "ocr_publisher": hints.ocr_publisher,
            "ocr_confidence": hints.ocr_confidence,
            "raw_ocr_text_excerpt": hints.raw_ocr_text_excerpt,
            "facsimile_or_reprint": hints.facsimile_or_reprint,
            "series_hint_reliable": has_reliable_series_hint(hints.series),
            "ocr_engine_available": hints.ocr_engine_available,
            "ocr_error": hints.ocr_error,
        }

        candidates = _query_gcd_empty_barcode_candidates(gcd_path, issue_number=hints.issue_number)
        publisher_filtered = [
            c for c in candidates if str(c.get("publisher") or "").lower().startswith("marvel")
            or "marvel" in str(c.get("publisher") or "").lower()
        ]
        if hints.publisher:
            from app.services.p106_1_gcd_non_barcode_recovery_service import _publisher_matches

            publisher_filtered = [
                c for c in candidates if _publisher_matches(hints.publisher, str(c.get("publisher") or ""))
            ]

        scorable, pool_block = _prepare_scoring_candidates(
            session,
            hints=hints,
            image_path=image_path,
            prior_diagnosis=p106,
            publisher_filtered=publisher_filtered,
        )

        filter_steps = {
            "empty_barcode_sql_candidates": len(candidates),
            "after_publisher_filter": len(publisher_filtered),
            "scorable_after_pool_gate": len(scorable),
            "pool_block_reason": pool_block,
            "series_hint_reliable": has_reliable_series_hint(hints.series),
        }
        report["stage5_filtering"] = filter_steps

        scored_preview = []
        for row in scorable[:10]:
            _, breakdown = _score_candidate_breakdown(session, row=row, hints=hints, image_path=image_path)
            scored_preview.append(
                {
                    "gcd_issue_id": row.get("gcd_issue_id"),
                    "series": row.get("series"),
                    "issue_number": row.get("issue_number"),
                    "title": row.get("title"),
                    "breakdown": breakdown,
                }
            )
        report["stage6_top_scored"] = scored_preview

        p106_1 = diagnose_gcd_non_barcode_recovery(
            session,
            barcode=barcode,
            gcd_path=gcd_path,
            cache_path=cache_path,
            hints=hints,
            image_path=image_path,
            prior_diagnosis=p106,
        )
        inst = p106_1.get("p106_1_instrumentation") or {}
        report["stage6_final"] = {
            "recovery_block_reason": p106_1.get("recovery_block_reason"),
            "recovery_reason": p106_1.get("recovery_reason"),
            "ready_to_auto_import": p106_1.get("ready_to_auto_import"),
            "status": p106_1.get("status"),
            "reason": p106_1.get("reason"),
            "pick_decision": inst.get("pick_decision"),
            "instrumentation_keys": list(inst.keys()),
        }
        report["stage5_p106_1_instrumentation"] = inst

        merged_diag = dict(p106)
        merged_diag.update({k: v for k, v in p106_1.items() if k not in ("p106_1_skipped",)})
        report["stage7_barcode_gap_replay"] = barcode_gap_payload_from_diagnosis(merged_diag)

        gap = report.get("stage7_barcode_gap_persisted") or {}
        ms = (item.matched_series if item else None) or ""
        gs = gap.get("gcd_series") if isinstance(gap, dict) else None
        report["stage8_ui"] = {
            "intakeHeadline_logic": "series from matched_series OR gap.gcd_series unless gap authoritative",
            "matched_series_on_item": ms,
            "barcode_gap_gcd_series": gs,
            "barcode_gap_action": gap.get("action") if isinstance(gap, dict) else None,
            "barcode_gap_gcd_match_count": gap.get("gcd_match_count") if isinstance(gap, dict) else None,
            "would_show_unidentified": not bool(str(ms).strip() or (str(gs or "").strip())),
        }

    print(_j(report))


if __name__ == "__main__":
    main()
