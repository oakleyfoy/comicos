from __future__ import annotations

from typing import Any


def expand_characters_from_raw(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    existing = raw.get("characters")
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, dict):
                continue
            name = (item.get("character_name") or item.get("name") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "character_name": name,
                    "alias": (item.get("alias") or "").strip() or None,
                    "role": (item.get("role") or item.get("character_role") or "").strip() or None,
                    "universe": (item.get("universe") or "").strip() or None,
                    "source_url": item.get("source_url"),
                }
            )
    return rows
