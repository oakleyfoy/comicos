"""Stable dedupe keys for Collector Advisor proposals and actions."""

from __future__ import annotations

from app.services.automation_engine_service import _Proposal


def proposal_dedupe_key(proposal: _Proposal) -> tuple[str, str, str, int]:
    return (
        proposal.alert_type,
        proposal.source_system or "",
        proposal.entity_type or "",
        int(proposal.entity_id or 0),
    )


def proposal_dedupe_key_fallback(proposal: _Proposal) -> tuple[str, str, str]:
    return (
        proposal.alert_type,
        (proposal.title or "").strip().lower()[:120],
        proposal.source_system or "",
    )


def dedupe_proposals(proposals: list[_Proposal]) -> list[_Proposal]:
    seen: set[tuple[str, str, str, int]] = set()
    seen_fallback: set[tuple[str, str, str]] = set()
    out: list[_Proposal] = []
    for proposal in proposals:
        key = proposal_dedupe_key(proposal)
        if key in seen:
            continue
        fb = proposal_dedupe_key_fallback(proposal)
        if fb in seen_fallback:
            continue
        seen.add(key)
        seen_fallback.add(fb)
        out.append(proposal)
    return out


def action_dict_dedupe_key(item: dict) -> tuple[str, str, str, int]:
    alert_type = str(item.get("alert_type") or item.get("category") or "").upper()
    entity_id = int(item.get("entity_id") or item.get("rank") or 0)
    return (
        alert_type,
        str(item.get("source_system") or ""),
        str(item.get("entity_type") or item.get("title") or "")[:80],
        entity_id,
    )


def count_unique_advisor_actions(*groups: list[dict]) -> int:
    keys: set[tuple[str, str, str, int]] = set()
    for group in groups:
        for item in group:
            if not item:
                continue
            keys.add(action_dict_dedupe_key(item))
    return len(keys)
