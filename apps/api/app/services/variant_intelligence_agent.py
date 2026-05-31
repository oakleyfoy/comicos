from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseVariant
from app.schemas.release_intelligence import ReleaseAgentExecutionRead, ReleaseKeySignalRead
from app.services.release_intelligence import AGENT_VARIANT_INTELLIGENCE, run_with_release_execution


def _signal_exists(session: Session, *, issue_id: int, signal_type: str, payload: dict) -> bool:
    rows = session.exec(
        select(ReleaseKeySignal)
        .where(ReleaseKeySignal.issue_id == issue_id)
        .where(ReleaseKeySignal.signal_type == signal_type)
    ).all()
    encoded = json.dumps(payload, sort_keys=True)
    return any(json.dumps(row.signal_payload_json, sort_keys=True) == encoded for row in rows)


def detect_variant_signals(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[ReleaseKeySignalRead], ReleaseAgentExecutionRead]:
    def runner():
        created: list[ReleaseKeySignal] = []
        issues = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        issue_ids = [int(issue.id or 0) for issue in issues]
        if not issue_ids:
            return []
        variants = session.exec(
            select(ReleaseVariant)
            .where(ReleaseVariant.issue_id.in_(issue_ids))
            .order_by(ReleaseVariant.issue_id.asc(), ReleaseVariant.id.asc())
        ).all()
        for variant in variants:
            variant_type = variant.variant_type.upper()
            base_payload = {
                "variant_id": int(variant.id or 0),
                "variant_name": variant.variant_name,
                "variant_type": variant.variant_type,
                "ratio_value": variant.ratio_value,
            }
            candidates: list[tuple[str, float]] = []
            if variant.ratio_value is not None:
                candidates.append(("VARIANT_RATIO", 0.9))
            if "INCENTIVE" in variant_type or variant.ratio_value is not None:
                candidates.append(("INCENTIVE_VARIANT", 0.86))
            if variant.ratio_value is not None and variant.ratio_value >= 25:
                candidates.append(("HIGH_RATIO_VARIANT", 0.92))
            if "OPEN" in variant_type or "OPEN ORDER" in variant_type:
                candidates.append(("OPEN_ORDER_VARIANT", 0.84))
            for signal_type, confidence in candidates:
                if _signal_exists(session, issue_id=variant.issue_id, signal_type=signal_type, payload=base_payload):
                    continue
                row = ReleaseKeySignal(
                    owner_user_id=owner_user_id,
                    issue_id=variant.issue_id,
                    signal_type=signal_type,
                    confidence_score=confidence,
                    signal_payload_json=base_payload,
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
        agent_code=AGENT_VARIANT_INTELLIGENCE,
        runner=runner,
    )
    return result, ReleaseAgentExecutionRead.model_validate(execution)
