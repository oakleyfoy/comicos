from __future__ import annotations

from sqlmodel import Session, select

from app.models.collection_gap import CollectionGap
from app.schemas.collection_gap import CollectionGapWantListSuggestionRead
from app.services.collection_gap_engine import CollectionGapCandidate, generate_collection_gaps
from app.services.collection_gaps import latest_collection_gap_rows


def recommend_want_list_additions(
    session: Session,
    *,
    owner_user_id: int,
) -> list[CollectionGapWantListSuggestionRead]:
    """Suggest want-list additions from latest gaps — read-only, no want-list writes."""
    latest = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    if not latest:
        candidates = generate_collection_gaps(session, owner_user_id=owner_user_id)
        return [_candidate_to_suggestion(c) for c in candidates if c.issue_number]

    suggestions: list[CollectionGapWantListSuggestionRead] = []
    for row in sorted(
        latest.values(),
        key=lambda r: (-{"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(r.priority, 0), r.id or 0),
    ):
        if not row.issue_number:
            continue
        suggestions.append(
            CollectionGapWantListSuggestionRead(
                publisher=row.publisher,
                series_name=row.series_name,
                issue_number=row.issue_number,
                priority=row.priority,  # type: ignore[arg-type]
                gap_type=row.gap_type,  # type: ignore[arg-type]
                rationale=row.rationale,
            )
        )
    return suggestions


def _candidate_to_suggestion(c: CollectionGapCandidate) -> CollectionGapWantListSuggestionRead:
    return CollectionGapWantListSuggestionRead(
        publisher=c.publisher,
        series_name=c.series_name,
        issue_number=c.issue_number,
        priority=c.priority,  # type: ignore[arg-type]
        gap_type=c.gap_type,  # type: ignore[arg-type]
        rationale=c.rationale,
    )
