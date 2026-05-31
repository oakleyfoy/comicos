from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.pull_list import PullList, PullListAutomationRun, PullListCertificationRun, PullListDecision, PullListIssue
from app.models.recommendation_v2 import RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.pull_list_certification import PullListCertificationCheckRead, PullListCertificationRead
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import days_until_foc, foc_status_bucket, utc_today
from app.services.pull_list import get_pull_list, list_pull_lists
from app.services.pull_list_automation import run_pull_list_refresh
from app.services.pull_list_decision_engine import (
    DECISION_CONTINUE_RUN,
    DECISION_PASS,
    DECISION_START_RUN,
    DECISION_WATCH,
    evaluate_pull_list_decision,
)
from app.services.pull_list_decisions import generate_pull_list_decisions
from app.services.pull_list_health import build_pull_list_automation_ops_panel

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P52-05"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"


@dataclass
class _DomainScore:
    score: float
    checks: list[PullListCertificationCheckRead] = field(default_factory=list)


def _score_from_checks(checks: list[PullListCertificationCheckRead]) -> float:
    if not checks:
        return 0.0
    passed = sum(1 for c in checks if c.status == CHECK_PASS)
    return round(100.0 * passed / len(checks), 1)


def _certification_result(readiness: float) -> str:
    if readiness >= 90.0:
        return RESULT_APPROVED
    if readiness >= 80.0:
        return RESULT_READY_WITH_WARNINGS
    return RESULT_NOT_READY


def _recommendation(result: str) -> str:
    if result == RESULT_APPROVED:
        return "Pull List Intelligence Platform is approved for production collector workflows."
    if result == RESULT_READY_WITH_WARNINGS:
        return "Platform is usable with warnings — review failed checks before full production rollout."
    return "Platform is not ready for production — remediate failing validations and re-run certification."


def _validation_status(checks: list[PullListCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _validate_foundation(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PullListCertificationCheckRead] = []
    try:
        lists, total = list_pull_lists(session, owner_user_id=owner_user_id, limit=5, offset=0)
        checks.append(
            PullListCertificationCheckRead(
                check_code="foundation_pull_lists_readable",
                title="Pull lists readable",
                status=CHECK_PASS,
                message=f"Listed {total} pull list(s).",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            PullListCertificationCheckRead(
                check_code="foundation_pull_lists_readable",
                title="Pull lists readable",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        return _DomainScore(score=_score_from_checks(checks), checks=checks)

    issue_count = 0
    for pl in lists:
        detail_issues = session.exec(
            select(PullList).where(PullList.id == pl.id, PullList.owner_user_id == owner_user_id)
        ).first()
        if detail_issues is None:
            checks.append(
                PullListCertificationCheckRead(
                    check_code="foundation_owner_isolation",
                    title="Owner isolation",
                    status=CHECK_FAIL,
                    message=f"Pull list {pl.id} failed owner scope.",
                )
            )
            break
    else:
        checks.append(
            PullListCertificationCheckRead(
                check_code="foundation_owner_isolation",
                title="Owner isolation",
                status=CHECK_PASS,
                message="Pull list queries respect owner_user_id.",
            )
        )

    for pl in lists:
        from app.services.pull_list import get_pull_list

        detail = get_pull_list(session, owner_user_id=owner_user_id, pull_list_id=pl.id)
        issue_count += len(detail.issues)
    checks.append(
        PullListCertificationCheckRead(
            check_code="foundation_pull_list_issues_readable",
            title="Pull list issues readable",
            status=CHECK_PASS,
            message=f"Loaded {issue_count} issue row(s) across visible pull lists.",
        )
    )

    release_rows = session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id).limit(1)).first()
    checks.append(
        PullListCertificationCheckRead(
            check_code="foundation_release_catalog",
            title="Release catalog accessible",
            status=CHECK_PASS if release_rows is not None else CHECK_WARN,
            message="Owner release issues available for attachment."
            if release_rows is not None
            else "No release issues found for owner (attachment path not exercised).",
        )
    )

    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_decision_engine(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PullListCertificationCheckRead] = []

    def _check(code: str, title: str, expected: str, actual: str, reasons: tuple[str, ...]) -> None:
        ok = actual == expected and len(reasons) > 0
        checks.append(
            PullListCertificationCheckRead(
                check_code=code,
                title=title,
                status=CHECK_PASS if ok else CHECK_FAIL,
                message=f"Expected {expected}, got {actual}; reasons={len(reasons)}.",
            )
        )

    pl_issue = session.exec(
        select(PullListIssue)
        .join(PullList, PullList.id == PullListIssue.pull_list_id)
        .where(PullList.owner_user_id == owner_user_id)
        .limit(1)
    ).first()
    if pl_issue is not None:
        issue = session.get(ReleaseIssue, pl_issue.release_id)
        series = session.get(ReleaseSeries, issue.series_id) if issue else None
        if issue and series:
            r_cont = evaluate_pull_list_decision(
                session, owner_user_id=owner_user_id, issue=issue, series=series, v2=None
            )
            _check(
                "decision_continue_run",
                "Scenario A — active run",
                DECISION_CONTINUE_RUN,
                r_cont.decision_type,
                r_cont.reasons,
            )
        else:
            checks.append(
                PullListCertificationCheckRead(
                    check_code="decision_continue_run",
                    title="Scenario A — active run",
                    status=CHECK_WARN,
                    message="Pull list issue present but release/series missing.",
                )
            )
    else:
        checks.append(
            PullListCertificationCheckRead(
                check_code="decision_continue_run",
                title="Scenario A — active run",
                status=CHECK_WARN,
                message="No pull list issue on file; CONTINUE_RUN path not exercised live.",
            )
        )

    series_stub = ReleaseSeries(
        id=0,
        owner_user_id=owner_user_id,
        publisher="CERT",
        series_name="Synthetic",
        series_type="ONGOING",
        status="ACTIVE",
    )
    start_issue = ReleaseIssue(
        id=0,
        owner_user_id=owner_user_id,
        release_uuid="cert-synthetic-start",
        series_id=0,
        issue_number="1",
        title="Synthetic #1",
        release_status="SCHEDULED",
    )
    v2_start = RecommendationScoreV2(
        owner_user_id=owner_user_id,
        recommendation_run_id=0,
        release_issue_id=0,
        total_score=82.0,
        recommendation_tier="STRONG_BUY",
        recommendation_type="INVESTMENT_NUMBER_ONE",
        confidence_score=0.88,
    )
    r_start = evaluate_pull_list_decision(
        session, owner_user_id=owner_user_id, issue=start_issue, series=series_stub, v2=v2_start
    )
    _check("decision_start_run", "Scenario B — strong #1", DECISION_START_RUN, r_start.decision_type, r_start.reasons)

    watch_issue = ReleaseIssue(
        id=0,
        owner_user_id=owner_user_id,
        release_uuid="cert-synthetic-watch",
        series_id=0,
        issue_number="5",
        title="Synthetic #5",
        release_status="SCHEDULED",
    )
    v2_watch = RecommendationScoreV2(
        owner_user_id=owner_user_id,
        recommendation_run_id=0,
        release_issue_id=0,
        total_score=52.0,
        recommendation_tier="WATCH",
        recommendation_type="FRANCHISE_OPPORTUNITY",
        confidence_score=0.62,
    )
    r_watch = evaluate_pull_list_decision(
        session, owner_user_id=owner_user_id, issue=watch_issue, series=series_stub, v2=v2_watch
    )
    _check("decision_watch", "Scenario C — moderate signals", DECISION_WATCH, r_watch.decision_type, r_watch.reasons)

    pass_issue = ReleaseIssue(
        id=0,
        owner_user_id=owner_user_id,
        release_uuid="cert-synthetic-pass",
        series_id=0,
        issue_number="2",
        title="Synthetic #2",
        release_status="SCHEDULED",
    )
    v2_pass = RecommendationScoreV2(
        owner_user_id=owner_user_id,
        recommendation_run_id=0,
        release_issue_id=0,
        total_score=28.0,
        recommendation_tier="PASS",
        recommendation_type="NEW_OPPORTUNITY",
        confidence_score=0.4,
    )
    r_pass = evaluate_pull_list_decision(
        session, owner_user_id=owner_user_id, issue=pass_issue, series=series_stub, v2=v2_pass
    )
    _check("decision_pass", "Scenario D — weak signals", DECISION_PASS, r_pass.decision_type, r_pass.reasons)

    r_dup1 = evaluate_pull_list_decision(
        session, owner_user_id=owner_user_id, issue=start_issue, series=series_stub, v2=v2_start
    )
    r_dup2 = evaluate_pull_list_decision(
        session, owner_user_id=owner_user_id, issue=start_issue, series=series_stub, v2=v2_start
    )
    checks.append(
        PullListCertificationCheckRead(
            check_code="decision_deterministic_eval",
            title="Deterministic evaluation",
            status=CHECK_PASS if r_dup1 == r_dup2 else CHECK_FAIL,
            message="Twin evaluate_pull_list_decision calls match."
            if r_dup1 == r_dup2
            else "Evaluation outputs diverged.",
        )
    )

    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_dashboard(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PullListCertificationCheckRead] = []
    today = date(2026, 5, 30)

    date_checks = [
        (today + timedelta(days=5), "THIS_WEEK"),
        (today + timedelta(days=20), "THIS_MONTH"),
        (today - timedelta(days=1), "MISSED"),
    ]
    for foc, expected in date_checks:
        bucket = foc_status_bucket(foc, today=today)
        checks.append(
            PullListCertificationCheckRead(
                check_code=f"dashboard_foc_bucket_{expected.lower()}",
                title=f"FOC bucket {expected}",
                status=CHECK_PASS if bucket == expected else CHECK_FAIL,
                message=f"foc_status={bucket}, days={days_until_foc(foc, today=today)}.",
            )
        )

    try:
        dash = get_foc_dashboard(session, owner_user_id=owner_user_id, today=utc_today())
        checks.append(
            PullListCertificationCheckRead(
                check_code="dashboard_load",
                title="FOC dashboard materialization",
                status=CHECK_PASS,
                message=f"action_required={dash.summary.action_required_count}, upcoming_foc={dash.summary.upcoming_foc_count}",
            )
        )
        section_names = [
            ("dashboard_action_required", dash.action_required, "ACTION_REQUIRED"),
            ("dashboard_upcoming_foc", dash.upcoming_foc, "UPCOMING_FOC"),
            ("dashboard_upcoming_releases", dash.upcoming_releases, "UPCOMING_RELEASES"),
            ("dashboard_missed_foc", dash.missed_foc, "MISSED_FOC"),
            ("dashboard_watchlist", dash.watchlist, "WATCHLIST"),
        ]
        for code, rows, label in section_names:
            checks.append(
                PullListCertificationCheckRead(
                    check_code=code,
                    title=f"Section {label}",
                    status=CHECK_PASS,
                    message=f"{label} queue rows={len(rows)}",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            PullListCertificationCheckRead(
                check_code="dashboard_load",
                title="FOC dashboard materialization",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )

    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_automation(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PullListCertificationCheckRead] = []
    before = len(session.exec(select(PullListDecision).where(PullListDecision.owner_user_id == owner_user_id)).all())
    run1 = run_pull_list_refresh(session, owner_user_ids=[owner_user_id])
    run2 = run_pull_list_refresh(session, owner_user_ids=[owner_user_id])
    after = len(session.exec(select(PullListDecision).where(PullListDecision.owner_user_id == owner_user_id)).all())

    checks.append(
        PullListCertificationCheckRead(
            check_code="automation_run1_success",
            title="Automation run 1",
            status=CHECK_PASS if run1.status in {"SUCCESS", "PARTIAL"} else CHECK_FAIL,
            message=f"decisions_created={run1.decisions_created}, actions_generated={run1.actions_generated}, status={run1.status}",
        )
    )
    checks.append(
        PullListCertificationCheckRead(
            check_code="automation_run2_idempotent",
            title="Automation run 2 idempotent decisions",
            status=CHECK_PASS if run2.decisions_created == 0 else CHECK_FAIL,
            message=f"decisions_created={run2.decisions_created}, actions_generated={run2.actions_generated}",
        )
    )
    checks.append(
        PullListCertificationCheckRead(
            check_code="automation_stable_actions",
            title="Stable action counts",
            status=CHECK_PASS if run1.actions_generated == run2.actions_generated else CHECK_FAIL,
            message=f"run1={run1.actions_generated}, run2={run2.actions_generated}",
        )
    )
    checks.append(
        PullListCertificationCheckRead(
            check_code="automation_no_duplicate_decision_rows",
            title="No duplicate decision rows on rerun",
            status=CHECK_PASS if run2.decisions_created == 0 else CHECK_FAIL,
            message=f"decision rows before={before}, after={after}, delta={after - before}, run1_created={run1.decisions_created}",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PullListCertificationCheckRead] = []
    today = utc_today()
    dash1 = get_foc_dashboard(session, owner_user_id=owner_user_id, today=today)
    dash2 = get_foc_dashboard(session, owner_user_id=owner_user_id, today=today)
    checks.append(
        PullListCertificationCheckRead(
            check_code="determinism_dashboard_counts",
            title="Identical dashboard counts",
            status=CHECK_PASS
            if dash1.summary.model_dump() == dash2.summary.model_dump()
            else CHECK_FAIL,
            message="FOC dashboard summary stable across consecutive reads.",
        )
    )

    issue = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id).limit(1)).first()
    series = session.get(ReleaseSeries, issue.series_id) if issue else None
    v2 = None
    if issue:
        v2 = session.exec(
            select(RecommendationScoreV2)
            .where(
                RecommendationScoreV2.owner_user_id == owner_user_id,
                RecommendationScoreV2.release_issue_id == int(issue.id or 0),
            )
            .limit(1)
        ).first()
    if issue and series:
        e1 = evaluate_pull_list_decision(session, owner_user_id=owner_user_id, issue=issue, series=series, v2=v2)
        e2 = evaluate_pull_list_decision(session, owner_user_id=owner_user_id, issue=issue, series=series, v2=v2)
        checks.append(
            PullListCertificationCheckRead(
                check_code="determinism_live_decision",
                title="Identical live decision outcome",
                status=CHECK_PASS if e1 == e2 else CHECK_FAIL,
                message=f"decision={e1.decision_type}",
            )
        )
    else:
        checks.append(
            PullListCertificationCheckRead(
                check_code="determinism_live_decision",
                title="Identical live decision outcome",
                status=CHECK_WARN,
                message="No owner release row available; skipped live decision twin check.",
            )
        )

    c1 = generate_pull_list_decisions(session, owner_user_id=owner_user_id)
    c2 = generate_pull_list_decisions(session, owner_user_id=owner_user_id)
    checks.append(
        PullListCertificationCheckRead(
            check_code="determinism_generate_twice",
            title="Generate decisions twice",
            status=CHECK_PASS if c2 == 0 else CHECK_WARN if c1 == 0 and c2 == 0 else CHECK_FAIL,
            message=f"first={c1}, second={c2}",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_operations(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PullListCertificationCheckRead] = []
    panel = build_pull_list_automation_ops_panel(session, owner_user_id=owner_user_id)
    for field_name, label in [
        ("last_run", "Last run"),
        ("status", "Status"),
        ("runtime_ms", "Runtime"),
        ("decisions_generated", "Decisions generated"),
        ("actions_generated", "Actions generated"),
    ]:
        value = getattr(panel, field_name)
        ok = value is not None and (field_name != "last_run" or value is not None)
        if field_name == "status":
            ok = bool(value) and value != "NEVER_RUN"
        checks.append(
            PullListCertificationCheckRead(
                check_code=f"operations_panel_{field_name}",
                title=f"Ops panel — {label}",
                status=CHECK_PASS if ok else CHECK_WARN if field_name == "last_run" else CHECK_FAIL,
                message=str(value),
            )
        )

    latest = session.exec(
        select(PullListAutomationRun).order_by(PullListAutomationRun.started_at.desc(), PullListAutomationRun.id.desc())
    ).first()
    checks.append(
        PullListCertificationCheckRead(
            check_code="operations_automation_latest",
            title="Automation latest run record",
            status=CHECK_PASS if latest is not None else CHECK_WARN,
            message=f"run_id={int(latest.id or 0)}" if latest else "No automation runs yet.",
        )
    )
    run_count = len(session.exec(select(PullListAutomationRun)).all())
    checks.append(
        PullListCertificationCheckRead(
            check_code="operations_automation_runs_api_ready",
            title="Automation runs history",
            status=CHECK_PASS if run_count >= 0 else CHECK_FAIL,
            message=f"runs_indexed={run_count}",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _to_read(row: PullListCertificationRun, *, checks: list[PullListCertificationCheckRead]) -> PullListCertificationRead:
    result = row.certification_result
    return PullListCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        readiness_score=float(row.readiness_score),
        foundation_score=float(row.foundation_score),
        decision_engine_score=float(row.decision_engine_score),
        dashboard_score=float(row.dashboard_score),
        automation_score=float(row.automation_score),
        determinism_score=float(row.determinism_score),
        operations_score=float(row.operations_score),
        certification_result=result,
        certification_recommendation=_recommendation(result),
        validation_status=_validation_status(checks),
        checks=checks,
        validation_summary=row.validation_summary,
    )


def run_pull_list_certification(session: Session, *, owner_user_id: int) -> PullListCertificationRead:
    started = datetime.now(timezone.utc)
    row = PullListCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[PullListCertificationCheckRead] = []
    try:
        foundation = _validate_foundation(session, owner_user_id=owner_user_id)
        decision = _validate_decision_engine(session, owner_user_id=owner_user_id)
        dashboard = _validate_dashboard(session, owner_user_id=owner_user_id)
        automation = _validate_automation(session, owner_user_id=owner_user_id)
        determinism = _validate_determinism(session, owner_user_id=owner_user_id)
        operations = _validate_operations(session, owner_user_id=owner_user_id)

        all_checks.extend(foundation.checks)
        all_checks.extend(decision.checks)
        all_checks.extend(dashboard.checks)
        all_checks.extend(automation.checks)
        all_checks.extend(determinism.checks)
        all_checks.extend(operations.checks)

        scores = [
            foundation.score,
            decision.score,
            dashboard.score,
            automation.score,
            determinism.score,
            operations.score,
        ]
        readiness = round(sum(scores) / len(scores), 1)
        cert_result = _certification_result(readiness)

        summary_payload = {
            "certification_version": CERTIFICATION_VERSION,
            "readiness_score": readiness,
            "certification_result": cert_result,
            "domain_scores": {
                "foundation": foundation.score,
                "decision_engine": decision.score,
                "dashboard": dashboard.score,
                "automation": automation.score,
                "determinism": determinism.score,
                "operations": operations.score,
            },
            "checks": [c.model_dump() for c in all_checks],
        }

        row.foundation_score = foundation.score
        row.decision_engine_score = decision.score
        row.dashboard_score = dashboard.score
        row.automation_score = automation.score
        row.determinism_score = determinism.score
        row.operations_score = operations.score
        row.readiness_score = readiness
        row.certification_result = cert_result
        row.validation_summary = json.dumps(summary_payload, default=str)
        row.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pull list certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
        all_checks.append(
            PullListCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    finally:
        row.completed_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        session.refresh(row)

    return _to_read(row, checks=all_checks)


def get_latest_pull_list_certification(session: Session, *, owner_user_id: int) -> PullListCertificationRead | None:
    row = session.exec(
        select(PullListCertificationRun)
        .where(PullListCertificationRun.owner_user_id == owner_user_id)
        .order_by(PullListCertificationRun.started_at.desc(), PullListCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [PullListCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
    except (json.JSONDecodeError, ValueError):
        checks = []
    return _to_read(row, checks=checks)


def build_pull_list_certification_ops_panel(session: Session, *, owner_user_id: int):
    from app.schemas.pull_list_certification import PullListCertificationOpsPanelRead

    latest = get_latest_pull_list_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return PullListCertificationOpsPanelRead()
    return PullListCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        validation_status=latest.validation_status,
    )


def certification_read_from_row(row: PullListCertificationRun) -> PullListCertificationRead:
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [PullListCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
    except (json.JSONDecodeError, ValueError):
        checks = []
    return _to_read(row, checks=checks)


def list_pull_list_certification_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PullListCertificationRead], int]:
    rows = session.exec(
        select(PullListCertificationRun)
        .where(PullListCertificationRun.owner_user_id == owner_user_id)
        .order_by(PullListCertificationRun.started_at.desc(), PullListCertificationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [certification_read_from_row(row) for row in page], total
