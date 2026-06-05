from __future__ import annotations

from typing import Any


def bucket_role(role_display: str) -> str:
    """Map LoCG role label to a stable bucket; preserve exact text in role_display."""
    cleaned = (role_display or "").strip()
    if not cleaned:
        return "OTHER"
    lower = cleaned.lower()
    if "writer" in lower or lower in {"w", "script"}:
        return "WRITER"
    if "cover" in lower and "artist" in lower:
        return "COVER_ARTIST"
    if lower == "artist" or ("interior" in lower and "artist" in lower):
        return "ARTIST"
    if "color" in lower:
        return "COLORIST"
    if "letter" in lower:
        return "LETTERER"
    if "edit" in lower:
        return "EDITOR"
    if "inker" in lower or "ink" in lower:
        return "INKER"
    return cleaned.upper().replace(" ", "_")[:64]


def expand_creators_from_raw(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    existing = raw.get("creators")
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, dict):
                continue
            name = (item.get("creator_name") or item.get("name") or "").strip()
            if not name:
                continue
            role_display = (item.get("role_display") or item.get("role") or "").strip()
            rows.append(
                {
                    "creator_name": name,
                    "role": bucket_role(role_display),
                    "role_display": role_display or None,
                    "source_url": item.get("source_url"),
                }
            )
    credits = raw.get("creator_credits")
    if isinstance(credits, dict):
        for role_label, names in credits.items():
            if not isinstance(names, list):
                continue
            role_display = str(role_label).strip()
            for name in names:
                cleaned = str(name).strip()
                if not cleaned:
                    continue
                rows.append(
                    {
                        "creator_name": cleaned,
                        "role": bucket_role(role_display),
                        "role_display": role_display,
                        "source_url": None,
                    }
                )
    return rows
