from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal
from app.schemas.release_intelligence import ReleaseAgentExecutionRead, ReleaseKeySignalRead
from app.services.release_intelligence import AGENT_KEY_ISSUE, run_with_release_execution

KEYWORD_SIGNAL_TYPES = {
    "FIRST APPEARANCE": "FIRST_APPEARANCE",
    "ORIGIN": "ORIGIN_ISSUE",
    "ANNIVERSARY": "ANNIVERSARY_ISSUE",
    "DEATH OF": "DEATH_ISSUE",
    "STATUS QUO": "STATUS_QUO_CHANGE",
}

MILESTONE_NUMBERS = {"25", "50", "75", "100", "150", "200", "250", "300", "500", "1000"}


def _signal_exists(session: Session, *, issue_id: int, signal_type: str, payload: dict) -> bool:
    rows = session.exec(
        select(ReleaseKeySignal)
        .where(ReleaseKeySignal.issue_id == issue_id)
        .where(ReleaseKeySignal.signal_type == signal_type)
    ).all()
    encoded = json.dumps(payload, sort_keys=True)
    return any(json.dumps(row.signal_payload_json, sort_keys=True) == encoded for row in rows)


def detect_key_issues(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[ReleaseKeySignalRead], ReleaseAgentExecutionRead]:
    def runner():
        created: list[ReleaseKeySignal] = []
        issues = session.exec(
            select(ReleaseIssue)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
            .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
        ).all()
        for issue in issues:
            title = issue.title.upper()
            candidates: list[tuple[str, dict, float]] = []
            for needle, signal_type in KEYWORD_SIGNAL_TYPES.items():
                if needle in title:
                    candidates.append((signal_type, {"matched_keyword": needle}, 0.88))
            if issue.issue_number.strip().upper().replace("#", "") in MILESTONE_NUMBERS:
                candidates.append(("MILESTONE_NUMBERING", {"issue_number": issue.issue_number}, 0.84))
            for signal_type, payload, confidence in candidates:
                if _signal_exists(session, issue_id=int(issue.id or 0), signal_type=signal_type, payload=payload):
                    continue
                row = ReleaseKeySignal(
                    owner_user_id=owner_user_id,
                    issue_id=int(issue.id or 0),
                    signal_type=signal_type,
                    confidence_score=confidence,
                    signal_payload_json=payload,
                )
                session.add(row)
                created.append(row)
        session.commit()
        for row in created:
            session.refresh(row)
        return [ReleaseKeySignalRead.model_validate(row) for row in created]

    result, execution = run_with_release_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_KEY_ISSUE,
        runner=runner,
    )
    return result, ReleaseAgentExecutionRead.model_validate(execution)
