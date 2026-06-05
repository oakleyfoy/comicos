"""P66 printing backfill — proposal, confidence, and apply helpers."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch
from app.models.lunar_feed import LunarFeedRawRow
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.printing_intelligence import (
    PRINTING_KIND_ANNIVERSARY,
    PRINTING_KIND_FACSIMILE,
    PRINTING_KIND_FIRST,
    PRINTING_KIND_REPRINT,
    apply_reprint_issue_guard,
    merge_first_print_issue_dates,
    parse_printing_from_lunar_row,
    printing_badge_label,
    resolve_printing_schedule,
    stamp_original_release_from_external,
)

Confidence = Literal["HIGH", "LOW"]

_REPRINT_HINT = re.compile(
    r"\b(\d{1,2})\s*(?:TH|ST|ND|RD)?\s*PTG\b|"
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+printing\b|"
    r"\bfacsimile\b|"
    r"\banniversary\b",
    re.I,
)

# Certified first-print retail dates when LoCG row is missing (investigation-backed).
KNOWN_FIRST_PRINT_RELEASE: dict[tuple[str, str, str], date] = {
    ("Image Comics", "Tigress Island", "1"): date(2026, 3, 11),
}


def lunar_row_dict(payload: dict) -> dict[str, str]:
    return {str(k): str(v) if v is not None else "" for k, v in payload.items()}


def parse_lunar_date(value: str) -> date | None:
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


def load_lunar_reprint_index(session: Session) -> dict[str, dict]:
    rows = session.exec(select(LunarFeedRawRow).limit(5000)).all()
    index: dict[str, dict] = {}
    for row in rows:
        payload = row.row_payload_json or {}
        code = (payload.get("Code") or row.product_code or "").strip()
        if not code:
            continue
        profile = parse_printing_from_lunar_row(lunar_row_dict(payload))
        if profile.is_reprint_line or _REPRINT_HINT.search(str(payload.get("Title") or "")):
            index[code] = payload
    return index


def locg_release_for_issue(session: Session, *, owner_user_id: int, issue_id: int) -> date | None:
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


def known_first_print_release(*, publisher: str, series_name: str, issue_number: str) -> date | None:
    key = (publisher.strip(), series_name.strip(), issue_number.strip().lstrip("#"))
    return KNOWN_FIRST_PRINT_RELEASE.get(key)


def classify_confidence(proposal: dict[str, Any]) -> Confidence:
    updates = proposal.get("variant_updates") or []
    if not updates:
        return "LOW"
    if proposal.get("known_first_print_release") and _pollution_fingerprint(proposal):
        return "HIGH"
    kinds = {u.get("printing_kind") for u in updates}
    if PRINTING_KIND_FACSIMILE in kinds or PRINTING_KIND_ANNIVERSARY in kinds:
        if not _pollution_fingerprint(proposal):
            return "LOW"
    if proposal.get("locg_first_print_release") and _pollution_fingerprint(proposal):
        return "HIGH"
    if not _pollution_fingerprint(proposal):
        return "LOW"
    release_dates = {u.get("printing_release_date") for u in updates if u.get("printing_release_date")}
    if len(release_dates) > 1:
        return "LOW"
    return "HIGH"


def _clear_issue_schedule_matching_reprint_variants(
    issue: ReleaseIssue,
    proposal: dict[str, Any],
    *,
    foc_only: bool = False,
) -> None:
    for row in proposal.get("variant_updates") or []:
        rel = row.get("printing_release_date")
        foc = row.get("printing_foc_date")
        if not foc_only and issue.release_date and rel and issue.release_date.isoformat() == rel:
            if issue.original_release_date is None or issue.release_date != issue.original_release_date:
                issue.release_date = None
        if issue.foc_date and foc and issue.foc_date.isoformat() == foc:
            issue.foc_date = None


def _pollution_fingerprint(proposal: dict[str, Any]) -> bool:
    before = proposal.get("before_issue") or {}
    updates = proposal.get("variant_updates") or []
    if not updates:
        return False
    top = updates[0]
    rel = top.get("printing_release_date")
    foc = top.get("printing_foc_date")
    if rel and before.get("release_date") == rel:
        return True
    if foc and before.get("foc_date") == foc:
        return True
    return False


def build_proposal(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variants: list[ReleaseVariant],
    lunar_by_code: dict[str, dict],
) -> dict[str, Any] | None:
    reprint_variants: list[dict[str, Any]] = []
    for v in variants:
        code = (v.source_item_code or "").strip()
        if not code or code not in lunar_by_code:
            continue
        profile = parse_printing_from_lunar_row(lunar_row_dict(lunar_by_code[code]))
        if not profile.is_reprint_line:
            continue
        row = lunar_by_code[code]
        foc = parse_lunar_date(str(row.get("FOCDate") or row.get("FOC Date") or ""))
        rel = parse_lunar_date(str(row.get("InStoreDate") or row.get("In-Store Date") or ""))
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

    if not reprint_variants:
        return None

    locg_release = locg_release_for_issue(session, owner_user_id=owner_user_id, issue_id=int(issue.id or 0))
    known_release = known_first_print_release(
        publisher=series.publisher,
        series_name=series.series_name,
        issue_number=issue.issue_number,
    )
    proposed_original_release = locg_release or known_release or issue.original_release_date
    proposed_original_foc = issue.original_foc_date

    polluted_release = issue.release_date
    if proposed_original_release is None and reprint_variants:
        for rv in reprint_variants:
            if rv["printing_release_date"]:
                polluted_release = date.fromisoformat(rv["printing_release_date"])
                break
    if locg_release and polluted_release and locg_release < polluted_release:
        proposed_original_release = locg_release
    if known_release and polluted_release and known_release < polluted_release:
        proposed_original_release = known_release

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
    top = max(reprint_variants, key=lambda r: r["printing_number"] or 0)
    proposed_badge = printing_badge_label(
        printing_kind=str(top["printing_kind"]),
        printing_number=top.get("printing_number"),
    )

    proposal = {
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
        "known_first_print_release": known_release.isoformat() if known_release else None,
        "needs_locg_original_stamp": proposed_original_release is None,
        "current_ui_badge": ui_ctx.printing_badge,
        "proposed_ui_badge_after_backfill": proposed_badge,
        "would_change_issue_dates": before_issue != after_issue,
    }
    proposal["confidence"] = classify_confidence(proposal)
    return proposal


def candidate_issue_ids(
    session: Session,
    *,
    owner_user_id: int | None,
    lunar_by_code: dict[str, dict],
    issue_id: int | None = None,
    limit: int | None = None,
    exclude_issue_ids: set[int] | None = None,
) -> list[int]:
    if issue_id is not None:
        return [issue_id]
    reprint_codes = list(lunar_by_code.keys())
    if not reprint_codes:
        return []
    q = (
        select(ReleaseVariant.issue_id)
        .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
        .where(ReleaseVariant.source_item_code.in_(reprint_codes))
        .distinct()
    )
    if owner_user_id is not None:
        q = q.where(ReleaseIssue.owner_user_id == owner_user_id)
    ids = [int(x) for x in session.exec(q).all() if x is not None]
    if exclude_issue_ids:
        ids = [i for i in ids if i not in exclude_issue_ids]
    ids.sort()
    if limit is not None:
        ids = ids[: max(0, limit)]
    return ids


def apply_proposal(
    session: Session,
    proposal: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Mutate DB rows for one proposal. Caller owns transaction."""
    issue_id = int(proposal["release_issue_id"])
    issue = session.get(ReleaseIssue, issue_id)
    if issue is None:
        raise ValueError(f"release_issue {issue_id} not found")

    before_apply = {
        "issue": {
            "release_date": issue.release_date.isoformat() if issue.release_date else None,
            "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
            "original_release_date": issue.original_release_date.isoformat() if issue.original_release_date else None,
            "original_foc_date": issue.original_foc_date.isoformat() if issue.original_foc_date else None,
        },
        "variants": [],
    }

    variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id)).all())
    by_id = {int(v.id or 0): v for v in variants}
    for row in proposal.get("variant_updates") or []:
        vid = int(row["variant_id"])
        variant = by_id.get(vid)
        if variant is None:
            raise ValueError(f"release_variant {vid} not found for issue {issue_id}")
        before_apply["variants"].append(
            {
                "variant_id": vid,
                "printing_kind": variant.printing_kind,
                "printing_number": variant.printing_number,
                "printing_foc_date": variant.printing_foc_date.isoformat() if variant.printing_foc_date else None,
                "printing_release_date": variant.printing_release_date.isoformat() if variant.printing_release_date else None,
            }
        )
        variant.printing_number = row.get("printing_number")
        variant.printing_kind = row.get("printing_kind") or PRINTING_KIND_REPRINT
        if row.get("printing_foc_date"):
            variant.printing_foc_date = date.fromisoformat(row["printing_foc_date"])
        if row.get("printing_release_date"):
            variant.printing_release_date = date.fromisoformat(row["printing_release_date"])
        session.add(variant)

    locg_date = proposal.get("locg_first_print_release")
    known_date = proposal.get("known_first_print_release")
    stamp_date: date | None = None
    if locg_date:
        stamp_date = date.fromisoformat(locg_date)
    elif known_date:
        stamp_date = date.fromisoformat(known_date)

    has_original_release = issue.original_release_date is not None
    has_original_foc = issue.original_foc_date is not None

    if stamp_date is not None:
        if not has_original_release or force:
            stamp_original_release_from_external(
                issue,
                release_date=stamp_date,
                title=proposal.get("title") or "",
            )
        else:
            apply_reprint_issue_guard(issue)
    elif has_original_release or has_original_foc:
        apply_reprint_issue_guard(issue)
    else:
        if _pollution_fingerprint(proposal):
            _clear_issue_schedule_matching_reprint_variants(issue, proposal)

    if issue.original_foc_date is None:
        _clear_issue_schedule_matching_reprint_variants(issue, proposal, foc_only=True)

    session.add(issue)
    session.flush()

    after_variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id)).all())
    ui = resolve_printing_schedule(issue, after_variants)
    after_apply = {
        "issue": {
            "release_date": issue.release_date.isoformat() if issue.release_date else None,
            "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
            "original_release_date": issue.original_release_date.isoformat() if issue.original_release_date else None,
            "original_foc_date": issue.original_foc_date.isoformat() if issue.original_foc_date else None,
        },
        "ui_badge": ui.printing_badge,
    }
    return {"before": before_apply, "after": after_apply}


def _breakdown_from_proposals(proposals: list[dict[str, Any]], *, applied_ids: set[int]) -> dict[str, Any]:
    from collections import Counter

    pub = Counter()
    kinds = Counter()
    for p in proposals:
        iid = int(p.get("release_issue_id") or 0)
        if iid not in applied_ids:
            continue
        pub[(p.get("publisher") or "unknown").strip()] += 1
        for vu in p.get("variant_updates") or []:
            kinds[str(vu.get("printing_kind") or "unknown")] += 1
    return {
        "publisher": dict(sorted(pub.items(), key=lambda x: (-x[1], x[0]))),
        "printing_kind_on_variants": dict(sorted(kinds.items(), key=lambda x: (-x[1], x[0]))),
    }


def run_backfill(
    session: Session,
    *,
    owner_user_id: int | None,
    issue_id: int | None = None,
    limit: int | None = None,
    apply: bool = False,
    force: bool = False,
    high_confidence_only: bool = True,
    exclude_issue_ids: set[int] | None = None,
    omit_proposals: bool = False,
) -> dict[str, Any]:
    lunar_by_code = load_lunar_reprint_index(session)
    issue_ids = candidate_issue_ids(
        session,
        owner_user_id=owner_user_id,
        lunar_by_code=lunar_by_code,
        issue_id=issue_id,
        limit=limit,
        exclude_issue_ids=exclude_issue_ids,
    )

    proposals: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    skipped_low: list[dict[str, Any]] = []
    skipped_no_proposal: list[int] = []
    errors: list[dict[str, Any]] = []

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
        proposal = build_proposal(
            session,
            owner_user_id=int(issue.owner_user_id),
            issue=issue,
            series=series,
            variants=variants,
            lunar_by_code=lunar_by_code,
        )
        if proposal is None:
            skipped_no_proposal.append(iid)
            continue
        proposals.append(proposal)

        if high_confidence_only and proposal.get("confidence") != "HIGH":
            skipped_low.append({"release_issue_id": iid, "reason": "low_confidence", "proposal": proposal})
            continue

        if not apply:
            continue

        try:
            result = apply_proposal(session, proposal, force=force)
            applied.append({"release_issue_id": iid, "confidence": proposal["confidence"], **result})
        except Exception as exc:  # noqa: BLE001
            errors.append({"release_issue_id": iid, "error": str(exc)})
            raise

    variant_rows = sum(len(p.get("variant_updates") or []) for p in proposals)
    high = [p for p in proposals if p.get("confidence") == "HIGH"]
    low = [p for p in proposals if p.get("confidence") == "LOW"]
    tigress = [
        p
        for p in proposals
        if (p.get("series") or "").lower() == "tigress island" and p.get("issue_number") == "1"
    ]

    applied_ids = {int(a["release_issue_id"]) for a in applied}
    breakdown = _breakdown_from_proposals(proposals, applied_ids=applied_ids) if apply else {}

    return {
        "dry_run": not apply,
        "apply": apply,
        "force": force,
        "owner_user_id_filter": owner_user_id,
        "exclude_issue_ids": sorted(exclude_issue_ids) if exclude_issue_ids else [],
        "candidates_scanned": len(issue_ids),
        "summary": {
            "proposal_count": len(proposals),
            "variant_update_count": variant_rows,
            "high_confidence_count": len(high),
            "low_confidence_count": len(low),
            "applied_count": len(applied) if apply else 0,
            "skipped_low_confidence": len(skipped_low),
            "skipped_no_proposal": len(skipped_no_proposal),
            "skipped_total": len(skipped_low) + len(skipped_no_proposal),
            "error_count": len(errors),
            "failed_count": len(errors),
            **({"breakdown": breakdown} if breakdown else {}),
        },
        "proposals": [] if omit_proposals else proposals,
        "applied": applied,
        "skipped_low_confidence": skipped_low,
        "skipped_no_proposal": skipped_no_proposal,
        "errors": errors,
        "tigress_island_1": tigress[0] if tigress else None,
    }
