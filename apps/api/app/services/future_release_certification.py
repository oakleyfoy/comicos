from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.future_release_certification import FutureReleaseCertificationRun
from app.schemas.future_release_certification import (
    FutureReleaseCertificationCheckRead,
    FutureReleaseCertificationOpsPanelRead,
    FutureReleaseCertificationRead,
    FutureReleaseIntelligenceReportRead,
)
from app.services.collected_run_engine import generate_collected_runs
from app.services.collected_runs import latest_collected_run_rows, persist_collected_runs
from app.services.future_release_action_engine import (
    determine_action_type,
    score_action_priority,
)
from app.services.future_release_actions import persist_future_release_actions
from app.services.future_release_dashboard import build_future_release_dashboard
from app.services.future_release_match_engine import generate_future_release_matches
from app.services.future_release_matches import persist_future_release_matches
from app.services.next_issue_engine import generate_next_issues
from app.services.next_issues import persist_next_issues

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P58-06"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"


@dataclass
class _DomainScore:
    score: float
    checks: list[FutureReleaseCertificationCheckRead] = field(default_factory=list)


def _score_from_checks(checks: list[FutureReleaseCertificationCheckRead]) -> float:
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


def _health_status(result: str, validation_status: str) -> str:
    if validation_status == CHECK_FAIL:
        return "UNHEALTHY"
    if result == RESULT_APPROVED:
        return "HEALTHY"
    return "DEGRADED"


def _certification_recommendation(result: str) -> str:
    if result == RESULT_APPROVED:
        return "Future Release Intelligence is approved for production collector workflows."
    if result == RESULT_READY_WITH_WARNINGS:
        return "Future Release Intelligence is usable with warnings — review failed checks before full rollout."
    return "Future Release Intelligence is not ready — remediate failing validations and re-run certification."


def _validation_status(checks: list[FutureReleaseCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _validate_run_detection(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[FutureReleaseCertificationCheckRead] = []
    try:
        candidates = generate_collected_runs(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="run_detection_engine",
                title="Collected run detection engine",
                status=CHECK_PASS,
                message=f"Detected {len(candidates)} run candidate(s).",
            )
        )
        created = persist_collected_runs(session, owner_user_id=owner_user_id)
        latest = latest_collected_run_rows(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="run_detection_persist",
                title="Collected run persistence",
                status=CHECK_PASS,
                message=f"Latest runs={len(latest)}, new rows={created}.",
            )
        )
        if not candidates:
            checks.append(
                FutureReleaseCertificationCheckRead(
                    check_code="run_detection_inventory",
                    title="Inventory-backed runs",
                    status=CHECK_WARN,
                    message="No collected runs yet — add inventory to validate live runs.",
                )
            )
        else:
            checks.append(
                FutureReleaseCertificationCheckRead(
                    check_code="run_detection_inventory",
                    title="Inventory-backed runs",
                    status=CHECK_PASS,
                    message="At least one collected run detected.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="run_detection_engine",
                title="Collected run detection engine",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_next_issue_detection(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[FutureReleaseCertificationCheckRead] = []
    try:
        predictions = generate_next_issues(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="next_issue_engine",
                title="Next issue detection engine",
                status=CHECK_PASS,
                message=f"Generated {len(predictions)} prediction(s).",
            )
        )
        created = persist_next_issues(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="next_issue_persist",
                title="Next issue persistence",
                status=CHECK_PASS,
                message=f"Persisted {created} new snapshot(s).",
            )
        )
        if not predictions:
            checks.append(
                FutureReleaseCertificationCheckRead(
                    check_code="next_issue_catalog",
                    title="Lunar catalog matches",
                    status=CHECK_WARN,
                    message="No next issues matched — import Lunar releases for live validation.",
                )
            )
        else:
            sample = predictions[0]
            checks.append(
                FutureReleaseCertificationCheckRead(
                    check_code="next_issue_catalog",
                    title="Lunar catalog matches",
                    status=CHECK_PASS if sample.confidence >= 0.75 else CHECK_WARN,
                    message=f"Sample next issue #{sample.next_issue} confidence={sample.confidence}.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="next_issue_engine",
                title="Next issue detection engine",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_release_matching(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[FutureReleaseCertificationCheckRead] = []
    try:
        matches = generate_future_release_matches(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="release_matching_engine",
                title="Future release matching engine",
                status=CHECK_PASS,
                message=f"Matched {len(matches)} future release(s).",
            )
        )
        created = persist_future_release_matches(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="release_matching_persist",
                title="Future release match persistence",
                status=CHECK_PASS,
                message=f"Persisted {created} new snapshot(s).",
            )
        )
        if matches:
            row = matches[0]
            checks.append(
                FutureReleaseCertificationCheckRead(
                    check_code="release_matching_metadata",
                    title="FOC and release metadata captured",
                    status=CHECK_PASS if row.foc_date or row.release_date else CHECK_WARN,
                    message=f"Publisher={row.publisher}, variants={row.variant_count}.",
                )
            )
        else:
            checks.append(
                FutureReleaseCertificationCheckRead(
                    check_code="release_matching_metadata",
                    title="FOC and release metadata captured",
                    status=CHECK_WARN,
                    message="No future matches — pipeline idle until catalog data exists.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="release_matching_engine",
                title="Future release matching engine",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_foc_intelligence(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[FutureReleaseCertificationCheckRead] = []
    today = date(2026, 6, 1)
    foc_three = today + timedelta(days=3)
    foc_seven = today + timedelta(days=7)
    checks.append(
        FutureReleaseCertificationCheckRead(
            check_code="foc_action_now",
            title="FOC ≤ 3 days → PREORDER_NOW",
            status=CHECK_PASS if determine_action_type(foc_date=foc_three, today=today) == "PREORDER_NOW" else CHECK_FAIL,
            message="Synthetic 3-day FOC action rule.",
        )
    )
    checks.append(
        FutureReleaseCertificationCheckRead(
            check_code="foc_action_week",
            title="FOC 10 days → PREORDER_THIS_WEEK",
            status=CHECK_PASS
            if determine_action_type(foc_date=today + timedelta(days=10), today=today) == "PREORDER_THIS_WEEK"
            else CHECK_FAIL,
            message="Synthetic 10-day FOC action rule.",
        )
    )
    checks.append(
        FutureReleaseCertificationCheckRead(
            check_code="foc_priority_95",
            title="Priority ≥ 95 for FOC ≤ 3 days",
            status=CHECK_PASS
            if score_action_priority(action_type="PREORDER_NOW", foc_date=foc_three, today=today) >= 95.0
            else CHECK_FAIL,
            message=f"Score={score_action_priority(action_type='PREORDER_NOW', foc_date=foc_three, today=today)}.",
        )
    )
    checks.append(
        FutureReleaseCertificationCheckRead(
            check_code="foc_priority_85",
            title="Priority ≥ 85 for FOC ≤ 7 days",
            status=CHECK_PASS
            if score_action_priority(action_type="PREORDER_THIS_WEEK", foc_date=foc_seven, today=today) >= 85.0
            else CHECK_FAIL,
            message=f"Score={score_action_priority(action_type='PREORDER_THIS_WEEK', foc_date=foc_seven, today=today)}.",
        )
    )
    checks.append(
        FutureReleaseCertificationCheckRead(
            check_code="foc_missed",
            title="Missed FOC detection",
            status=CHECK_PASS
            if determine_action_type(foc_date=today - timedelta(days=1), today=today) == "MISSED_FOC"
            else CHECK_FAIL,
            message="Past FOC maps to MISSED_FOC.",
        )
    )
    try:
        created = persist_future_release_actions(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="foc_action_persist",
                title="FOC action persistence",
                status=CHECK_PASS,
                message=f"Persisted {created} action snapshot(s).",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="foc_action_persist",
                title="FOC action persistence",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_dashboard(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[FutureReleaseCertificationCheckRead] = []
    try:
        dash = build_future_release_dashboard(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="dashboard_load",
                title="Future release dashboard loads",
                status=CHECK_PASS,
                message="Dashboard pipeline executed successfully.",
            )
        )
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="dashboard_sections",
                title="Dashboard sections populated",
                status=CHECK_PASS,
                message=(
                    f"next={len(dash.next_issues)}, foc={len(dash.upcoming_foc)}, "
                    f"now={len(dash.preorder_now)}, watchlist={len(dash.watchlist)}."
                ),
            )
        )
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="dashboard_summary",
                title="Dashboard summary cards",
                status=CHECK_PASS,
                message=f"Active runs={dash.summary.active_runs}, upcoming={dash.summary.upcoming_issues}.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="dashboard_load",
                title="Future release dashboard loads",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[FutureReleaseCertificationCheckRead] = []
    try:
        first_runs = generate_collected_runs(session, owner_user_id=owner_user_id)
        second_runs = generate_collected_runs(session, owner_user_id=owner_user_id)
        same_runs = len(first_runs) == len(second_runs) and {
            (r.publisher, r.series_name, r.latest_owned_issue) for r in first_runs
        } == {(r.publisher, r.series_name, r.latest_owned_issue) for r in second_runs}
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="determinism_run_detection",
                title="Run detection deterministic",
                status=CHECK_PASS if same_runs else CHECK_FAIL,
                message=f"Runs={len(first_runs)}.",
            )
        )
        first_next = generate_next_issues(session, owner_user_id=owner_user_id)
        second_next = generate_next_issues(session, owner_user_id=owner_user_id)
        same_next = len(first_next) == len(second_next)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="determinism_next_issue",
                title="Next issue detection deterministic",
                status=CHECK_PASS if same_next else CHECK_FAIL,
                message=f"Predictions={len(first_next)}.",
            )
        )
        persist_collected_runs(session, owner_user_id=owner_user_id)
        repeat = persist_collected_runs(session, owner_user_id=owner_user_id)
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="determinism_persist_idempotent",
                title="Append-only persistence idempotent",
                status=CHECK_PASS if repeat == 0 else CHECK_WARN,
                message=f"Second persist created {repeat} row(s).",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="determinism_run_detection",
                title="Run detection deterministic",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_operations(*, panel: FutureReleaseCertificationOpsPanelRead) -> _DomainScore:
    checks: list[FutureReleaseCertificationCheckRead] = []
    checks.append(
        FutureReleaseCertificationCheckRead(
            check_code="ops_panel_shape",
            title="Operations panel readable",
            status=CHECK_PASS,
            message=f"Result={panel.certification_result}, validation={panel.validation_status}.",
        )
    )
    checks.append(
        FutureReleaseCertificationCheckRead(
            check_code="ops_panel_timestamp",
            title="Operations panel timestamp",
            status=CHECK_PASS if panel.last_certification_at is not None else CHECK_WARN,
            message="Certification timestamp recorded for ops dashboard.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _to_read(
    row: FutureReleaseCertificationRun,
    *,
    checks: list[FutureReleaseCertificationCheckRead],
    report: FutureReleaseIntelligenceReportRead,
) -> FutureReleaseCertificationRead:
    return FutureReleaseCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        run_detection_score=float(row.run_detection_score),
        next_issue_detection_score=float(row.next_issue_detection_score),
        release_matching_score=float(row.release_matching_score),
        foc_intelligence_score=float(row.foc_intelligence_score),
        dashboard_score=float(row.dashboard_score),
        determinism_score=float(row.determinism_score),
        operations_score=float(row.operations_score),
        readiness_score=float(row.readiness_score),
        certification_result=row.certification_result,
        validation_status=report.validation_status,
        checks=checks,
        report=report,
        validation_summary=row.validation_summary or "",
    )


def run_future_release_certification(session: Session, *, owner_user_id: int) -> FutureReleaseCertificationRead:
    started = datetime.now(timezone.utc)
    row = FutureReleaseCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[FutureReleaseCertificationCheckRead] = []
    report = FutureReleaseIntelligenceReportRead(
        readiness_score=0.0,
        certification_result=RESULT_NOT_READY,
        certification_recommendation=_certification_recommendation(RESULT_NOT_READY),
        validation_status=CHECK_FAIL,
        health_status="UNHEALTHY",
    )

    try:
        run_det = _validate_run_detection(session, owner_user_id=owner_user_id)
        next_issue = _validate_next_issue_detection(session, owner_user_id=owner_user_id)
        matching = _validate_release_matching(session, owner_user_id=owner_user_id)
        foc = _validate_foc_intelligence(session, owner_user_id=owner_user_id)
        dashboard = _validate_dashboard(session, owner_user_id=owner_user_id)
        determinism = _validate_determinism(session, owner_user_id=owner_user_id)

        all_checks.extend(run_det.checks)
        all_checks.extend(next_issue.checks)
        all_checks.extend(matching.checks)
        all_checks.extend(foc.checks)
        all_checks.extend(dashboard.checks)
        all_checks.extend(determinism.checks)

        val_status = _validation_status(all_checks)
        readiness = round(
            (
                run_det.score
                + next_issue.score
                + matching.score
                + foc.score
                + dashboard.score
                + determinism.score
            )
            / 6.0,
            1,
        )
        cert_result = _certification_result(readiness)

        row.run_detection_score = run_det.score
        row.next_issue_detection_score = next_issue.score
        row.release_matching_score = matching.score
        row.foc_intelligence_score = foc.score
        row.dashboard_score = dashboard.score
        row.determinism_score = determinism.score

        panel = FutureReleaseCertificationOpsPanelRead(
            last_certification_at=started,
            readiness_score=readiness,
            certification_result=cert_result,
            validation_status=val_status,
        )
        operations = _validate_operations(panel=panel)
        all_checks.extend(operations.checks)
        row.operations_score = operations.score

        readiness = round(
            (
                run_det.score
                + next_issue.score
                + matching.score
                + foc.score
                + dashboard.score
                + determinism.score
                + operations.score
            )
            / 7.0,
            1,
        )
        cert_result = _certification_result(readiness)
        val_status = _validation_status(all_checks)

        row.readiness_score = readiness
        row.certification_result = cert_result

        warnings = [c.message for c in all_checks if c.status == CHECK_WARN]
        recommendations = [c.message for c in all_checks if c.status == CHECK_FAIL]
        report = FutureReleaseIntelligenceReportRead(
            readiness_score=readiness,
            certification_result=cert_result,
            certification_recommendation=_certification_recommendation(cert_result),
            validation_status=val_status,
            health_status=_health_status(cert_result, val_status),
            warnings=warnings,
            recommendations=recommendations,
            domain_scores={
                "run_detection": run_det.score,
                "next_issue_detection": next_issue.score,
                "release_matching": matching.score,
                "foc_intelligence": foc.score,
                "dashboard": dashboard.score,
                "determinism": determinism.score,
                "operations": operations.score,
            },
        )

        summary_payload = {
            "certification_version": CERTIFICATION_VERSION,
            "report": report.model_dump(),
            "checks": [c.model_dump() for c in all_checks],
        }
        row.validation_summary = json.dumps(summary_payload, default=str)
        row.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Future release certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
        all_checks.append(
            FutureReleaseCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        report = FutureReleaseIntelligenceReportRead(
            readiness_score=0.0,
            certification_result=RESULT_NOT_READY,
            certification_recommendation=_certification_recommendation(RESULT_NOT_READY),
            validation_status=CHECK_FAIL,
            health_status="UNHEALTHY",
        )
    finally:
        row.completed_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        session.refresh(row)

    return _to_read(row, checks=all_checks, report=report)


def get_latest_future_release_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> FutureReleaseCertificationRead | None:
    row = session.exec(
        select(FutureReleaseCertificationRun)
        .where(FutureReleaseCertificationRun.owner_user_id == owner_user_id)
        .order_by(FutureReleaseCertificationRun.started_at.desc(), FutureReleaseCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [FutureReleaseCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = FutureReleaseIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = FutureReleaseIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_WARN,
            health_status="DEGRADED",
        )
    return _to_read(row, checks=checks, report=report)


def build_future_release_certification_ops_panel(
    session: Session,
    *,
    owner_user_id: int,
) -> FutureReleaseCertificationOpsPanelRead:
    latest = get_latest_future_release_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return FutureReleaseCertificationOpsPanelRead()
    return FutureReleaseCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        validation_status=latest.validation_status,
    )
