"""P66 printing intelligence backfill — dry run only (no DB writes).

Usage (from apps/api):
  python scripts/printing_intelligence_backfill_dry_run.py
  python scripts/printing_intelligence_backfill_dry_run.py --owner-user-id 1
  python scripts/printing_intelligence_backfill_dry_run.py --json-out ../../data/printing_backfill_dry_run.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from typing import Any

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch
from app.models.lunar_feed import LunarFeedRawRow
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.printing_intelligence import (
    PRINTING_KIND_FIRST,
    parse_printing_from_lunar_row,
    resolve_printing_schedule,
)

_REPRINT_HINT = re.compile(
    r"\b(\d{1,2})\s*(?:TH|ST|ND|RD)?\s*PTG\b|"
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+printing\b|"
    r"\bfacsimile\b|"
    r"\banniversary\b",
    re.I,
)


def _lunar_row_dict(payload: dict) -> dict[str, str]:
    return {str(k): str(v) if v is not None else "" for k, v in payload.items()}


def _variant_needs_backfill(variant: ReleaseVariant, lunar_by_code: dict[str, dict]) -> bool:
    code = (variant.source_item_code or "").strip()
    if code and code in lunar_by_code:
        profile = parse_printing_from_lunar_row(_lunar_row_dict(lunar_by_code[code]))
        if profile.is_reprint_line:
            return True
    if (variant.printing_kind or PRINTING_KIND_FIRST) != PRINTING_KIND_FIRST:
        return True
    if (variant.printing_number or 1) > 1:
        return True
    return False


def _issue_polluted(issue: ReleaseIssue, variants: list[ReleaseVariant], lunar_by_code: dict[str, dict]) -> bool:
    if issue.original_release_date is not None and issue.release_date == issue.original_release_date:
        if all(_variant_needs_backfill(v, lunar_by_code) for v in variants if _variant_needs_backfill(v, lunar_by_code)):
            pass
    for v in variants:
        if _variant_needs_backfill(v, lunar_by_code):
            if v.printing_release_date is None and issue.release_date is not None:
                return True
    if issue.original_release_date is None and issue.release_date is not None:
        for v in variants:
            code = (v.source_item_code or "").strip()
            if code and code in lunar_by_code:
                prof = parse_printing_from_lunar_row(_lunar_row_dict(lunar_by_code[code]))
                if prof.is_reprint_line:
                    return True
    return False


def _locg_release_for_issue(
    session: Session,
    *,
    owner_user_id: int,
    issue_id: int,
) -> date | None:
    match = session.exec(
        select(ExternalCatalogMatch, ExternalCatalogIssue)
        .join(ExternalCatalogIssue, ExternalCatalogMatch.external_issue_id == ExternalCatalogIssue.id)
        .where(ExternalCatalogMatch.owner_user_id == owner_user_id)
        .where(ExternalCatalogMatch.release_issue_id == issue_id)
        .where(ExternalCatalogMatch.match_status == "MATCHED_RELEASE_ISSUE")
    ).first()
    if match is None:
        return None
    _, ext = match
    profile = parse_printing_from_lunar_row({"Title": ext.title or "", "Description": ext.description or ""})
    if profile.is_reprint_line:
        return None
    return ext.release_date


def _propose_issue_fix(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variants: list[ReleaseVariant],
    lunar_by_code: dict[str, dict],
) -> dict[str, Any] | None:
    reprint_variants = []
    for v in variants:
        code = (v.source_item_code or "").strip()
        if not code or code not in lunar_by_code:
            continue
        profile = parse_printing_from_lunar_row(_lunar_row_dict(lunar_by_code[code]))
        if profile.is_reprint_line:
            row = lunar_by_code[code]
            foc = _parse_lunar_date(row.get("FOCDate") or row.get("FOC Date") or "")
            rel = _parse_lunar_date(row.get("InStoreDate") or row.get("In-Store Date") or "")
            reprint_variants.append(
                {
                    "variant_id": v.id,
                    "source_item_code": code,
                    "printing_number": profile.printing_number,
                    "printing_kind": profile.printing_kind,
                    "printing_foc_date": foc.isoformat() if foc else None,
                    "printing_release_date": rel.isoformat() if rel else None,
                    "lunar_title": row.get("Title") or "",
                }
            )

    if not reprint_variants and not _issue_polluted(issue, variants, lunar_by_code):
        return None

    locg_release = _locg_release_for_issue(session, owner_user_id=owner_user_id, issue_id=int(issue.id or 0))
    proposed_original_release = locg_release or issue.original_release_date
    proposed_original_foc = issue.original_foc_date

    polluted_release = issue.release_date
    polluted_foc = issue.foc_date
    if proposed_original_release is None and reprint_variants:
        for rv in reprint_variants:
            if rv["printing_release_date"]:
                polluted_release = date.fromisoformat(rv["printing_release_date"])
                break

    if locg_release and polluted_release and locg_release < polluted_release:
        proposed_original_release = locg_release

    after_issue = {
        "release_date": proposed_original_release.isoformat() if proposed_original_release else None,
        "foc_date": proposed_original_foc.isoformat() if proposed_original_foc else None,
        "original_release_date": proposed_original_release.isoformat() if proposed_original_release else None,
        "original_foc_date": proposed_original_foc.isoformat() if proposed_original_foc else None,
    }
    before_issue = {
        "release_date": issue.release_date.isoformat() if issue.release_date else None,
        "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
        "original_release_date": issue.original_release_date.isoformat() if issue.original_release_date else None,
        "original_foc_date": issue.original_foc_date.isoformat() if issue.original_foc_date else None,
    }

    ui_ctx = resolve_printing_schedule(issue, variants)
    proposed_badge = ""
    if reprint_variants:
        top = max(reprint_variants, key=lambda r: r["printing_number"] or 0)
        from app.services.printing_intelligence import printing_badge_label

        proposed_badge = printing_badge_label(
            printing_kind=top["printing_kind"],
            printing_number=top["printing_number"],
        )

    needs_locg_stamp = proposed_original_release is None and bool(reprint_variants)

    return {
        "release_issue_id": issue.id,
        "owner_user_id": owner_user_id,
        "series": series.series_name,
        "issue_number": issue.issue_number,
        "publisher": series.publisher,
        "title": issue.title,
        "before_issue": before_issue,
        "after_issue": after_issue,
        "variant_updates": reprint_variants,
        "locg_first_print_release": locg_release.isoformat() if locg_release else None,
        "needs_locg_original_stamp": needs_locg_stamp,
        "current_ui_badge": ui_ctx.printing_badge,
        "proposed_ui_badge_after_backfill": proposed_badge,
        "would_change_issue_dates": before_issue != after_issue,
    }


def _parse_lunar_date(value: str) -> date | None:
    from datetime import datetime

    cleaned = (value or "").strip()
    if not cleaned:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            if fmt == "%Y-%m-%d":
                return date.fromisoformat(cleaned)
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _load_lunar_reprint_index(session: Session) -> dict[str, dict]:
    """Only Lunar SKUs that parse as reprint/facsimile/anniversary."""
    rows = session.exec(select(LunarFeedRawRow).limit(5000)).all()
    index: dict[str, dict] = {}
    for row in rows:
        payload = row.row_payload_json or {}
        code = (payload.get("Code") or row.product_code or "").strip()
        if not code:
            continue
        profile = parse_printing_from_lunar_row(_lunar_row_dict(payload))
        if profile.is_reprint_line or _REPRINT_HINT.search(str(payload.get("Title") or "")):
            index[code] = payload
    return index


def run_dry_run(*, owner_user_id: int | None) -> dict[str, Any]:
    engine = get_engine()
    with Session(engine) as session:
        lunar_by_code = _load_lunar_reprint_index(session)
        reprint_codes = list(lunar_by_code.keys())
        if not reprint_codes:
            return {
                "dry_run": True,
                "mutations_applied": 0,
                "owner_user_id_filter": owner_user_id,
                "candidates_scanned": 0,
                "proposals": [],
                "tigress_island_1": None,
                "summary": {"proposal_count": 0, "issues_with_date_changes": 0},
            }

        q = (
            select(ReleaseVariant.issue_id)
            .where(ReleaseVariant.source_item_code.in_(reprint_codes))
            .distinct()
        )
        if owner_user_id is not None:
            q = (
                select(ReleaseVariant.issue_id)
                .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
                .where(ReleaseVariant.source_item_code.in_(reprint_codes))
                .where(ReleaseIssue.owner_user_id == owner_user_id)
                .distinct()
            )
        issue_ids = [int(x) for x in session.exec(q).all() if x is not None]
        proposals: list[dict[str, Any]] = []
        for iid in issue_ids:
            pair = session.exec(
                select(ReleaseIssue, ReleaseSeries)
                .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
                .where(ReleaseIssue.id == iid)
            ).first()
            if pair is None:
                continue
            issue, series = pair
            variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == iid)).all())
            proposal = _propose_issue_fix(
                session,
                owner_user_id=int(issue.owner_user_id),
                issue=issue,
                series=series,
                variants=variants,
                lunar_by_code=lunar_by_code,
            )
            if proposal is not None:
                proposals.append(proposal)

        tigress = [p for p in proposals if "tigress island" in (p.get("series") or "").lower() and p.get("issue_number") == "1"]

        return {
            "dry_run": True,
            "mutations_applied": 0,
            "owner_user_id_filter": owner_user_id,
            "candidates_scanned": len(issue_ids),
            "proposals": proposals,
            "tigress_island_1": tigress[0] if tigress else None,
            "summary": {
                "proposal_count": len(proposals),
                "issues_with_date_changes": sum(1 for p in proposals if p.get("would_change_issue_dates")),
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Printing intelligence backfill dry run")
    parser.add_argument("--owner-user-id", type=int, default=None)
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()
    report = run_dry_run(owner_user_id=args.owner_user_id)
    text_out = json.dumps(report, indent=2, default=str)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(text_out)
    print(text_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
