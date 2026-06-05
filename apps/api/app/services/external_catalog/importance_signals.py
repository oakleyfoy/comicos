from __future__ import annotations

import re
from typing import Any

MILESTONE_ISSUE_NUMBERS = frozenset({25, 50, 75, 100, 150, 200, 250, 300, 400, 500, 600, 750, 1000})

SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "anniversary": re.compile(
        r"\b(\d+(?:th|st|nd|rd)?\s+anniversary|anniversary\s+edition|celebrat(?:e|ing)\s+\d+\s+years?)\b",
        re.I,
    ),
    "first_appearance": re.compile(
        r"\b(first appearance|1st appearance|first app\.?|first cameo|first full appearance)\b",
        re.I,
    ),
    "death_key_event": re.compile(
        r"\b(death of|dies|killed|funeral|fallen|last rites|final fate)\b",
        re.I,
    ),
    "debut_origin": re.compile(
        r"\b(debut|origin of|origin story|new team|new villain|first adventure)\b",
        re.I,
    ),
    "homage": re.compile(r"\b(homage|tribute cover|swipe|retro cover)\b", re.I),
    "relaunch_new_series": re.compile(
        r"\b(relaunch|new series|volume \d+|vol\.?\s*\d+\s*#1|fresh start|series launch)\b",
        re.I,
    ),
    "final_issue": re.compile(
        r"\b(final issue|last issue|end of an era|series finale|the end)\b",
        re.I,
    ),
    "limited_series_oneshot": re.compile(
        r"\b(limited series|mini[- ]series|one[- ]shot|annual|special)\b",
        re.I,
    ),
    "tiein_crossover_event": re.compile(
        r"\b(tie[- ]?in|crossover|event|war of|saga|battleworld|crisis)\b",
        re.I,
    ),
    "media_tie_in": re.compile(
        r"\b(movie|tv|television|streaming|game|video game|mcu|dceu|adaptation)\b",
        re.I,
    ),
    "creator_owned": re.compile(
        r"\b(creator[- ]owned|indie|image comics debut|skybound)\b",
        re.I,
    ),
}


def _blob(*parts: str | None) -> str:
    return " ".join(p for p in parts if p).strip()


def _parse_issue_int(issue_number: str | None) -> int | None:
    if not issue_number:
        return None
    cleaned = issue_number.strip().lstrip("#")
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def is_first_issue_number(issue_number: str | None, *, title: str = "", series_name: str = "") -> bool:
    num = _parse_issue_int(issue_number)
    if num == 1:
        return True
    hay = f"{title} {series_name}".lower()
    return bool(re.search(r"(^|\s)#?\s*1(\s|$|[^0-9])", hay) or re.search(r"\bnumber one\b", hay))


def milestone_number(issue_number: str | None) -> int | None:
    num = _parse_issue_int(issue_number)
    if num is not None and num in MILESTONE_ISSUE_NUMBERS:
        return num
    return None


def detect_importance_signals(
    *,
    title: str,
    series_name: str,
    issue_number: str | None,
    description: str | None,
    story_summary: str | None,
    imprint: str | None = None,
    universe: str | None = None,
) -> dict[str, Any]:
    text = _blob(title, series_name, description, story_summary)
    signals: list[str] = []
    matched: dict[str, str] = {}

    for key, pattern in SIGNAL_PATTERNS.items():
        m = pattern.search(text)
        if m:
            signals.append(key)
            matched[key] = m.group(0)

    first_issue = is_first_issue_number(issue_number, title=title, series_name=series_name)
    milestone = milestone_number(issue_number)

    return {
        "first_issue": first_issue,
        "milestone_issue_number": milestone,
        "is_milestone_issue": milestone is not None,
        "signals": signals,
        "matched_phrases": matched,
        "imprint": (imprint or "").strip() or None,
        "universe": (universe or "").strip() or None,
    }


def parse_ratio_from_text(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"1\s*:\s*(\d+)", value, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{2,4})\s*(?:copy|variant)\b", value, re.I)
    if m:
        return int(m.group(1))
    return None
