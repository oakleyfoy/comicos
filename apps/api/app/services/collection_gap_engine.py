from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.schemas.run_detection import RunDetectionSeriesRead
from app.services.run_detection import parse_issue_number_for_run_detection, run_detection_groups_for_user

COLLECTION_GAP_TYPES = (
    "MISSING_ISSUE",
    "RUN_GAP",
    "KEY_MISSING",
    "MILESTONE_MISSING",
)

MILESTONE_ISSUE_NUMBERS = frozenset({25, 50, 100, 300, 500, 1000})


@dataclass(frozen=True)
class CollectionGapCandidate:
    publisher: str
    series_name: str
    issue_number: str
    gap_type: str
    completion_percent: float
    priority: str
    rationale: str


def run_completion_for_numeric_owned(owned: list[int]) -> tuple[float, list[int]]:
    if not owned:
        return 0.0, []
    unique = sorted(set(owned))
    lo, hi = unique[0], unique[-1]
    span = hi - lo + 1
    owned_set = set(unique)
    missing = [n for n in range(lo, hi + 1) if n not in owned_set]
    pct = round(100.0 * len(unique) / span, 1) if span else 0.0
    return pct, missing


def _owned_integer_issues(group: RunDetectionSeriesRead) -> list[int]:
    ints: list[int] = []
    for label in group.owned_issue_numbers:
        parsed = parse_issue_number_for_run_detection(label)
        if parsed.kind not in {"integer", "decimal"} or parsed.numeric_value is None:
            continue
        value = parsed.numeric_value
        if value != value.to_integral_value():
            continue
        ints.append(int(value))
    return ints


def _gap_type_for_issue(*, issue_number: str, is_identity_gap: bool) -> str:
    if is_identity_gap:
        return "RUN_GAP"
    parsed = parse_issue_number_for_run_detection(issue_number)
    if parsed.numeric_value is not None and parsed.numeric_value == parsed.numeric_value.to_integral_value():
        num = int(parsed.numeric_value)
        if num == 1:
            return "KEY_MISSING"
        if num in MILESTONE_ISSUE_NUMBERS:
            return "MILESTONE_MISSING"
    return "MISSING_ISSUE"


def _assign_priority(
    *,
    gap_type: str,
    completion_percent: float,
    series_status: str,
    span_size: int,
) -> str:
    if gap_type in {"KEY_MISSING", "MILESTONE_MISSING"}:
        return "CRITICAL"
    if completion_percent >= 80.0 and span_size >= 3:
        return "CRITICAL"
    if series_status in {"partial_run", "incomplete_limited_series"}:
        return "HIGH"
    if completion_percent >= 40.0 or span_size >= 3:
        return "MEDIUM"
    return "LOW"


def _rationale_for_gap(
    *,
    gap_type: str,
    series_name: str,
    issue_number: str,
    completion_percent: float,
) -> str:
    if gap_type == "RUN_GAP":
        return f"Run identity gap detected for {series_name}; completion math may be incomplete."
    if gap_type == "MILESTONE_MISSING":
        return f"Milestone issue missing ({series_name} #{issue_number}). Run completion currently {completion_percent:.0f}%."
    if gap_type == "KEY_MISSING":
        return f"Key issue missing ({series_name} #{issue_number}). Run completion currently {completion_percent:.0f}%."
    if issue_number:
        return f"Run is missing issue #{issue_number}. Run completion currently {completion_percent:.0f}%."
    return f"Acquisition gap in {series_name}. Run completion currently {completion_percent:.0f}%."


def _candidate_key(c: CollectionGapCandidate) -> tuple[str, str, str]:
    return (
        c.publisher.strip().lower(),
        c.series_name.strip().lower(),
        c.issue_number.strip().lower(),
    )


def generate_collection_gaps(session: Session, *, owner_user_id: int) -> list[CollectionGapCandidate]:
    """Read-only gap analysis from inventory and run-detection (portfolio run intelligence)."""
    groups = run_detection_groups_for_user(session, owner_user_id=owner_user_id)
    candidates: dict[tuple[str, str, str], CollectionGapCandidate] = {}

    for group in groups:
        owned_ints = _owned_integer_issues(group)
        completion_pct, span_missing = run_completion_for_numeric_owned(owned_ints)
        span_size = (max(owned_ints) - min(owned_ints) + 1) if owned_ints else 0

        for missing_num in span_missing:
            issue_label = str(missing_num)
            gap_type = _gap_type_for_issue(issue_number=issue_label, is_identity_gap=False)
            priority = _assign_priority(
                gap_type=gap_type,
                completion_percent=completion_pct,
                series_status=group.series_status,
                span_size=span_size,
            )
            candidate = CollectionGapCandidate(
                publisher=group.publisher,
                series_name=group.title,
                issue_number=issue_label,
                gap_type=gap_type,
                completion_percent=completion_pct,
                priority=priority,
                rationale=_rationale_for_gap(
                    gap_type=gap_type,
                    series_name=group.title,
                    issue_number=issue_label,
                    completion_percent=completion_pct,
                ),
            )
            candidates[_candidate_key(candidate)] = candidate

        for missing in group.missing_issues:
            if missing.classification == "unresolved_identity_gap":
                candidate = CollectionGapCandidate(
                    publisher=group.publisher,
                    series_name=group.title,
                    issue_number="",
                    gap_type="RUN_GAP",
                    completion_percent=completion_pct,
                    priority=_assign_priority(
                        gap_type="RUN_GAP",
                        completion_percent=completion_pct,
                        series_status=group.series_status,
                        span_size=span_size,
                    ),
                    rationale=_rationale_for_gap(
                        gap_type="RUN_GAP",
                        series_name=group.title,
                        issue_number="",
                        completion_percent=completion_pct,
                    ),
                )
                key = _candidate_key(candidate)
                if key not in candidates:
                    candidates[key] = candidate
                continue
            if missing.classification not in {"confirmed_missing", "likely_missing"}:
                continue
            if not missing.issue_number:
                continue
            parsed = parse_issue_number_for_run_detection(missing.issue_number)
            if parsed.numeric_value is not None and parsed.numeric_value == parsed.numeric_value.to_integral_value():
                issue_label = str(int(parsed.numeric_value))
            else:
                issue_label = missing.issue_number
            gap_type = _gap_type_for_issue(issue_number=issue_label, is_identity_gap=False)
            priority = _assign_priority(
                gap_type=gap_type,
                completion_percent=completion_pct,
                series_status=group.series_status,
                span_size=span_size,
            )
            candidate = CollectionGapCandidate(
                publisher=group.publisher,
                series_name=group.title,
                issue_number=issue_label,
                gap_type=gap_type,
                completion_percent=completion_pct,
                priority=priority,
                rationale=_rationale_for_gap(
                    gap_type=gap_type,
                    series_name=group.title,
                    issue_number=issue_label,
                    completion_percent=completion_pct,
                ),
            )
            candidates[_candidate_key(candidate)] = candidate

    ordered = sorted(
        candidates.values(),
        key=lambda c: (
            -{"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(c.priority, 0),
            c.publisher.lower(),
            c.series_name.lower(),
            parse_issue_number_for_run_detection(c.issue_number).sortable_key,
        ),
    )
    return ordered
