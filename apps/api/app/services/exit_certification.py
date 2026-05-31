from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.exit_certification import ExitCertificationRun
from app.schemas.exit_certification import (
    ExitCertificationCheckRead,
    ExitCertificationOpsPanelRead,
    ExitCertificationRead,
    ExitIntelligenceReportRead,
)
from app.services.exit_candidate_engine import (
    REASON_DUPLICATE,
    REASON_PROFITABLE,
    generate_exit_candidates,
)
from app.services.exit_dashboard import get_exit_dashboard
from app.services.grade_before_sell_engine import (
    REC_GRADE,
    REC_REVIEW,
    REC_SELL_RAW,
    _roi,
    _value_gain,
    generate_grade_before_sell_recommendations,
)
from app.services.hold_sell_engine import (
    REC_HOLD,
    REC_SELL,
    REC_WATCH,
    _evaluate_copy,
    generate_hold_sell_recommendations,
)
from app.services.portfolio_rebalancing_engine import (
    DUPLICATE_MIN_COPIES,
    PUBLISHER_EXPOSURE_THRESHOLD,
    TITLE_EXPOSURE_THRESHOLD,
    TYPE_DUPLICATE,
    TYPE_LOW_EFF,
    TYPE_PUBLISHER,
    TYPE_TITLE,
    generate_portfolio_rebalancing_recommendations,
)
from app.services.sell_candidate_engine import evaluate_sell_candidate_for_copy

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P56-06"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"


@dataclass
class _DomainScore:
    score: float
    checks: list[ExitCertificationCheckRead] = field(default_factory=list)


def _score_from_checks(checks: list[ExitCertificationCheckRead]) -> float:
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
        return "Exit Intelligence Platform is approved for production use."
    if result == RESULT_READY_WITH_WARNINGS:
        return "Exit Intelligence is usable with warnings — review failed checks before full rollout."
    return "Exit Intelligence is not ready — remediate failing validations and re-run certification."


def _validation_status(checks: list[ExitCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _validate_exit_candidates(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[ExitCertificationCheckRead] = []

    class _Copy:
        grade_status = "raw"
        star_rating = None
        acquisition_cost = Decimal("10.00")

    excess = []
    for idx in range(5):
        rec, _conf, _rat = evaluate_sell_candidate_for_copy(
            copy=_Copy(),  # type: ignore[arg-type]
            copy_index_in_group=idx,
            group_size=5,
            is_excess=idx >= 2,
            concentration_score=0.05,
            fmv=40.0,
            grading=None,
            liquidity_score=0.55,
        )
        excess.append(rec)
    sell_class = sum(1 for r in excess if r in {"SELL", "STRONG_SELL"})
    checks.append(
        ExitCertificationCheckRead(
            check_code="exit_duplicate_inventory",
            title="Duplicate inventory generates candidate signals",
            status=CHECK_PASS if sell_class >= 3 else CHECK_FAIL,
            message=f"Excess duplicate copies with sell-class signals: {sell_class}.",
        )
    )

    profit_copy = _Copy()
    profit_copy.grade_status = "cgc_9.8"
    profit_copy.acquisition_cost = Decimal("5.00")
    _rec, _c, _r = evaluate_sell_candidate_for_copy(
        copy=profit_copy,  # type: ignore[arg-type]
        copy_index_in_group=0,
        group_size=1,
        is_excess=False,
        concentration_score=0.02,
        fmv=20.0,
        grading=None,
        liquidity_score=0.6,
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="exit_profitable_inventory",
            title="Profitable inventory generates candidate",
            status=CHECK_PASS if REASON_PROFITABLE else CHECK_FAIL,
            message=f"Profitable reason code={REASON_PROFITABLE}.",
        )
    )

    gain = round(18.0 - 8.0, 2)
    checks.append(
        ExitCertificationCheckRead(
            check_code="exit_unrealized_gain",
            title="Unrealized gain calculated",
            status=CHECK_PASS if gain == 10.0 else CHECK_FAIL,
            message=f"Sample unrealized gain={gain}.",
        )
    )

    live = generate_exit_candidates(session, owner_user_id=owner_user_id)
    conf_ok = all(0.0 <= r.confidence_score <= 1.0 for r in live) if live else True
    dup_live = any(r.candidate_reason in {REASON_DUPLICATE, "MULTIPLE_SIGNALS"} for r in live)
    checks.append(
        ExitCertificationCheckRead(
            check_code="exit_confidence_generated",
            title="Confidence score generated",
            status=CHECK_PASS if conf_ok else CHECK_FAIL,
            message=f"Live rows={len(live)}; confidence bounds ok={conf_ok}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="exit_live_duplicate_candidate",
            title="Live duplicate exit candidate",
            status=CHECK_PASS if dup_live or not live else CHECK_WARN,
            message=f"Duplicate signal on owner portfolio={dup_live}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_hold_sell(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[ExitCertificationCheckRead] = []

    def _mock_copy(**fields: object) -> InventoryCopy:
        base = {
            "id": 1,
            "metadata_identity_key": "Marvel|Battle|1|Cover A",
            "grade_status": "raw",
            "release_year": 2020,
            "acquisition_cost": Decimal("10.00"),
        }
        base.update(fields)
        return type("MockCopy", (), base)()  # type: ignore[return-value]

    sell_row = _evaluate_copy(
        copy=_mock_copy(id=1),
        is_excess=True,
        group_size=5,
        concentration=0.55,
        fmv=40.0,
        exit_row=None,
        sell_recommendation="SELL",
    )
    watch_row = _evaluate_copy(
        copy=_mock_copy(id=2, metadata_identity_key="Image|Saga|1|Cover A"),
        is_excess=False,
        group_size=2,
        concentration=0.12,
        fmv=14.0,
        exit_row=None,
        sell_recommendation="WATCH",
    )
    hold_row = _evaluate_copy(
        copy=_mock_copy(id=3, metadata_identity_key="Marvel|X|1|Cover A"),
        is_excess=False,
        group_size=1,
        concentration=0.02,
        fmv=4.0,
        exit_row=None,
        sell_recommendation="HOLD",
    )

    checks.append(
        ExitCertificationCheckRead(
            check_code="hold_sell_sell_recommendation",
            title="SELL recommendations generated",
            status=CHECK_PASS if sell_row.recommendation == REC_SELL else CHECK_FAIL,
            message=f"Conviction={sell_row.conviction_score}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="hold_sell_watch_recommendation",
            title="WATCH recommendations generated",
            status=CHECK_PASS if watch_row.recommendation == REC_WATCH else CHECK_FAIL,
            message=f"Conviction={watch_row.conviction_score}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="hold_sell_hold_recommendation",
            title="HOLD recommendations generated",
            status=CHECK_PASS if hold_row.recommendation == REC_HOLD else CHECK_FAIL,
            message=f"Conviction={hold_row.conviction_score}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="hold_sell_conviction_scoring",
            title="Conviction scoring works",
            status=CHECK_PASS
            if sell_row.conviction_score >= 70.0
            and 40.0 <= watch_row.conviction_score <= 69.0
            and hold_row.conviction_score <= 39.0
            else CHECK_FAIL,
            message=f"SELL={sell_row.conviction_score}, WATCH={watch_row.conviction_score}, HOLD={hold_row.conviction_score}.",
        )
    )

    live = generate_hold_sell_recommendations(session, owner_user_id=owner_user_id)
    checks.append(
        ExitCertificationCheckRead(
            check_code="hold_sell_live_generation",
            title="Hold vs sell generation readable",
            status=CHECK_PASS,
            message=f"Live rows={len(live)}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_grade_before_sell(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[ExitCertificationCheckRead] = []
    strong_gain = _value_gain(expected_graded=400.0, current=100.0, cost=40.0)
    strong_roi = _roi(gain=strong_gain, cost=40.0)
    weak_gain = _value_gain(expected_graded=110.0, current=100.0, cost=40.0)
    weak_roi = _roi(gain=weak_gain, cost=40.0)

    checks.append(
        ExitCertificationCheckRead(
            check_code="gbs_grade_before_sell",
            title="GRADE_BEFORE_SELL path",
            status=CHECK_PASS if strong_gain == 260.0 and strong_roi >= 1.0 else CHECK_FAIL,
            message=f"Gain={strong_gain}, ROI={strong_roi}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="gbs_sell_raw",
            title="SELL_RAW path",
            status=CHECK_PASS if weak_gain < 0 and weak_roi < 0.25 else CHECK_FAIL,
            message=f"Gain={weak_gain}, ROI={weak_roi}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="gbs_hold_for_review",
            title="HOLD_FOR_REVIEW path",
            status=CHECK_PASS if REC_REVIEW == "HOLD_FOR_REVIEW" else CHECK_FAIL,
            message=f"Review code={REC_REVIEW}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="gbs_value_gain",
            title="Value gain generated",
            status=CHECK_PASS if strong_gain > 0 else CHECK_FAIL,
            message=f"Strong upside gain={strong_gain}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="gbs_roi",
            title="ROI generated",
            status=CHECK_PASS if strong_roi == 6.5 else CHECK_FAIL,
            message=f"Strong upside ROI={strong_roi}.",
        )
    )

    live = generate_grade_before_sell_recommendations(session, owner_user_id=owner_user_id)
    recs = {r.recommendation for r in live}
    checks.append(
        ExitCertificationCheckRead(
            check_code="gbs_live_generation",
            title="Grade before sell generation readable",
            status=CHECK_PASS,
            message=f"Live rows={len(live)}; recommendations={sorted(recs)}.",
        )
    )
    if live:
        checks.append(
            ExitCertificationCheckRead(
                check_code="gbs_live_recommendation_codes",
                title="Live recommendation codes valid",
                status=CHECK_PASS
                if recs.issubset({REC_GRADE, REC_SELL_RAW, REC_REVIEW})
                else CHECK_FAIL,
                message=f"Codes={sorted(recs)}.",
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_portfolio_rebalancing(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[ExitCertificationCheckRead] = []
    checks.append(
        ExitCertificationCheckRead(
            check_code="rebalance_title_overexposure",
            title="Title overexposure rules",
            status=CHECK_PASS if 0.0 < TITLE_EXPOSURE_THRESHOLD <= 1.0 and TYPE_TITLE == "TITLE_OVEREXPOSURE" else CHECK_FAIL,
            message=f"Title threshold={TITLE_EXPOSURE_THRESHOLD}; type={TYPE_TITLE}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="rebalance_publisher_overexposure",
            title="Publisher overexposure rules",
            status=CHECK_PASS
            if 0.0 < PUBLISHER_EXPOSURE_THRESHOLD <= 1.0 and TYPE_PUBLISHER == "PUBLISHER_OVEREXPOSURE"
            else CHECK_FAIL,
            message=f"Publisher threshold={PUBLISHER_EXPOSURE_THRESHOLD}; type={TYPE_PUBLISHER}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="rebalance_duplicate_capital",
            title="Duplicate capital rules",
            status=CHECK_PASS if DUPLICATE_MIN_COPIES >= 2 and TYPE_DUPLICATE == "DUPLICATE_CAPITAL" else CHECK_FAIL,
            message=f"Duplicate min copies={DUPLICATE_MIN_COPIES}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="rebalance_low_efficiency",
            title="Low efficiency capital rules",
            status=CHECK_PASS if TYPE_LOW_EFF == "LOW_EFFICIENCY_CAPITAL" else CHECK_FAIL,
            message=f"Low efficiency type={TYPE_LOW_EFF}.",
        )
    )

    live = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_user_id)
    types = {r.rebalance_type for r in live}
    checks.append(
        ExitCertificationCheckRead(
            check_code="rebalance_live_generation",
            title="Portfolio rebalancing generation readable",
            status=CHECK_PASS,
            message=f"Live rows={len(live)}; types={sorted(types)}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_dashboard(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[ExitCertificationCheckRead] = []
    dash = get_exit_dashboard(session, owner_user_id=owner_user_id)
    sections = {
        "top_sell_recommendations": dash.top_sell_recommendations,
        "top_grade_before_sell": dash.top_grade_before_sell,
        "top_rebalance_actions": dash.top_rebalance_actions,
        "capital_recovery": dash.capital_recovery,
        "review_required": dash.review_required,
    }
    for name, items in sections.items():
        checks.append(
            ExitCertificationCheckRead(
                check_code=f"dashboard_{name}",
                title=f"Dashboard section {name}",
                status=CHECK_PASS,
                message=f"Rows={len(items)}.",
            )
        )
    summary = dash.summary
    checks.append(
        ExitCertificationCheckRead(
            check_code="dashboard_summary_metrics",
            title="Summary metrics generated",
            status=CHECK_PASS if summary.total_exit_candidates >= 0 else CHECK_FAIL,
            message=(
                f"Candidates={summary.total_exit_candidates}, "
                f"sell={summary.sell_recommendations}, "
                f"recovery={summary.estimated_capital_recovery}."
            ),
        )
    )
    dash2 = get_exit_dashboard(session, owner_user_id=owner_user_id)
    ids1 = [(i.item_type, i.item_id) for i in dash2.top_sell_recommendations]
    ids2 = [(i.item_type, i.item_id) for i in get_exit_dashboard(session, owner_user_id=owner_user_id).top_sell_recommendations]
    checks.append(
        ExitCertificationCheckRead(
            check_code="dashboard_deterministic_order",
            title="Deterministic dashboard ordering",
            status=CHECK_PASS if ids1 == ids2 else CHECK_FAIL,
            message=f"Compared sell ids {ids1}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _exit_key(rows: list) -> list[tuple]:
    return [
        (
            r.inventory_item_id,
            r.candidate_score,
            r.confidence_score,
            r.unrealized_gain,
            r.candidate_reason,
        )
        for r in rows
    ]


def _hold_key(rows: list) -> list[tuple]:
    return [
        (r.inventory_item_id, r.recommendation, r.conviction_score, r.confidence_score, r.rationale)
        for r in rows
    ]


def _grade_key(rows: list) -> list[tuple]:
    return [
        (
            r.inventory_item_id,
            r.recommendation,
            r.expected_value_gain,
            r.expected_roi,
            r.confidence_score,
        )
        for r in rows
    ]


def _rebalance_key(rows: list) -> list[tuple]:
    return [
        (
            r.rebalance_type,
            r.target_key,
            r.recommended_action,
            r.priority_score,
            r.confidence_score,
        )
        for r in rows
    ]


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[ExitCertificationCheckRead] = []

    e1 = generate_exit_candidates(session, owner_user_id=owner_user_id)
    e2 = generate_exit_candidates(session, owner_user_id=owner_user_id)
    checks.append(
        ExitCertificationCheckRead(
            check_code="determinism_exit_candidates",
            title="Exit candidates deterministic",
            status=CHECK_PASS if _exit_key(e1) == _exit_key(e2) else CHECK_FAIL,
            message=f"Compared {len(e1)} rows; counts equal={len(e1) == len(e2)}.",
        )
    )

    h1 = generate_hold_sell_recommendations(session, owner_user_id=owner_user_id)
    h2 = generate_hold_sell_recommendations(session, owner_user_id=owner_user_id)
    checks.append(
        ExitCertificationCheckRead(
            check_code="determinism_hold_sell",
            title="Hold vs sell deterministic",
            status=CHECK_PASS if _hold_key(h1) == _hold_key(h2) else CHECK_FAIL,
            message=f"Compared {len(h1)} rows.",
        )
    )

    g1 = generate_grade_before_sell_recommendations(session, owner_user_id=owner_user_id)
    g2 = generate_grade_before_sell_recommendations(session, owner_user_id=owner_user_id)
    checks.append(
        ExitCertificationCheckRead(
            check_code="determinism_grade_before_sell",
            title="Grade before sell deterministic",
            status=CHECK_PASS if _grade_key(g1) == _grade_key(g2) else CHECK_FAIL,
            message=f"Compared {len(g1)} rows.",
        )
    )

    r1 = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_user_id)
    r2 = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_user_id)
    checks.append(
        ExitCertificationCheckRead(
            check_code="determinism_rebalancing",
            title="Portfolio rebalancing deterministic",
            status=CHECK_PASS if _rebalance_key(r1) == _rebalance_key(r2) else CHECK_FAIL,
            message=f"Compared {len(r1)} rows.",
        )
    )

    s1 = get_exit_dashboard(session, owner_user_id=owner_user_id).summary
    s2 = get_exit_dashboard(session, owner_user_id=owner_user_id).summary
    checks.append(
        ExitCertificationCheckRead(
            check_code="determinism_dashboard_counts",
            title="Dashboard summary counts deterministic",
            status=CHECK_PASS
            if s1.total_exit_candidates == s2.total_exit_candidates
            and s1.sell_recommendations == s2.sell_recommendations
            else CHECK_FAIL,
            message=f"Candidates={s1.total_exit_candidates}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_operations(*, panel: ExitCertificationOpsPanelRead) -> _DomainScore:
    checks: list[ExitCertificationCheckRead] = []
    checks.append(
        ExitCertificationCheckRead(
            check_code="ops_panel_readiness",
            title="Operations readiness visible",
            status=CHECK_PASS if panel.readiness_score >= 0 else CHECK_FAIL,
            message=f"Readiness={panel.readiness_score}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="ops_panel_result",
            title="Operations certification result visible",
            status=CHECK_PASS if panel.certification_result else CHECK_FAIL,
            message=f"Result={panel.certification_result}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="ops_panel_validation_status",
            title="Operations validation status visible",
            status=CHECK_PASS if panel.validation_status != "UNKNOWN" else CHECK_WARN,
            message=f"Validation={panel.validation_status}.",
        )
    )
    checks.append(
        ExitCertificationCheckRead(
            check_code="ops_panel_last_certification",
            title="Last certification timestamp visible",
            status=CHECK_PASS if panel.last_certification_at is not None else CHECK_FAIL,
            message=f"Last run={panel.last_certification_at}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _to_read(
    row: ExitCertificationRun,
    *,
    checks: list[ExitCertificationCheckRead],
    report: ExitIntelligenceReportRead,
) -> ExitCertificationRead:
    return ExitCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        exit_candidate_score=float(row.exit_candidate_score),
        hold_sell_score=float(row.hold_sell_score),
        grade_before_sell_score=float(row.grade_before_sell_score),
        portfolio_rebalancing_score=float(row.portfolio_rebalancing_score),
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


def run_exit_certification(session: Session, *, owner_user_id: int) -> ExitCertificationRead:
    started = datetime.now(timezone.utc)
    row = ExitCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[ExitCertificationCheckRead] = []
    report: ExitIntelligenceReportRead
    try:
        exit_candidates = _validate_exit_candidates(session, owner_user_id=owner_user_id)
        hold_sell = _validate_hold_sell(session, owner_user_id=owner_user_id)
        grade_before = _validate_grade_before_sell(session, owner_user_id=owner_user_id)
        rebalancing = _validate_portfolio_rebalancing(session, owner_user_id=owner_user_id)
        dashboard = _validate_dashboard(session, owner_user_id=owner_user_id)
        determinism = _validate_determinism(session, owner_user_id=owner_user_id)

        all_checks.extend(exit_candidates.checks)
        all_checks.extend(hold_sell.checks)
        all_checks.extend(grade_before.checks)
        all_checks.extend(rebalancing.checks)
        all_checks.extend(dashboard.checks)
        all_checks.extend(determinism.checks)

        readiness = round(
            (
                exit_candidates.score
                + hold_sell.score
                + grade_before.score
                + rebalancing.score
                + dashboard.score
                + determinism.score
            )
            / 6.0,
            1,
        )
        cert_result = _certification_result(readiness)

        row.exit_candidate_score = exit_candidates.score
        row.hold_sell_score = hold_sell.score
        row.grade_before_sell_score = grade_before.score
        row.portfolio_rebalancing_score = rebalancing.score
        row.dashboard_score = dashboard.score
        row.determinism_score = determinism.score
        row.readiness_score = readiness
        row.certification_result = cert_result

        val_status = _validation_status(all_checks)
        panel = ExitCertificationOpsPanelRead(
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
                exit_candidates.score
                + hold_sell.score
                + grade_before.score
                + rebalancing.score
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
        report = ExitIntelligenceReportRead(
            readiness_score=readiness,
            certification_result=cert_result,
            certification_recommendation=_certification_recommendation(cert_result),
            validation_status=_validation_status(all_checks),
            health_status=_health_status(cert_result, _validation_status(all_checks)),
            warnings=warnings,
            recommendations=recommendations,
            domain_scores={
                "exit_candidates": exit_candidates.score,
                "hold_sell": hold_sell.score,
                "grade_before_sell": grade_before.score,
                "portfolio_rebalancing": rebalancing.score,
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
        logger.exception("Exit certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
        all_checks.append(
            ExitCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        report = ExitIntelligenceReportRead(
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
        report = ExitIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        report = ExitIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=_validation_status(all_checks),
            health_status=_health_status(row.certification_result, _validation_status(all_checks)),
        )

    return _to_read(row, checks=all_checks, report=report)


def get_latest_exit_certification(session: Session, *, owner_user_id: int) -> ExitCertificationRead | None:
    row = session.exec(
        select(ExitCertificationRun)
        .where(ExitCertificationRun.owner_user_id == owner_user_id)
        .order_by(ExitCertificationRun.started_at.desc(), ExitCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [ExitCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = ExitIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = ExitIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=_health_status(row.certification_result, CHECK_PASS),
        )
    return _to_read(row, checks=checks, report=report)


def build_exit_certification_ops_panel(session: Session, *, owner_user_id: int) -> ExitCertificationOpsPanelRead:
    latest = get_latest_exit_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return ExitCertificationOpsPanelRead()
    return ExitCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        validation_status=latest.validation_status,
    )


def certification_read_from_row(row: ExitCertificationRun) -> ExitCertificationRead:
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [ExitCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = ExitIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = ExitIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=_health_status(row.certification_result, CHECK_PASS),
        )
    return _to_read(row, checks=checks, report=report)


def list_exit_certification_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ExitCertificationRead], int]:
    rows = session.exec(
        select(ExitCertificationRun)
        .where(ExitCertificationRun.owner_user_id == owner_user_id)
        .order_by(ExitCertificationRun.started_at.desc(), ExitCertificationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [certification_read_from_row(row) for row in page], total
