from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.schemas.release_intelligence import ReleaseAgentExecutionRead, ReleaseKeySignalRead
from app.services.release_intelligence import AGENT_NEW_NUMBER_ONE, run_with_release_execution


def _normalized_issue_number(value: str) -> str:
    return value.strip().upper().replace("#", "")


def _signal_exists(session: Session, *, issue_id: int, signal_type: str, payload: dict) -> bool:
    rows = session.exec(
        select(ReleaseKeySignal)
        .where(ReleaseKeySignal.issue_id == issue_id)
        .where(ReleaseKeySignal.signal_type == signal_type)
    ).all()
    encoded = json.dumps(payload, sort_keys=True)
    return any(json.dumps(row.signal_payload_json, sort_keys=True) == encoded for row in rows)


def detect_new_number_ones(
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
            if _normalized_issue_number(issue.issue_number) != "1":
                continue
            series = session.get(ReleaseSeries, issue.series_id)
            release_kind = "ONGOING_1"
            if series is not None and series.series_type.upper() in {"MINI", "MINISERIES", "LIMITED"}:
                release_kind = "MINI_SERIES_1"
            elif "RELAUNCH" in issue.title.upper() or (series is not None and series.status.upper() == "RELAUNCH"):
                release_kind = "RELAUNCH_1"
            payload = {"classification": release_kind, "issue_number": issue.issue_number}
            if _signal_exists(session, issue_id=int(issue.id or 0), signal_type="NEW_NUMBER_ONE", payload=payload):
                continue
            row = ReleaseKeySignal(
                owner_user_id=owner_user_id,
                issue_id=int(issue.id or 0),
                signal_type="NEW_NUMBER_ONE",
                confidence_score=0.95,
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
        agent_code=AGENT_NEW_NUMBER_ONE,
        runner=runner,
    )
    return result, ReleaseAgentExecutionRead.model_validate(execution)
