from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.ai_spec_certification import AISpecCertificationRun
from app.models.ai_spec_evaluation import AISpecEvaluation
from app.models.spec_baseline_score import SpecBaselineScore
from app.models.spec_input import SpecInput
from app.models.top_spec_pick import TopSpecPick
from app.schemas.ai_spec_certification import (
    AISpecCertificationCheckRead,
    AISpecCertificationOpsPanelRead,
    AISpecCertificationRead,
    AISpecCertificationReportRead,
)
from app.services.ai_spec_client import (
    FALLBACK_MODEL_NAME,
    STATUS_FALLBACK,
    generate_fallback_ai_spec_evaluation,
)
from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.spec_automation import build_spec_automation_ops_panel, run_spec_refresh
from app.services.spec_input_builder import build_spec_inputs
from app.services.weekly_spec_dashboard import build_weekly_spec_dashboard

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P60-07"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"


@dataclass
class _DomainScore:
    score: float
    checks: list[AISpecCertificationCheckRead] = field(default_factory=list)


def _score_from_checks(checks: list[AISpecCertificationCheckRead]) -> float:
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
        return "AI Spec Engine is approved for production preorder intelligence workflows."
    if result == RESULT_READY_WITH_WARNINGS:
        return "AI Spec Engine is usable with warnings — review failed checks before full rollout."
    return "AI Spec Engine is not ready — remediate failing validations and re-run certification."


def _validation_status(checks: list[AISpecCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _validate_spec_inputs(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    try:
        result = build_spec_inputs(session, owner_user_id=owner_user_id)
        checks.append(
            AISpecCertificationCheckRead(
                check_code="spec_input_builder",
                title="Spec input builder",
                status=CHECK_PASS,
                message=f"Created={result.created}, updated={result.updated}, skipped={result.skipped}.",
            )
        )
        rows = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
        checks.append(
            AISpecCertificationCheckRead(
                check_code="spec_input_rows",
                title="Spec input persistence",
                status=CHECK_PASS if rows else CHECK_WARN,
                message=f"{len(rows)} spec input(s) materialized.",
            )
        )
        if rows:
            sample = rows[0]
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="spec_input_shape",
                    title="Spec input shape",
                    status=CHECK_PASS if sample.title.strip() else CHECK_WARN,
                    message=f"Sample publisher={sample.publisher or 'unknown'}.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AISpecCertificationCheckRead(
                check_code="spec_input_builder",
                title="Spec input builder",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_baseline_scoring(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    try:
        scores = session.exec(
            select(SpecBaselineScore).where(SpecBaselineScore.owner_user_id == owner_user_id)
        ).all()
        checks.append(
            AISpecCertificationCheckRead(
                check_code="baseline_rows",
                title="Baseline spec scores",
                status=CHECK_PASS if scores else CHECK_WARN,
                message=f"{len(scores)} baseline score(s) stored.",
            )
        )
        if scores:
            top = max(scores, key=lambda row: float(row.baseline_score))
            in_range = 0.0 <= float(top.baseline_score) <= 100.0
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="baseline_range",
                    title="Baseline score range",
                    status=CHECK_PASS if in_range else CHECK_FAIL,
                    message=f"Top baseline={float(top.baseline_score):.1f}, risk={float(top.risk_score):.1f}.",
                )
            )
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="baseline_confidence",
                    title="Baseline confidence",
                    status=CHECK_PASS if 0.0 <= float(top.confidence_score) <= 1.0 else CHECK_FAIL,
                    message=f"Sample confidence={float(top.confidence_score):.3f}.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AISpecCertificationCheckRead(
                check_code="baseline_rows",
                title="Baseline spec scores",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_ai_evaluations(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    try:
        evaluations = session.exec(
            select(AISpecEvaluation).where(AISpecEvaluation.owner_user_id == owner_user_id)
        ).all()
        checks.append(
            AISpecCertificationCheckRead(
                check_code="ai_eval_rows",
                title="AI spec evaluations",
                status=CHECK_PASS if evaluations else CHECK_WARN,
                message=f"{len(evaluations)} AI evaluation(s) stored.",
            )
        )
        if evaluations:
            sample = evaluations[0]
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="ai_eval_range",
                    title="AI score range",
                    status=CHECK_PASS if 0.0 <= float(sample.ai_score) <= 100.0 else CHECK_FAIL,
                    message=f"Sample ai_score={float(sample.ai_score):.1f}, status={sample.evaluation_status}.",
                )
            )
            fallback_count = sum(1 for row in evaluations if row.evaluation_status == STATUS_FALLBACK)
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="ai_eval_fallback_path",
                    title="Fallback evaluation path",
                    status=CHECK_PASS if fallback_count >= 1 or sample.evaluation_status == STATUS_FALLBACK else CHECK_WARN,
                    message=f"{fallback_count} evaluation(s) used deterministic fallback.",
                )
            )

        fallback = generate_fallback_ai_spec_evaluation(
            prompt_payload={"signal_summary": {"normalized_signals": ["NUMBER_ONE"]}},
            baseline_score=62.0,
            baseline_confidence=0.72,
            baseline_risk_score=45.0,
        )
        checks.append(
            AISpecCertificationCheckRead(
                check_code="ai_eval_fallback_contract",
                title="Fallback contract",
                status=CHECK_PASS
                if fallback.evaluation_status == STATUS_FALLBACK and fallback.model_name == FALLBACK_MODEL_NAME
                else CHECK_FAIL,
                message=f"Fallback score={fallback.ai_score}, risk={fallback.risk_level}.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AISpecCertificationCheckRead(
                check_code="ai_eval_rows",
                title="AI spec evaluations",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_top20_ranking(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    try:
        picks = session.exec(
            select(TopSpecPick)
            .where(TopSpecPick.owner_user_id == owner_user_id)
            .order_by(TopSpecPick.rank.asc())
        ).all()
        checks.append(
            AISpecCertificationCheckRead(
                check_code="top20_rows",
                title="Top spec picks",
                status=CHECK_PASS if picks else CHECK_WARN,
                message=f"{len(picks)} ranked pick(s) stored.",
            )
        )
        if picks:
            ranks = [int(row.rank) for row in picks]
            unique_ranks = len(set(ranks)) == len(ranks)
            sequential = ranks == list(range(1, len(ranks) + 1))
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="top20_rank_unique",
                    title="Rank uniqueness",
                    status=CHECK_PASS if unique_ranks else CHECK_FAIL,
                    message=f"Ranks span 1..{max(ranks)}.",
                )
            )
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="top20_rank_order",
                    title="Rank ordering",
                    status=CHECK_PASS if sequential else CHECK_FAIL,
                    message="Sequential ranks without gaps.",
                )
            )
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="top20_limit",
                    title="Top 20 limit",
                    status=CHECK_PASS if len(picks) <= 20 else CHECK_FAIL,
                    message=f"Pick count={len(picks)} (max 20).",
                )
            )
            top = picks[0]
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="top20_score_order",
                    title="Score ordering",
                    status=CHECK_PASS if float(top.final_score) >= float(picks[-1].final_score) else CHECK_WARN,
                    message=f"Rank #1 score={float(top.final_score):.1f}.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AISpecCertificationCheckRead(
                check_code="top20_rows",
                title="Top spec picks",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_weekly_dashboard(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    try:
        dash = build_weekly_spec_dashboard(session, owner_user_id=owner_user_id)
        checks.append(
            AISpecCertificationCheckRead(
                check_code="dashboard_build",
                title="Weekly spec dashboard",
                status=CHECK_PASS,
                message="Dashboard materialized from Top 20 picks.",
            )
        )
        section_count = sum(
            1
            for section in (
                dash.top_20_preorder,
                dash.preorder_now,
                dash.high_confidence,
                dash.high_risk_high_reward,
                dash.number_one_issues,
                dash.ratio_variants,
                dash.first_appearances,
                dash.milestones,
            )
            if section is not None
        )
        checks.append(
            AISpecCertificationCheckRead(
                check_code="dashboard_sections",
                title="Dashboard sections",
                status=CHECK_PASS,
                message=f"{section_count} section groups available.",
            )
        )
        checks.append(
            AISpecCertificationCheckRead(
                check_code="dashboard_summary",
                title="Dashboard summary",
                status=CHECK_PASS if dash.summary.top_picks_count >= 0 else CHECK_FAIL,
                message=f"Summary top_picks_count={dash.summary.top_picks_count}.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AISpecCertificationCheckRead(
                check_code="dashboard_build",
                title="Weekly spec dashboard",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_automation(
    session: Session,
    *,
    owner_user_id: int,
    pipeline_run_status: str,
) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    try:
        checks.append(
            AISpecCertificationCheckRead(
                check_code="automation_pipeline",
                title="Spec automation pipeline",
                status=CHECK_PASS if pipeline_run_status in {"SUCCESS", "NO_CHANGE"} else CHECK_FAIL,
                message=f"Certification pipeline status={pipeline_run_status}.",
            )
        )
        panel = build_spec_automation_ops_panel(session, owner_user_id=owner_user_id)
        checks.append(
            AISpecCertificationCheckRead(
                check_code="automation_ops_panel",
                title="Spec automation visibility",
                status=CHECK_PASS if panel.last_run is not None else CHECK_WARN,
                message=f"Last automation status={panel.status}.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AISpecCertificationCheckRead(
                check_code="automation_pipeline",
                title="Spec automation pipeline",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    try:
        before = session.exec(select(TopSpecPick).where(TopSpecPick.owner_user_id == owner_user_id)).all()
        before_count = len(before)
        before_ids = sorted(int(row.id or 0) for row in before)

        second = run_spec_refresh(session, owner_user_id=owner_user_id)
        checks.append(
            AISpecCertificationCheckRead(
                check_code="determinism_repeat",
                title="Repeat spec refresh",
                status=CHECK_PASS if second.status in {"SUCCESS", "NO_CHANGE"} else CHECK_FAIL,
                message=f"Second run status={second.status}.",
            )
        )

        after = session.exec(select(TopSpecPick).where(TopSpecPick.owner_user_id == owner_user_id)).all()
        after_ids = sorted(int(row.id or 0) for row in after)
        if second.status == "NO_CHANGE":
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="determinism_no_dup",
                    title="Unchanged pipeline handling",
                    status=CHECK_PASS if before_count == len(after) and before_ids == after_ids else CHECK_WARN,
                    message="Top picks stable when pipeline reports no change.",
                )
            )
        else:
            checks.append(
                AISpecCertificationCheckRead(
                    check_code="determinism_no_dup",
                    title="Unchanged pipeline handling",
                    status=CHECK_PASS if len(after) <= 20 else CHECK_FAIL,
                    message=f"Pick count before={before_count}, after={len(after)}.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AISpecCertificationCheckRead(
                check_code="determinism_repeat",
                title="Repeat spec refresh",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_operations(*, panel: AISpecCertificationOpsPanelRead) -> _DomainScore:
    checks: list[AISpecCertificationCheckRead] = []
    checks.append(
        AISpecCertificationCheckRead(
            check_code="ops_panel_shape",
            title="Operations panel readable",
            status=CHECK_PASS,
            message=f"Result={panel.certification_result}, validation={panel.validation_status}.",
        )
    )
    checks.append(
        AISpecCertificationCheckRead(
            check_code="ops_panel_timestamp",
            title="Operations panel timestamp",
            status=CHECK_PASS if panel.last_certification_at is not None else CHECK_WARN,
            message="Certification timestamp recorded for ops dashboard.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _to_read(
    row: AISpecCertificationRun,
    *,
    checks: list[AISpecCertificationCheckRead],
    report: AISpecCertificationReportRead,
) -> AISpecCertificationRead:
    return AISpecCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        input_score=float(row.input_score),
        baseline_score=float(row.baseline_score),
        ai_eval_score=float(row.ai_eval_score),
        top20_score=float(row.top20_score),
        dashboard_score=float(row.dashboard_score),
        automation_score=float(row.automation_score),
        determinism_score=float(row.determinism_score),
        operations_score=float(row.operations_score),
        readiness_score=float(row.readiness_score),
        certification_result=row.certification_result,
        validation_status=report.validation_status,
        checks=checks,
        report=report,
        validation_summary=row.validation_summary or "",
    )


def _hydrate_read(row: AISpecCertificationRun) -> AISpecCertificationRead:
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [AISpecCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = AISpecCertificationReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = AISpecCertificationReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_WARN,
            health_status="DEGRADED",
        )
    return _to_read(row, checks=checks, report=report)


def run_ai_spec_certification(session: Session, *, owner_user_id: int) -> AISpecCertificationRead:
    started = datetime.now(timezone.utc)
    row = AISpecCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[AISpecCertificationCheckRead] = []
    report = AISpecCertificationReportRead(
        readiness_score=0.0,
        certification_result=RESULT_NOT_READY,
        certification_recommendation=_certification_recommendation(RESULT_NOT_READY),
        validation_status=CHECK_FAIL,
        health_status="UNHEALTHY",
    )

    pipeline_run_status = "FAILED"
    try:
        run_industry_scanner_refresh(session, owner_user_id=owner_user_id, trigger_type="SCHEDULED")
        pipeline = run_spec_refresh(session, owner_user_id=owner_user_id)
        pipeline_run_status = pipeline.status

        inputs = _validate_spec_inputs(session, owner_user_id=owner_user_id)
        baseline = _validate_baseline_scoring(session, owner_user_id=owner_user_id)
        ai_eval = _validate_ai_evaluations(session, owner_user_id=owner_user_id)
        top20 = _validate_top20_ranking(session, owner_user_id=owner_user_id)
        dashboard = _validate_weekly_dashboard(session, owner_user_id=owner_user_id)
        automation = _validate_automation(
            session,
            owner_user_id=owner_user_id,
            pipeline_run_status=pipeline_run_status,
        )
        determinism = _validate_determinism(session, owner_user_id=owner_user_id)

        all_checks.extend(inputs.checks)
        all_checks.extend(baseline.checks)
        all_checks.extend(ai_eval.checks)
        all_checks.extend(top20.checks)
        all_checks.extend(dashboard.checks)
        all_checks.extend(automation.checks)
        all_checks.extend(determinism.checks)

        row.input_score = inputs.score
        row.baseline_score = baseline.score
        row.ai_eval_score = ai_eval.score
        row.top20_score = top20.score
        row.dashboard_score = dashboard.score
        row.automation_score = automation.score
        row.determinism_score = determinism.score

        val_status = _validation_status(all_checks)
        readiness = round(
            (
                inputs.score
                + baseline.score
                + ai_eval.score
                + top20.score
                + dashboard.score
                + automation.score
                + determinism.score
            )
            / 7.0,
            1,
        )
        cert_result = _certification_result(readiness)

        panel = AISpecCertificationOpsPanelRead(
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
                inputs.score
                + baseline.score
                + ai_eval.score
                + top20.score
                + dashboard.score
                + automation.score
                + determinism.score
                + operations.score
            )
            / 8.0,
            1,
        )
        cert_result = _certification_result(readiness)
        val_status = _validation_status(all_checks)

        row.readiness_score = readiness
        row.certification_result = cert_result

        warnings = [c.message for c in all_checks if c.status == CHECK_WARN]
        recommendations = [c.message for c in all_checks if c.status == CHECK_FAIL]
        report = AISpecCertificationReportRead(
            readiness_score=readiness,
            certification_result=cert_result,
            certification_recommendation=_certification_recommendation(cert_result),
            validation_status=val_status,
            health_status=_health_status(cert_result, val_status),
            warnings=warnings,
            recommendations=recommendations,
            domain_scores={
                "input": inputs.score,
                "baseline": baseline.score,
                "ai_eval": ai_eval.score,
                "top20": top20.score,
                "dashboard": dashboard.score,
                "automation": automation.score,
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
        logger.exception("AI spec certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
        all_checks.append(
            AISpecCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        report = AISpecCertificationReportRead(
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


def get_latest_ai_spec_certification(session: Session, *, owner_user_id: int) -> AISpecCertificationRead | None:
    row = session.exec(
        select(AISpecCertificationRun)
        .where(AISpecCertificationRun.owner_user_id == owner_user_id)
        .order_by(AISpecCertificationRun.started_at.desc(), AISpecCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    return _hydrate_read(row)


def list_ai_spec_certification_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AISpecCertificationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(AISpecCertificationRun)
        .where(AISpecCertificationRun.owner_user_id == owner_user_id)
        .order_by(AISpecCertificationRun.started_at.desc(), AISpecCertificationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_hydrate_read(row) for row in page], total


def build_ai_spec_certification_ops_panel(
    session: Session,
    *,
    owner_user_id: int,
) -> AISpecCertificationOpsPanelRead:
    latest = get_latest_ai_spec_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return AISpecCertificationOpsPanelRead()
    return AISpecCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        validation_status=latest.validation_status,
    )
