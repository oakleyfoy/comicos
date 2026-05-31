from __future__ import annotations

import json


def encode_scoped_notes(*, owner_user_id: int, summary: str, **extra: object) -> str:
    payload: dict[str, object] = {"owner_user_id": owner_user_id, "summary": summary, **extra}
    return json.dumps(payload, sort_keys=True)


def decode_scoped_notes(raw: str) -> dict[str, object]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"summary": raw}
    return parsed if isinstance(parsed, dict) else {"summary": str(parsed)}


def notes_owner_user_id(raw: str) -> int | None:
    owner = decode_scoped_notes(raw).get("owner_user_id")
    if owner is None:
        return None
    try:
        return int(owner)
    except (TypeError, ValueError):
        return None


def notes_summary(raw: str) -> str:
    decoded = decode_scoped_notes(raw)
    summary = decoded.get("summary")
    return str(summary) if summary is not None else raw
