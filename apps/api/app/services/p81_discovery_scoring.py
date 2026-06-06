"""P81-01 opportunity scoring (non-personalized)."""

from __future__ import annotations

import re
from dataclasses import dataclass

MILESTONE_ISSUES = {100, 200, 300, 500, 1000}
FRANCHISE_KEYWORDS = ("batman", "spider-man", "spiderman", "tmnt", "teenage mutant ninja", "invincible", "superman")
CREATOR_KEYWORDS = (
    "daniel warren johnson",
    "ryan stegman",
    "jonathan hickman",
    "scott snyder",
    "chip zdarsky",
    "james tynion",
)
ANNIVERSARY_RE = re.compile(r"\b(\d{1,3})(?:th|nd|rd|st)\s+anniversary\b", re.I)
VARIANT_RATIO_RE = re.compile(r"\b1\s*:\s*(\d+)\b", re.I)


@dataclass
class P81ScoreInput:
    opportunity_type: str
    title: str
    summary: str
    series_name: str
    issue_number: str
    variant_label: str
    publisher: str
    creators: list[str]


def _normalized_issue_num(issue_number: str) -> str:
    return (issue_number or "").strip().lstrip("#").upper()


def _issue_int(issue_number: str) -> int | None:
    raw = _normalized_issue_num(issue_number)
    if not raw or not raw.replace(".", "", 1).isdigit():
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _text_blob(inp: P81ScoreInput) -> str:
    return " ".join([inp.title, inp.summary, inp.series_name, inp.variant_label]).lower()


def score_discovery_opportunity(inp: P81ScoreInput) -> tuple[float, list[str]]:
    signals: list[str] = []
    score = 25.0

    num = _issue_int(inp.issue_number)
    blob = _text_blob(inp)

    if inp.opportunity_type in {"NEW_1", "NEW_SERIES"} or num == 1:
        score += 22
        signals.append("#1 Issue")
    if inp.opportunity_type == "NEW_SERIES":
        score += 8
        signals.append("New series launch")

    if num is not None and num in MILESTONE_ISSUES:
        score += 28
        signals.append(f"Milestone issue #{num}")
    elif inp.opportunity_type == "MILESTONE":
        score += 20
        signals.append("Milestone issue")

    if ANNIVERSARY_RE.search(blob) or inp.opportunity_type == "ANNIVERSARY":
        score += 16
        signals.append("Anniversary issue")

    for creator in inp.creators:
        c_low = creator.lower()
        if any(k in c_low for k in CREATOR_KEYWORDS):
            score += 14
            signals.append(f"Creator signal: {creator}")
            break
    if inp.opportunity_type == "CREATOR_PROJECT":
        score += 10
        signals.append("Creator project")

    for franchise in FRANCHISE_KEYWORDS:
        if franchise in blob:
            score += 10
            signals.append(f"Franchise signal: {franchise.title()}")
            break

    ratio_match = VARIANT_RATIO_RE.search(inp.variant_label or "")
    if ratio_match:
        ratio = int(ratio_match.group(1))
        if ratio >= 100:
            score += 18
            signals.append("1:100 variant")
        elif ratio >= 50:
            score += 14
            signals.append("1:50 variant")
        elif ratio >= 25:
            score += 10
            signals.append("1:25 variant")
    if inp.opportunity_type == "VARIANT_EXPANSION":
        score += 8
        if "foil" in blob:
            signals.append("Foil variant")
            score += 4
        if "virgin" in blob:
            signals.append("Virgin variant")
            score += 4

    score = min(100.0, round(score, 1))
    return score, signals[:8]


def category_for_score(score: float) -> str:
    if score >= 90:
        return "MUST_WATCH"
    if score >= 75:
        return "HIGH_OPPORTUNITY"
    if score >= 50:
        return "WATCH"
    return "LOW_PRIORITY"
