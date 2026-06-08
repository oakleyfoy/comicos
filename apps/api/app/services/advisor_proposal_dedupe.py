"""Stable dedupe keys for Collector Advisor proposals and actions (P90-05)."""

from __future__ import annotations

from typing import Any

from app.services.advisor_evidence import dedupe_evidence_segments, dedupe_evidence_string, split_evidence_segments
from app.services.automation_engine_service import _Proposal
from app.services.collector_alert_priority_service import PriorityInputs, compute_priority_score

_TITLE_PREFIXES = (
    "Strong Buy: ",
    "Good Buy: ",
    "Spec Buy: ",
    "Undervalued: ",
    "Buy opportunity: ",
    "Buy: ",
    "Watch: ",
    "Sell now: ",
    "Monitor sell: ",
    "Grade first: ",
    "Collection gap: ",
    "Stale listing: ",
    "Upcoming: ",
    "Portfolio action: ",
    "Review stale listing: ",
    "Review expired listing: ",
)


def normalized_comic_from_title(title: str) -> str:
    return comic_label_from_title(title).lower()


def comic_label_from_title(title: str) -> str:
    text = (title or "").strip()
    for prefix in _TITLE_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def proposal_action_category(proposal: _Proposal) -> str:
    atype = (proposal.alert_type or "").upper()
    if atype in {"BUY_OPPORTUNITY", "PRICE_DROP"}:
        return "BUY"
    if atype == "SELL_OPPORTUNITY":
        return "SELL"
    if atype == "GRADE_OPPORTUNITY":
        return "GRADE"
    if atype in {"WATCHLIST_MATCH", "COLLECTION_GAP", "RELEASE_ALERT", "PORTFOLIO_ACTION"}:
        return "WATCH"
    return ""


def action_dict_category(item: dict[str, Any]) -> str:
    explicit = str(item.get("category") or "").upper()
    if explicit in {"BUY", "SELL", "GRADE", "WATCH"}:
        return explicit
    atype = str(item.get("alert_type") or "").upper()
    if atype in {"BUY_OPPORTUNITY", "PRICE_DROP"}:
        return "BUY"
    if atype == "SELL_OPPORTUNITY":
        return "SELL"
    if atype == "GRADE_OPPORTUNITY":
        return "GRADE"
    if atype in {"WATCHLIST_MATCH", "COLLECTION_GAP", "RELEASE_ALERT", "PORTFOLIO_ACTION"}:
        return "WATCH"
    return explicit or "WATCH"


def proposal_priority_score(proposal: _Proposal) -> float:
    return compute_priority_score(
        PriorityInputs(
            alert_type=str(proposal.alert_type or ""),
            severity=str(proposal.severity or "MEDIUM"),
            confidence=str(proposal.confidence or "MEDIUM"),
            profit_signal=float(proposal.profit_signal or 0.0),
            urgency_signal=float(proposal.urgency_signal or 0.0),
            marketplace_activity=float(proposal.marketplace_activity or 0.0),
            release_days=proposal.release_days,
        )
    )


def action_dict_priority_score(item: dict[str, Any]) -> float:
    if item.get("priority_score") is not None:
        return float(item["priority_score"])
    category = action_dict_category(item)
    alert_type = str(item.get("alert_type") or _category_to_alert_type(category))
    return compute_priority_score(
        PriorityInputs(
            alert_type=alert_type,
            severity=str(item.get("severity") or "MEDIUM"),
            confidence=str(item.get("confidence") or "MEDIUM"),
            profit_signal=float(item.get("profit_signal") or 0.0),
            urgency_signal=float(item.get("urgency_signal") or 0.0),
            marketplace_activity=float(item.get("marketplace_activity") or 0.0),
            release_days=item.get("release_days"),
        )
    )


def _category_to_alert_type(category: str) -> str:
    mapping = {
        "BUY": "BUY_OPPORTUNITY",
        "SELL": "SELL_OPPORTUNITY",
        "GRADE": "GRADE_OPPORTUNITY",
        "WATCH": "COLLECTION_GAP",
    }
    return mapping.get(category.upper(), "PORTFOLIO_ACTION")


def proposal_entity_key(proposal: _Proposal) -> tuple[str, str, str, int]:
    category = proposal_action_category(proposal)
    return (
        category,
        str(proposal.entity_type or ""),
        str(proposal.entity_id or 0),
        int(proposal.entity_id or 0),
    )


def proposal_comic_key(proposal: _Proposal) -> tuple[str, str] | None:
    category = proposal_action_category(proposal)
    if not category:
        return None
    comic = normalized_comic_from_title(proposal.title)
    if len(comic) < 3:
        return None
    return category, comic


def action_entity_key(item: dict[str, Any]) -> tuple[str, str, str, int]:
    category = action_dict_category(item)
    entity_type = str(item.get("entity_type") or "")
    entity_id = int(item.get("entity_id") or 0)
    return category, entity_type, str(entity_id), entity_id


def action_comic_key(item: dict[str, Any]) -> tuple[str, str] | None:
    category = action_dict_category(item)
    if not category:
        return None
    comic = str(item.get("comic") or "").strip().lower()
    if not comic:
        comic = normalized_comic_from_title(str(item.get("title") or ""))
    if len(comic) < 3:
        return None
    return category, comic


def _source_evidence_label(source_system: str) -> str:
    key = (source_system or "").upper()
    if "MONITOR" in key:
        return "marketplace alert"
    if "MARKETPLACE" in key or key == "P88":
        return "verified listing"
    if "P90" in key or "AUTOMATION" in key:
        return "automation alert"
    if "SELL" in key:
        return "sell intelligence"
    return ""


def _merge_text_parts(*parts: str) -> str:
    combined: list[str] = []
    for part in parts:
        combined.extend(split_evidence_segments(part))
    return " · ".join(dedupe_evidence_segments(combined))


def _merge_proposals(primary: _Proposal, secondary: _Proposal) -> _Proposal:
    evidence = _merge_text_parts(
        primary.reason,
        secondary.reason,
        _source_evidence_label(primary.source_system),
        _source_evidence_label(secondary.source_system),
    )
    summary = _merge_text_parts(primary.summary, secondary.summary, evidence)
    return _Proposal(
        alert_type=primary.alert_type,
        severity=primary.severity,
        title=primary.title,
        summary=summary or primary.summary,
        source_system=primary.source_system,
        entity_type=primary.entity_type,
        entity_id=int(primary.entity_id or 0),
        confidence=primary.confidence,
        reason=evidence or primary.reason,
        action_route=primary.action_route,
        profit_signal=max(float(primary.profit_signal or 0), float(secondary.profit_signal or 0)),
        urgency_signal=max(float(primary.urgency_signal or 0), float(secondary.urgency_signal or 0)),
        marketplace_activity=max(
            float(primary.marketplace_activity or 0),
            float(secondary.marketplace_activity or 0),
        ),
        release_days=primary.release_days if primary.release_days is not None else secondary.release_days,
    )


def _proposals_duplicate(a: _Proposal, b: _Proposal) -> bool:
    ca, cb = proposal_action_category(a), proposal_action_category(b)
    if not ca or ca != cb:
        return False
    if (
        ca == cb
        and (a.entity_type or "") == (b.entity_type or "")
        and int(a.entity_id or 0) > 0
        and int(a.entity_id or 0) == int(b.entity_id or 0)
    ):
        return True
    ck_a, ck_b = proposal_comic_key(a), proposal_comic_key(b)
    return ck_a is not None and ck_a == ck_b


def dedupe_proposals(proposals: list[_Proposal]) -> list[_Proposal]:
    ranked = sorted(proposals, key=proposal_priority_score, reverse=True)
    out: list[_Proposal] = []
    for proposal in ranked:
        merged = False
        for idx, existing in enumerate(out):
            if _proposals_duplicate(existing, proposal):
                out[idx] = _merge_proposals(existing, proposal)
                merged = True
                break
        if not merged:
            out.append(proposal)
    return out


def _merge_action_dicts(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    merged["reason"] = dedupe_evidence_string(
        _merge_text_parts(
            str(primary.get("reason") or ""),
            str(secondary.get("reason") or ""),
            _source_evidence_label(str(primary.get("source_system") or "")),
            _source_evidence_label(str(secondary.get("source_system") or "")),
        )
    )
    merged["summary"] = _merge_text_parts(
        str(primary.get("summary") or ""),
        str(secondary.get("summary") or ""),
        merged["reason"],
    )
    merged["profit_signal"] = max(
        float(primary.get("profit_signal") or 0),
        float(secondary.get("profit_signal") or 0),
    )
    merged["urgency_signal"] = max(
        float(primary.get("urgency_signal") or 0),
        float(secondary.get("urgency_signal") or 0),
    )
    merged["marketplace_activity"] = max(
        float(primary.get("marketplace_activity") or 0),
        float(secondary.get("marketplace_activity") or 0),
    )
    for field in ("potential_upside", "profit_potential", "value_increase"):
        a = primary.get(field)
        b = secondary.get(field)
        if a is not None or b is not None:
            merged[field] = max(float(a or 0), float(b or 0))
    return merged


def _actions_duplicate(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ca, cb = action_dict_category(a), action_dict_category(b)
    if ca != cb or not ca:
        return False
    ea, eb = action_entity_key(a), action_entity_key(b)
    if ea[3] > 0 and ea[3] == eb[3] and ea[1] == eb[1]:
        return True
    ck_a, ck_b = action_comic_key(a), action_comic_key(b)
    return ck_a is not None and ck_a == ck_b


def dedupe_advisor_action_dicts(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(actions, key=action_dict_priority_score, reverse=True)
    out: list[dict[str, Any]] = []
    for action in ranked:
        merged = False
        for idx, existing in enumerate(out):
            if _actions_duplicate(existing, action):
                out[idx] = _merge_action_dicts(existing, action)
                merged = True
                break
        if not merged:
            out.append(action)
    return out


def action_dict_dedupe_key(item: dict) -> tuple[str, str, str]:
    category = action_dict_category(item)
    entity_type = str(item.get("entity_type") or "")
    entity_id = int(item.get("entity_id") or 0)
    if entity_id > 0 and entity_type:
        return category, entity_type, str(entity_id)
    comic_key = action_comic_key(item)
    if comic_key:
        return comic_key[0], "comic", comic_key[1]
    return category, str(item.get("source_system") or ""), normalized_comic_from_title(str(item.get("title") or ""))[:120]


def count_unique_advisor_actions(*groups: list[dict]) -> int:
    keys: set[tuple[str, str, str]] = set()
    for group in groups:
        for item in group:
            if not item:
                continue
            keys.add(action_dict_dedupe_key(item))
    return len(keys)


# Legacy helpers (tests / diagnostics)
def proposal_dedupe_key(proposal: _Proposal) -> tuple[str, str, str, int]:
    category = proposal_action_category(proposal)
    return (
        category,
        proposal.entity_type or "",
        str(int(proposal.entity_id or 0)),
        int(proposal.entity_id or 0),
    )


def proposal_dedupe_key_fallback(proposal: _Proposal) -> tuple[str, str, str]:
    category = proposal_action_category(proposal)
    return (
        category,
        normalized_comic_from_title(proposal.title),
        proposal.entity_type or "",
    )
