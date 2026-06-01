from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.future_release_action import FutureReleaseAction
from app.models.future_release_match import FutureReleaseMatch
from app.models.industry_opportunity import IndustryOpportunityScore
from app.models.industry_release_signal import IndustryReleaseSignal
from app.models.key_issue_intelligence import KeyIssueProfile, KeyIssueSignal
from app.models.pull_list import PullListDecision
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.spec_input import (
    SPEC_INPUT_SOURCE_SYSTEMS,
    SpecInput,
)
from app.models.spec_intelligence import SpecScore
from app.services.future_release_matches import latest_future_release_match_rows
from app.services.industry_release_scans import latest_scan_run_id
from app.services.purchase_profiles import get_purchase_preferences, get_purchase_profile

SOURCE_RELEASE_INTELLIGENCE = "RELEASE_INTELLIGENCE"
SOURCE_FUTURE_RELEASE_INTELLIGENCE = "FUTURE_RELEASE_INTELLIGENCE"
SOURCE_INDUSTRY_SCANNER = "INDUSTRY_SCANNER"
SOURCE_PURCHASE_PROFILE = "PURCHASE_PROFILE"
SOURCE_PULL_LIST = "PULL_LIST"

SUMMARY_VERSION = "P60-01"


@dataclass
class SpecInputBuildResult:
    created: int = 0
    skipped: int = 0
    updated: int = 0


def _canonical_summary(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _parse_source_systems(value: str) -> list[str]:
    if not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _format_source_systems(systems: set[str]) -> str:
    allowed = {s for s in systems if s in SPEC_INPUT_SOURCE_SYSTEMS}
    return ",".join(sorted(allowed))


def _nullable_eq(column_value: int | None, target: int | None) -> bool:
    if column_value is None and target is None:
        return True
    return column_value == target


def _find_existing_row(
    session: Session,
    *,
    owner_user_id: int,
    release_id: int | None,
    industry_candidate_id: int | None,
    future_release_match_id: int | None,
) -> SpecInput | None:
    rows = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
    for row in rows:
        if (
            _nullable_eq(row.release_id, release_id)
            and _nullable_eq(row.industry_candidate_id, industry_candidate_id)
            and _nullable_eq(row.future_release_match_id, future_release_match_id)
        ):
            return row
    return None


def _latest_spec_score(session: Session, *, release_id: int) -> SpecScore | None:
    return session.exec(
        select(SpecScore)
        .where(SpecScore.release_issue_id == release_id)
        .order_by(SpecScore.created_at.desc(), SpecScore.id.desc())
    ).first()


def _purchase_context(session: Session, *, owner_user_id: int) -> dict:
    profile = get_purchase_profile(session, owner_user_id=owner_user_id)
    prefs = get_purchase_preferences(session, owner_user_id=owner_user_id)
    return {
        "profile_type": profile.profile_type,
        "display_name": profile.display_name,
        "preferred_copy_count": prefs.preferred_copy_count,
        "risk_tolerance": float(prefs.risk_tolerance),
        "variant_interest": float(prefs.variant_interest),
        "grading_interest": float(prefs.grading_interest),
        "completionist_score": float(prefs.completionist_score),
        "speculation_score": float(prefs.speculation_score),
    }


def _collect_release_ids(session: Session, *, owner_user_id: int) -> set[int]:
    release_ids: set[int] = set()

    for issue in session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all():
        if issue.id is not None:
            release_ids.add(int(issue.id))

    for row in latest_future_release_match_rows(session, owner_user_id=owner_user_id).values():
        release_ids.add(int(row.release_id))

    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is not None:
        for row in session.exec(
            select(IndustryOpportunityScore)
            .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
            .where(IndustryOpportunityScore.scan_run_id == run_id)
        ).all():
            release_ids.add(int(row.release_id))

    for row in session.exec(select(PullListDecision).where(PullListDecision.owner_user_id == owner_user_id)).all():
        release_ids.add(int(row.release_id))

    for row in session.exec(
        select(FutureReleaseAction)
        .where(FutureReleaseAction.owner_user_id == owner_user_id)
        .where(FutureReleaseAction.release_id.is_not(None))
    ).all():
        if row.release_id is not None:
            release_ids.add(int(row.release_id))

    return release_ids


def _build_row_payload(
    session: Session,
    *,
    owner_user_id: int,
    release_id: int,
    purchase_context: dict,
    future_matches: dict[tuple[str, str], FutureReleaseMatch],
    industry_by_release: dict[int, IndustryOpportunityScore],
    signals_by_release: dict[int, list[IndustryReleaseSignal]],
    pull_decisions: dict[int, PullListDecision],
    future_actions: dict[int, FutureReleaseAction],
) -> tuple[set[str], dict, SpecInput]:
    issue = session.get(ReleaseIssue, release_id)
    if issue is None:
        raise ValueError(f"Release issue {release_id} not found")

    series = session.get(ReleaseSeries, int(issue.series_id))
    publisher = series.publisher if series else ""
    series_name = series.series_name if series else ""

    systems: set[str] = {SOURCE_PURCHASE_PROFILE}
    normalized: list[dict] = []

    key_profiles = session.exec(
        select(KeyIssueProfile).where(KeyIssueProfile.release_issue_id == release_id)
    ).all()
    key_signals = session.exec(select(KeyIssueSignal).where(KeyIssueSignal.release_issue_id == release_id)).all()
    if key_profiles or key_signals or issue.title:
        systems.add(SOURCE_RELEASE_INTELLIGENCE)
        for profile in key_profiles:
            normalized.append(
                {
                    "system": SOURCE_RELEASE_INTELLIGENCE,
                    "kind": "key_issue_profile",
                    "key_issue_type": profile.key_issue_type,
                    "importance_score": float(profile.importance_score),
                    "confidence_score": float(profile.confidence_score),
                }
            )
        for signal in key_signals:
            normalized.append(
                {
                    "system": SOURCE_RELEASE_INTELLIGENCE,
                    "kind": "key_issue_signal",
                    "signal_type": signal.signal_type,
                    "signal_strength": float(signal.signal_strength),
                }
            )
        normalized.append(
            {
                "system": SOURCE_RELEASE_INTELLIGENCE,
                "kind": "release_issue",
                "release_status": issue.release_status,
                "cover_price": float(issue.cover_price),
            }
        )
        spec_score = _latest_spec_score(session, release_id=release_id)
        if spec_score is not None:
            normalized.append(
                {
                    "system": SOURCE_RELEASE_INTELLIGENCE,
                    "kind": "spec_score",
                    "score_value": float(spec_score.score_value),
                    "score_grade": spec_score.score_grade,
                    "confidence_score": float(spec_score.confidence_score),
                }
            )

    match: FutureReleaseMatch | None = None
    match_key = (series_name, issue.issue_number)
    if match_key in future_matches:
        match = future_matches[match_key]
    else:
        for candidate in future_matches.values():
            if int(candidate.release_id) == release_id:
                match = candidate
                break

    future_release_match_id: int | None = None
    if match is not None:
        systems.add(SOURCE_FUTURE_RELEASE_INTELLIGENCE)
        future_release_match_id = int(match.id or 0)
        normalized.append(
            {
                "system": SOURCE_FUTURE_RELEASE_INTELLIGENCE,
                "kind": "future_release_match",
                "confidence": float(match.confidence),
                "variant_count": int(match.variant_count),
            }
        )

    action = future_actions.get(release_id)
    if action is not None:
        systems.add(SOURCE_FUTURE_RELEASE_INTELLIGENCE)
        normalized.append(
            {
                "system": SOURCE_FUTURE_RELEASE_INTELLIGENCE,
                "kind": "future_release_action",
                "action_type": action.action_type,
                "priority_score": float(action.priority_score),
            }
        )

    industry_candidate_id: int | None = None
    opportunity = industry_by_release.get(release_id)
    industry_signals = signals_by_release.get(release_id, [])
    if opportunity is not None or industry_signals:
        systems.add(SOURCE_INDUSTRY_SCANNER)
    if opportunity is not None:
        industry_candidate_id = int(opportunity.candidate_id)
        normalized.append(
            {
                "system": SOURCE_INDUSTRY_SCANNER,
                "kind": "opportunity_score",
                "opportunity_score": float(opportunity.opportunity_score),
                "confidence_score": float(opportunity.confidence_score),
                "risk_level": opportunity.risk_level,
            }
        )
    for signal in industry_signals:
        normalized.append(
            {
                "system": SOURCE_INDUSTRY_SCANNER,
                "kind": "industry_signal",
                "signal_type": signal.signal_type,
                "confidence_score": float(signal.confidence_score),
            }
        )

    pull = pull_decisions.get(release_id)
    if pull is not None:
        systems.add(SOURCE_PULL_LIST)
        normalized.append(
            {
                "system": SOURCE_PULL_LIST,
                "kind": "pull_list_decision",
                "decision_type": pull.decision_type,
                "confidence_score": float(pull.confidence_score),
            }
        )

    summary_payload = {
        "version": SUMMARY_VERSION,
        "normalized_signals": sorted(normalized, key=lambda row: (row["system"], row.get("kind", ""), str(row))),
        "purchase_context": purchase_context,
    }
    signal_summary = _canonical_summary(summary_payload)

    row = SpecInput(
        owner_user_id=owner_user_id,
        release_id=release_id,
        industry_candidate_id=industry_candidate_id,
        future_release_match_id=future_release_match_id,
        title=issue.title or f"{series_name} #{issue.issue_number}",
        publisher=publisher,
        series_name=series_name,
        issue_number=issue.issue_number,
        foc_date=issue.foc_date,
        release_date=issue.release_date,
        source_systems=_format_source_systems(systems),
        signal_summary=signal_summary,
    )
    return systems, summary_payload, row


def build_spec_inputs(session: Session, *, owner_user_id: int) -> SpecInputBuildResult:
    result = SpecInputBuildResult()
    purchase_context = _purchase_context(session, owner_user_id=owner_user_id)
    release_ids = _collect_release_ids(session, owner_user_id=owner_user_id)
    if not release_ids:
        session.commit()
        return result

    future_matches = latest_future_release_match_rows(session, owner_user_id=owner_user_id)
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)

    industry_by_release: dict[int, IndustryOpportunityScore] = {}
    signals_by_release: dict[int, list[IndustryReleaseSignal]] = {}
    if run_id is not None:
        for row in session.exec(
            select(IndustryOpportunityScore)
            .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
            .where(IndustryOpportunityScore.scan_run_id == run_id)
        ).all():
            industry_by_release[int(row.release_id)] = row
        for signal in session.exec(
            select(IndustryReleaseSignal)
            .where(IndustryReleaseSignal.owner_user_id == owner_user_id)
            .where(IndustryReleaseSignal.scan_run_id == run_id)
        ).all():
            signals_by_release.setdefault(int(signal.release_id), []).append(signal)

    pull_decisions: dict[int, PullListDecision] = {}
    for row in session.exec(select(PullListDecision).where(PullListDecision.owner_user_id == owner_user_id)).all():
        prior = pull_decisions.get(int(row.release_id))
        if prior is None or row.created_at >= prior.created_at:
            pull_decisions[int(row.release_id)] = row

    future_actions: dict[int, FutureReleaseAction] = {}
    for row in session.exec(
        select(FutureReleaseAction)
        .where(FutureReleaseAction.owner_user_id == owner_user_id)
        .where(FutureReleaseAction.release_id.is_not(None))
    ).all():
        if row.release_id is None:
            continue
        rid = int(row.release_id)
        prior = future_actions.get(rid)
        if prior is None or row.created_at >= prior.created_at:
            future_actions[rid] = row

    for release_id in sorted(release_ids):
        _, _, candidate_row = _build_row_payload(
            session,
            owner_user_id=owner_user_id,
            release_id=release_id,
            purchase_context=purchase_context,
            future_matches=future_matches,
            industry_by_release=industry_by_release,
            signals_by_release=signals_by_release,
            pull_decisions=pull_decisions,
            future_actions=future_actions,
        )
        existing = _find_existing_row(
            session,
            owner_user_id=owner_user_id,
            release_id=candidate_row.release_id,
            industry_candidate_id=candidate_row.industry_candidate_id,
            future_release_match_id=candidate_row.future_release_match_id,
        )
        if existing is not None and existing.signal_summary == candidate_row.signal_summary:
            result.skipped += 1
            continue
        if existing is not None:
            existing.title = candidate_row.title
            existing.publisher = candidate_row.publisher
            existing.series_name = candidate_row.series_name
            existing.issue_number = candidate_row.issue_number
            existing.foc_date = candidate_row.foc_date
            existing.release_date = candidate_row.release_date
            existing.source_systems = candidate_row.source_systems
            existing.signal_summary = candidate_row.signal_summary
            session.add(existing)
            result.updated += 1
            continue
        session.add(candidate_row)
        result.created += 1

    session.commit()
    return result
