"""Shared formatting for P97 volume issue queue CLI output."""

from __future__ import annotations

from app.services.p97_volume_issue_queue_priority import LAUNCH_PRIORITY_TIERS

TIER_SECTION_TITLES: dict[str, str] = {
    "tier_0_manual_request": "TIER 0 — MANUAL REQUESTS",
    "tier_1_core": "TIER 1 — CORE US PUBLISHERS",
    "tier_2_legacy": "TIER 2 — LEGACY US PUBLISHERS",
    "tier_3_other_us": "TIER 3 — OTHER US / ENGLISH",
    "tier_4_deprioritized": "TIER 4 — DEPRIORITIZED / FOREIGN",
}


def _fmt(value: int) -> str:
    return f"{value:,}"


def _leader(label: str, value: str, *, width: int = 52) -> str:
    dots = max(1, width - len(label) - len(value))
    return f"{label}{'.' * dots}{value}"


def format_volume_row(row) -> str:
    label = (row.name or f"Volume {row.comicvine_volume_id}")[:22]
    value = f"{_fmt(row.missing_issue_count)} ({row.priority_score:.0f})"
    return _leader(label, value)


def append_top_volumes_by_tier(lines: list[str], grouped: dict[str, list], *, limit: int | None = None) -> None:
    for tier in LAUNCH_PRIORITY_TIERS:
        rows = grouped.get(tier) or []
        if not rows:
            continue
        title = TIER_SECTION_TITLES.get(tier, tier.upper())
        lines.extend(["", title, ""])
        for row in rows[: limit or len(rows)]:
            lines.append(format_volume_row(row))
