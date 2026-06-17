"""Flag suspicious P97 queue priority ordering (report only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.services.p97_queue_priority_config import is_core_run
from app.services.p97_volume_issue_import_queue_service import STATUS_PENDING, get_top_queued_volumes

RECOMMENDED_NOTE = (
    "Reduce pure publisher multiplier dominance so small runs do not outrank large missing gaps."
)


@dataclass
class QueuePrioritySanityRow:
    comicvine_volume_id: int
    name: str
    publisher: str | None
    missing_issue_count: int
    priority_score: float
    is_core: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "name": self.name,
            "publisher": self.publisher,
            "missing_issue_count": self.missing_issue_count,
            "priority_score": self.priority_score,
            "is_core": self.is_core,
            "reason": self.reason,
        }


def build_queue_priority_sanity_report(session: Session, *, top: int = 50) -> list[QueuePrioritySanityRow]:
    pending = get_top_queued_volumes(session, limit=top, statuses=(STATUS_PENDING,))
    if not pending:
        return []
    max_missing = max(int(r.missing_issue_count or 0) for r in pending)
    large_threshold = max(100, max_missing // 2)
    suspicious: list[QueuePrioritySanityRow] = []
    for row in pending:
        missing = int(row.missing_issue_count or 0)
        score = float(row.priority_score or 0)
        core = is_core_run(row.name, None)
        reasons: list[str] = []
        if missing <= 3 and not core:
            reasons.append("missing_issue_count<=3 and not core")
        if missing <= 3 and score >= 500_000:
            reasons.append("tiny run with very high priority_score")
        if missing < large_threshold:
            for other in pending:
                om = int(other.missing_issue_count or 0)
                if om >= large_threshold and score > float(other.priority_score or 0):
                    reasons.append(
                        f"outranks {other.name!r} (missing={om}) despite smaller gap"
                    )
                    break
        if reasons:
            suspicious.append(
                QueuePrioritySanityRow(
                    comicvine_volume_id=int(row.comicvine_volume_id),
                    name=row.name,
                    publisher=row.publisher,
                    missing_issue_count=missing,
                    priority_score=score,
                    is_core=core,
                    reason="; ".join(reasons),
                )
            )
    return suspicious
