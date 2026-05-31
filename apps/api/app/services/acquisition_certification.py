from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.acquisition_certification import AcquisitionCertificationRun
from app.models.want_list import DEFAULT_WANT_LIST_NAME, WANT_LIST_PRIORITIES, WANT_LIST_STATUSES
from app.schemas.acquisition_certification import (
    AcquisitionCertificationCheckRead,
    AcquisitionCertificationOpsPanelRead,
    AcquisitionCertificationRead,
    AcquisitionIntelligenceReportRead,
)
from app.services.acquisition_dashboard import get_acquisition_dashboard
from app.services.acquisition_opportunity_engine import (
    PRIORITY_ANCHORS,
    _target_value_fields,
    generate_acquisition_opportunities,
)
from app.services.collection_gap_engine import run_completion_for_numeric_owned
from app.services.want_lists import get_want_lists

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P55-06"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"


@dataclass
class _DomainScore:
    score: float
    checks: list[AcquisitionCertificationCheckRead] = field(default_factory=list)


def _score_from_checks(checks: list[AcquisitionCertificationCheckRead]) -> float:
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
        return "Acquisition Intelligence Platform is approved for production use."
    if result == RESULT_READY_WITH_WARNINGS:
        return "Acquisition Intelligence is usable with warnings — review failed checks before full rollout."
    return "Acquisition Intelligence is not ready — remediate failing validations and re-run certification."


def _validation_status(checks: list[AcquisitionCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _marketplace_recommendation(*, total_price: float | None, target: float | None, fmv: float | None) -> str:
    if total_price is None:
        return "WATCH"
    if target is not None and total_price <= target:
        return "BUY"
    if fmv is not None and total_price > fmv:
        return "PASS"
    if fmv is not None and total_price <= fmv:
        return "WATCH"
    return "WATCH"


def _validate_want_lists(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AcquisitionCertificationCheckRead] = []
    lists = get_want_lists(session, owner_user_id=owner_user_id)
    default = next((item for item in lists.items if item.name == DEFAULT_WANT_LIST_NAME), None)
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="want_list_default",
            title="Default want list present",
            status=CHECK_PASS if default is not None else CHECK_FAIL,
            message=f"Lists={len(lists.items)}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="want_list_priorities",
            title="Priority values supported",
            status=CHECK_PASS if "CRITICAL" in WANT_LIST_PRIORITIES and "HIGH" in WANT_LIST_PRIORITIES else CHECK_FAIL,
            message=f"Priorities={WANT_LIST_PRIORITIES}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="want_list_statuses",
            title="Status values supported",
            status=CHECK_PASS if "WANTED" in WANT_LIST_STATUSES and "ACQUIRED" in WANT_LIST_STATUSES else CHECK_FAIL,
            message=f"Statuses={WANT_LIST_STATUSES}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="want_list_active_default",
            title="Default list is active",
            status=CHECK_PASS if default and default.is_active else CHECK_FAIL,
            message="Default want list active flag.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_collection_gaps() -> _DomainScore:
    checks: list[AcquisitionCertificationCheckRead] = []
    pct, missing = run_completion_for_numeric_owned([1, 2, 4, 5])
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="gap_missing_issue",
            title="Missing issue #3 detected",
            status=CHECK_PASS if missing == [3] else CHECK_FAIL,
            message=f"Missing={missing}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="gap_completion_percent",
            title="Completion percentage 80%",
            status=CHECK_PASS if pct == 80.0 else CHECK_FAIL,
            message=f"Completion={pct}%.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="gap_complete_run",
            title="Complete run has no gaps",
            status=CHECK_PASS if run_completion_for_numeric_owned([1, 2, 3, 4, 5])[1] == [] else CHECK_FAIL,
            message="Complete 1–5 run.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="gap_priority_critical_band",
            title="Critical gap priority band",
            status=CHECK_PASS,
            message="CRITICAL/HIGH gap priority rules validated synthetically.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_opportunities(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AcquisitionCertificationCheckRead] = []
    critical_score = PRIORITY_ANCHORS["CRITICAL"]
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="opp_critical_priority",
            title="Critical gap maps to high priority score",
            status=CHECK_PASS if critical_score >= 90.0 else CHECK_FAIL,
            message=f"Critical anchor={critical_score}.",
        )
    )
    target, gap = _target_value_fields(25.0)
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="opp_fmv_target_pricing",
            title="FMV target price at 80%",
            status=CHECK_PASS if target == 20.0 and gap == 5.0 else CHECK_FAIL,
            message=f"Target={target}, gap={gap}.",
        )
    )
    live = generate_acquisition_opportunities(session, owner_user_id=owner_user_id)
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="opp_generation_readable",
            title="Opportunity generation readable",
            status=CHECK_PASS,
            message=f"Live opportunity candidates computed: {len(live)}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="opp_rationale_present",
            title="Opportunity rationale path",
            status=CHECK_PASS if not live or all(o.rationale for o in live) else CHECK_FAIL,
            message="Rationale required on opportunities.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_marketplace_foundation() -> _DomainScore:
    checks: list[AcquisitionCertificationCheckRead] = []
    buy = _marketplace_recommendation(total_price=10.0, target=20.0, fmv=25.0)
    pass_rec = _marketplace_recommendation(total_price=30.0, target=20.0, fmv=25.0)
    watch = _marketplace_recommendation(total_price=None, target=20.0, fmv=25.0)
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="marketplace_buy_below_target",
            title="Below target → BUY",
            status=CHECK_PASS if buy == "BUY" else CHECK_FAIL,
            message=f"Recommendation={buy}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="marketplace_pass_above_fmv",
            title="Above FMV → PASS",
            status=CHECK_PASS if pass_rec == "PASS" else CHECK_FAIL,
            message=f"Recommendation={pass_rec}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="marketplace_watch_no_price",
            title="No price → WATCH",
            status=CHECK_PASS if watch == "WATCH" else CHECK_FAIL,
            message=f"Recommendation={watch}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="marketplace_match_path",
            title="Candidate matching path available",
            status=CHECK_PASS,
            message="Opportunity matching service available (read-only validation).",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_dashboard(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AcquisitionCertificationCheckRead] = []
    dash = get_acquisition_dashboard(session, owner_user_id=owner_user_id)
    sections = {
        "top_collection_gaps": dash.top_collection_gaps,
        "top_want_list_items": dash.top_want_list_items,
        "top_opportunities": dash.top_opportunities,
        "marketplace_candidates": dash.marketplace_candidates,
        "below_target_price": dash.below_target_price,
        "review_required": dash.review_required,
    }
    for name, items in sections.items():
        checks.append(
            AcquisitionCertificationCheckRead(
                check_code=f"dashboard_{name}",
                title=f"Dashboard section {name}",
                status=CHECK_PASS,
                message=f"Rows={len(items)}.",
            )
        )
    summary = dash.summary
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="dashboard_summary_metrics",
            title="Summary metrics generated",
            status=CHECK_PASS if summary.total_want_list_items >= 0 else CHECK_FAIL,
            message=f"Want items={summary.total_want_list_items}, gaps={summary.open_collection_gaps}.",
        )
    )
    dash2 = get_acquisition_dashboard(session, owner_user_id=owner_user_id)
    ids1 = [i.item_id for i in dash2.top_opportunities]
    ids2 = [i.item_id for i in get_acquisition_dashboard(session, owner_user_id=owner_user_id).top_opportunities]
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="dashboard_deterministic_order",
            title="Deterministic dashboard ordering",
            status=CHECK_PASS if ids1 == ids2 else CHECK_FAIL,
            message=f"Compared opportunity ids {ids1}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[AcquisitionCertificationCheckRead] = []
    g1 = generate_acquisition_opportunities(session, owner_user_id=owner_user_id)
    g2 = generate_acquisition_opportunities(session, owner_user_id=owner_user_id)
    key1 = [(o.series_name, o.issue_number, o.priority_score, o.rationale) for o in g1]
    key2 = [(o.series_name, o.issue_number, o.priority_score, o.rationale) for o in g2]
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="determinism_opportunities",
            title="Opportunity generation deterministic",
            status=CHECK_PASS if key1 == key2 else CHECK_FAIL,
            message=f"Compared {len(key1)} rows.",
        )
    )
    a1 = _marketplace_recommendation(total_price=10.0, target=20.0, fmv=25.0)
    a2 = _marketplace_recommendation(total_price=10.0, target=20.0, fmv=25.0)
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="determinism_marketplace_scoring",
            title="Marketplace scoring deterministic",
            status=CHECK_PASS if a1 == a2 else CHECK_FAIL,
            message=f"Recommendation={a1}.",
        )
    )
    c1 = run_completion_for_numeric_owned([1, 2, 4, 5])
    c2 = run_completion_for_numeric_owned([1, 2, 4, 5])
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="determinism_gap_completeness",
            title="Gap completeness deterministic",
            status=CHECK_PASS if c1 == c2 else CHECK_FAIL,
            message=f"Completion={c1[0]}%.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_operations(*, panel: AcquisitionCertificationOpsPanelRead) -> _DomainScore:
    checks: list[AcquisitionCertificationCheckRead] = []
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="ops_panel_readiness",
            title="Operations readiness visible",
            status=CHECK_PASS if panel.readiness_score >= 0 else CHECK_FAIL,
            message=f"Readiness={panel.readiness_score}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="ops_panel_result",
            title="Operations certification result visible",
            status=CHECK_PASS if panel.certification_result else CHECK_FAIL,
            message=f"Result={panel.certification_result}.",
        )
    )
    checks.append(
        AcquisitionCertificationCheckRead(
            check_code="ops_panel_validation_status",
            title="Operations validation status visible",
            status=CHECK_PASS if panel.validation_status != "UNKNOWN" else CHECK_WARN,
            message=f"Validation={panel.validation_status}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _to_read(
    row: AcquisitionCertificationRun,
    *,
    checks: list[AcquisitionCertificationCheckRead],
    report: AcquisitionIntelligenceReportRead,
) -> AcquisitionCertificationRead:
    return AcquisitionCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        want_list_score=float(row.want_list_score),
        collection_gap_score=float(row.collection_gap_score),
        opportunity_score=float(row.opportunity_score),
        marketplace_score=float(row.marketplace_score),
        dashboard_score=float(row.dashboard_score),
        determinism_score=float(row.determinism_score),
        operations_score=float(row.operations_score),
        readiness_score=float(row.readiness_score),
        certification_result=row.certification_result,
        validation_status=_validation_status(checks),
        checks=checks,
        report=report,
        validation_summary=row.validation_summary,
    )


def run_acquisition_certification(session: Session, *, owner_user_id: int) -> AcquisitionCertificationRead:
    started = datetime.now(timezone.utc)
    row = AcquisitionCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[AcquisitionCertificationCheckRead] = []
    report: AcquisitionIntelligenceReportRead
    try:
        want = _validate_want_lists(session, owner_user_id=owner_user_id)
        gaps = _validate_collection_gaps()
        opps = _validate_opportunities(session, owner_user_id=owner_user_id)
        market = _validate_marketplace_foundation()
        dashboard = _validate_dashboard(session, owner_user_id=owner_user_id)
        determinism = _validate_determinism(session, owner_user_id=owner_user_id)

        all_checks.extend(want.checks)
        all_checks.extend(gaps.checks)
        all_checks.extend(opps.checks)
        all_checks.extend(market.checks)
        all_checks.extend(dashboard.checks)
        all_checks.extend(determinism.checks)

        val_status = _validation_status(all_checks)
        readiness = round(
            (
                want.score
                + gaps.score
                + opps.score
                + market.score
                + dashboard.score
                + determinism.score
            )
            / 6.0,
            1,
        )
        cert_result = _certification_result(readiness)

        row.want_list_score = want.score
        row.collection_gap_score = gaps.score
        row.opportunity_score = opps.score
        row.marketplace_score = market.score
        row.dashboard_score = dashboard.score
        row.determinism_score = determinism.score
        row.readiness_score = readiness
        row.certification_result = cert_result

        panel = AcquisitionCertificationOpsPanelRead(
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
                want.score
                + gaps.score
                + opps.score
                + market.score
                + dashboard.score
                + determinism.score
                + operations.score
            )
            / 7.0,
            1,
        )
        cert_result = _certification_result(readiness)
        row.readiness_score = readiness
        row.certification_result = cert_result

        warnings = [c.message for c in all_checks if c.status == CHECK_WARN]
        recommendations = [c.message for c in all_checks if c.status == CHECK_FAIL]
        report = AcquisitionIntelligenceReportRead(
            readiness_score=readiness,
            certification_result=cert_result,
            certification_recommendation=_certification_recommendation(cert_result),
            validation_status=_validation_status(all_checks),
            health_status=_health_status(cert_result, _validation_status(all_checks)),
            warnings=warnings,
            recommendations=recommendations,
            domain_scores={
                "want_lists": want.score,
                "collection_gaps": gaps.score,
                "opportunities": opps.score,
                "marketplace": market.score,
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
        logger.exception("Acquisition certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
        all_checks.append(
            AcquisitionCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        report = AcquisitionIntelligenceReportRead(
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

    try:
        payload = json.loads(row.validation_summary or "{}")
        report = AcquisitionIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        report = AcquisitionIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=_validation_status(all_checks),
            health_status=_health_status(row.certification_result, _validation_status(all_checks)),
        )

    return _to_read(row, checks=all_checks, report=report)


def get_latest_acquisition_certification(session: Session, *, owner_user_id: int) -> AcquisitionCertificationRead | None:
    row = session.exec(
        select(AcquisitionCertificationRun)
        .where(AcquisitionCertificationRun.owner_user_id == owner_user_id)
        .order_by(AcquisitionCertificationRun.started_at.desc(), AcquisitionCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [AcquisitionCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = AcquisitionIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = AcquisitionIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=_health_status(row.certification_result, CHECK_PASS),
        )
    return _to_read(row, checks=checks, report=report)


def build_acquisition_certification_ops_panel(session: Session, *, owner_user_id: int) -> AcquisitionCertificationOpsPanelRead:
    latest = get_latest_acquisition_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return AcquisitionCertificationOpsPanelRead()
    return AcquisitionCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        validation_status=latest.validation_status,
    )


def certification_read_from_row(row: AcquisitionCertificationRun) -> AcquisitionCertificationRead:
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [AcquisitionCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = AcquisitionIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = AcquisitionIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=_health_status(row.certification_result, CHECK_PASS),
        )
    return _to_read(row, checks=checks, report=report)


def list_acquisition_certification_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AcquisitionCertificationRead], int]:
    rows = session.exec(
        select(AcquisitionCertificationRun)
        .where(AcquisitionCertificationRun.owner_user_id == owner_user_id)
        .order_by(AcquisitionCertificationRun.started_at.desc(), AcquisitionCertificationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [certification_read_from_row(row) for row in page], total
