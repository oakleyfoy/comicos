"""P66-06 Printing intelligence — first print vs reprint/facsimile/anniversary separation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.models.release_intelligence import ReleaseIssue, ReleaseVariant

PRINTING_KIND_FIRST = "FIRST_PRINT"
PRINTING_KIND_REPRINT = "REPRINT"
PRINTING_KIND_FACSIMILE = "FACSIMILE"
PRINTING_KIND_ANNIVERSARY = "ANNIVERSARY_REISSUE"

_ORDINAL_WORD = {
    1: "1st",
    2: "2nd",
    3: "3rd",
    4: "4th",
    5: "5th",
    6: "6th",
    7: "7th",
    8: "8th",
    9: "9th",
    10: "10th",
}

_PTGN_RE = re.compile(r"\b(\d{1,2})\s*(?:TH|ST|ND|RD)?\s*PTG\b", re.I)
_PRINTING_WORD_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+printing\b|\b(second|third|fourth|fifth|sixth)\s+printing\b",
    re.I,
)
_WORD_TO_NUM = {"second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
_FACSIMILE_RE = re.compile(r"\bfacsimile\b", re.I)
_ANNIVERSARY_REISSUE_RE = re.compile(
    r"\b(?:\d{1,3}(?:st|nd|rd|th)\s+)?anniversary(?:\s+(?:edition|reissue|reprint))?\b|\banniversary\s+reissue\b",
    re.I,
)


@dataclass(frozen=True)
class PrintingProfile:
    printing_number: int | None
    printing_kind: str
    badge_label: str
    is_reprint_line: bool


def _ordinal_label(n: int) -> str:
    prefix = _ORDINAL_WORD.get(n, f"{n}th")
    return f"{prefix} Printing"


def printing_badge_label(*, printing_kind: str, printing_number: int | None) -> str:
    if printing_kind == PRINTING_KIND_FACSIMILE:
        return "Facsimile"
    if printing_kind == PRINTING_KIND_ANNIVERSARY:
        return "Anniversary Reissue"
    if printing_kind == PRINTING_KIND_REPRINT and printing_number and printing_number > 1:
        return _ordinal_label(printing_number)
    return ""


def parse_printing_number_from_text(text: str) -> int | None:
    blob = (text or "").strip()
    if not blob:
        return None
    m = _PTGN_RE.search(blob)
    if m:
        return int(m.group(1))
    m = _PRINTING_WORD_RE.search(blob)
    if m:
        if m.group(1):
            return int(m.group(1))
        word = (m.group(2) or "").lower()
        return _WORD_TO_NUM.get(word)
    return None


def parse_printing_profile(
    *,
    title: str = "",
    description: str = "",
    lunar_printing_field: str = "",
) -> PrintingProfile:
    combined = " ".join(part for part in (title, description, lunar_printing_field) if part).strip()
    if _FACSIMILE_RE.search(combined):
        return PrintingProfile(
            printing_number=None,
            printing_kind=PRINTING_KIND_FACSIMILE,
            badge_label=printing_badge_label(printing_kind=PRINTING_KIND_FACSIMILE, printing_number=None),
            is_reprint_line=True,
        )
    if _ANNIVERSARY_REISSUE_RE.search(combined):
        return PrintingProfile(
            printing_number=None,
            printing_kind=PRINTING_KIND_ANNIVERSARY,
            badge_label=printing_badge_label(printing_kind=PRINTING_KIND_ANNIVERSARY, printing_number=None),
            is_reprint_line=True,
        )
    lunar_num: int | None = None
    raw_print = (lunar_printing_field or "").strip()
    if raw_print.isdigit():
        lunar_num = int(raw_print)
    number = parse_printing_number_from_text(combined) or lunar_num
    if number is None or number <= 1:
        return PrintingProfile(
            printing_number=1,
            printing_kind=PRINTING_KIND_FIRST,
            badge_label="",
            is_reprint_line=False,
        )
    kind = PRINTING_KIND_REPRINT
    return PrintingProfile(
        printing_number=number,
        printing_kind=kind,
        badge_label=printing_badge_label(printing_kind=kind, printing_number=number),
        is_reprint_line=True,
    )


def parse_printing_from_lunar_row(row: dict[str, str]) -> PrintingProfile:
    title = row.get("Title") or row.get("ProductName") or row.get("title") or ""
    desc = row.get("Description") or row.get("description") or ""
    printing_field = row.get("Printing") or row.get("printing") or ""
    return parse_printing_profile(title=title, description=desc, lunar_printing_field=printing_field)


def merge_first_print_issue_dates(
    issue: ReleaseIssue,
    *,
    foc_date: date | None,
    release_date: date | None,
) -> None:
    """Apply schedule dates from a first-print source only; never move original earlier dates backward."""
    if foc_date is not None:
        if issue.original_foc_date is None or foc_date <= issue.original_foc_date:
            issue.original_foc_date = foc_date
            issue.foc_date = foc_date
    if release_date is not None:
        if issue.original_release_date is None:
            issue.original_release_date = release_date
            issue.release_date = release_date
        elif release_date < issue.original_release_date:
            issue.original_release_date = release_date
            issue.release_date = release_date


def apply_reprint_issue_guard(issue: ReleaseIssue) -> None:
    """Restore issue-level schedule to preserved originals when reprints overwrote them."""
    if issue.original_release_date is not None:
        issue.release_date = issue.original_release_date
    if issue.original_foc_date is not None:
        issue.foc_date = issue.original_foc_date


def stamp_original_release_from_external(
    issue: ReleaseIssue,
    *,
    release_date: date | None,
    title: str = "",
) -> None:
    profile = parse_printing_profile(title=title)
    if profile.is_reprint_line or release_date is None:
        return
    merge_first_print_issue_dates(issue, foc_date=None, release_date=release_date)


@dataclass(frozen=True)
class PrintingScheduleContext:
    printing_badge: str
    printing_kind: str
    printing_number: int | None
    original_foc_date: date | None
    original_release_date: date | None
    printing_foc_date: date | None
    printing_release_date: date | None


def _variant_sort_key(v: ReleaseVariant) -> tuple[int, date]:
    rel = v.printing_release_date or date.max
    num = v.printing_number or 0
    return (-num, rel)


def issue_import_is_reprint_only(*, variants: list) -> bool:
    if not variants:
        return False
    for v in variants:
        kind = getattr(v, "printing_kind", PRINTING_KIND_FIRST)
        num = getattr(v, "printing_number", None) or 1
        if kind == PRINTING_KIND_FIRST and num <= 1:
            return False
    return True


def resolve_printing_schedule(
    issue: ReleaseIssue | None,
    variants: list[ReleaseVariant],
    *,
    today: date | None = None,
) -> PrintingScheduleContext:
    _ = today
    original_foc = (issue.original_foc_date if issue else None) or (issue.foc_date if issue else None)
    original_rel = (issue.original_release_date if issue else None) or (issue.release_date if issue else None)

    reprint_variants = [
        v
        for v in variants
        if (v.printing_kind or PRINTING_KIND_FIRST) != PRINTING_KIND_FIRST
        or (v.printing_number or 1) > 1
    ]
    badge = ""
    kind = PRINTING_KIND_FIRST
    number: int | None = 1
    print_foc: date | None = None
    print_rel: date | None = None

    if reprint_variants:
        chosen = sorted(reprint_variants, key=_variant_sort_key)[0]
        kind = chosen.printing_kind or PRINTING_KIND_REPRINT
        number = chosen.printing_number
        badge = printing_badge_label(printing_kind=kind, printing_number=number)
        print_foc = chosen.printing_foc_date
        print_rel = chosen.printing_release_date

    return PrintingScheduleContext(
        printing_badge=badge,
        printing_kind=kind,
        printing_number=number,
        original_foc_date=original_foc,
        original_release_date=original_rel,
        printing_foc_date=print_foc,
        printing_release_date=print_rel,
    )
