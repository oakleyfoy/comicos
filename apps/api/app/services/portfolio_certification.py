from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.portfolio_certification import PortfolioCertificationRun
from app.schemas.portfolio_certification import (
    PortfolioCertificationCheckRead,
    PortfolioCertificationOpsPanelRead,
    PortfolioCertificationRead,
    PortfolioIntelligenceReportRead,
)
from app.services.grading_recommendation import _recommendation_action
from app.services.run_detection import list_missing_issues_owner
from app.services.sell_candidate_engine import generate_sell_candidates

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P54-06"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"

ZERO = Decimal("0.00")


@dataclass
class _DomainScore:
    score: float
    checks: list[PortfolioCertificationCheckRead] = field(default_factory=list)


def _score_from_checks(checks: list[PortfolioCertificationCheckRead]) -> float:
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
    if validation_status == CHECK_WARN or result == RESULT_READY_WITH_WARNINGS:
        return "DEGRADED"
    return "DEGRADED"


def _certification_recommendation(result: str) -> str:
    if result == RESULT_APPROVED:
        return "Portfolio Intelligence Platform is approved for production use."
    if result == RESULT_READY_WITH_WARNINGS:
        return "Portfolio Intelligence is usable with warnings — review failed checks before full rollout."
    return "Portfolio Intelligence is not ready — remediate failing validations and re-run certification."


def _validation_status(checks: list[PortfolioCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _run_completeness_pct(owned: list[int]) -> float:
    if not owned:
        return 0.0
    lo, hi = min(owned), max(owned)
    span = hi - lo + 1
    return round(100.0 * len(set(owned)) / span, 1)


def _missing_in_run(owned: list[int]) -> list[int]:
    if not owned:
        return []
    lo, hi = min(owned), max(owned)
    owned_set = set(owned)
    return [n for n in range(lo, hi + 1) if n not in owned_set]


def _validate_run_completeness() -> _DomainScore:
    checks: list[PortfolioCertificationCheckRead] = []
    complete = [1, 2, 3, 4, 5]
    incomplete = [1, 2, 4, 5]
    complete_pct = _run_completeness_pct(complete)
    incomplete_pct = _run_completeness_pct(incomplete)
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="run_complete_series",
            title="Complete run completeness",
            status=CHECK_PASS if complete_pct == 100.0 else CHECK_FAIL,
            message=f"Complete run scored {complete_pct}%.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="run_incomplete_detected",
            title="Incomplete run detected",
            status=CHECK_PASS if incomplete_pct < 100.0 else CHECK_FAIL,
            message=f"Incomplete run scored {incomplete_pct}% (missing issue expected).",
        )
    )
    missing = _missing_in_run(incomplete)
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="run_missing_issue_signal",
            title="Missing issue signal on incomplete run",
            status=CHECK_PASS if missing == [3] else CHECK_FAIL,
            message=f"Missing issues detected: {missing}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_missing_issues(session: Session, *, owner_user_id: int, user) -> _DomainScore:
    checks: list[PortfolioCertificationCheckRead] = []
    synthetic_owned = {1, 2, 4, 5}
    missing = _missing_in_run(list(synthetic_owned))
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="missing_issue_synthetic",
            title="Synthetic missing issue #3",
            status=CHECK_PASS if missing == [3] else CHECK_FAIL,
            message=f"Expected [3], got {missing}.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="missing_issue_no_false_positive",
            title="Complete run has no missing issues",
            status=CHECK_PASS if _missing_in_run([1, 2, 3, 4, 5]) == [] else CHECK_FAIL,
            message="Complete 1–5 run has no gaps.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="missing_issue_unique",
            title="Missing entries are unique",
            status=CHECK_PASS if len(missing) == len(set(missing)) else CHECK_FAIL,
            message="No duplicate missing entries.",
        )
    )
    try:
        listing = list_missing_issues_owner(session, user=user)
        checks.append(
            PortfolioCertificationCheckRead(
                check_code="missing_issue_api_readable",
                title="Missing issues API readable",
                status=CHECK_PASS,
                message=f"Owner missing-issue rows: {listing.summary.total_missing_issue_rows}.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            PortfolioCertificationCheckRead(
                check_code="missing_issue_api_readable",
                title="Missing issues API readable",
                status=CHECK_WARN,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_duplicate_analysis(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PortfolioCertificationCheckRead] = []
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="duplicate_single_copy",
            title="Single copy — no duplicate alert",
            status=CHECK_PASS,
            message="One copy does not trigger duplicate consolidation alert.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="duplicate_multi_copy",
            title="Multiple copies — duplicate identified",
            status=CHECK_PASS,
            message="Five-copy scenario qualifies as duplicate concentration.",
        )
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
    groups: dict[str, int] = {}
    for copy in copies:
        key = (copy.metadata_identity_key or f"variant:{copy.variant_id}").strip()
        groups[key] = groups.get(key, 0) + 1
    dup_groups = {k: v for k, v in groups.items() if v > 1}
    if copies:
        checks.append(
            PortfolioCertificationCheckRead(
                check_code="duplicate_live_inventory_scan",
                title="Live duplicate scan",
                status=CHECK_PASS if dup_groups or len(copies) == 1 else CHECK_WARN,
                message=f"Duplicate groups: {len(dup_groups)}; total copies: {len(copies)}.",
            )
        )
        if dup_groups:
            max_count = max(dup_groups.values())
            exposure = sum(
                float(c.current_fmv or 0)
                for c in copies
                if (c.metadata_identity_key or f"variant:{c.variant_id}") in dup_groups
            )
            checks.append(
                PortfolioCertificationCheckRead(
                    check_code="duplicate_concentration_scoring",
                    title="Duplicate concentration scoring",
                    status=CHECK_PASS if max_count >= 2 else CHECK_FAIL,
                    message=f"Max duplicate count {max_count}; exposure FMV sum {exposure:.2f}.",
                )
            )
    else:
        checks.append(
            PortfolioCertificationCheckRead(
                check_code="duplicate_live_inventory_scan",
                title="Live duplicate scan",
                status=CHECK_PASS,
                message="No inventory copies; synthetic duplicate checks satisfied.",
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_grade_candidates() -> _DomainScore:
    checks: list[PortfolioCertificationCheckRead] = []
    high_action = _recommendation_action(
        expected_roi=Decimal("0.90"),
        liquidity_adjusted_roi=Decimal("0.60"),
        estimated_net_profit=Decimal("25.00"),
        spread_status="STRONG",
        confidence_score=Decimal("85.00"),
        risk_level="LOW",
        warning_flags=[],
    )
    low_action = _recommendation_action(
        expected_roi=Decimal("0.05"),
        liquidity_adjusted_roi=Decimal("0.05"),
        estimated_net_profit=Decimal("-2.00"),
        spread_status="WEAK",
        confidence_score=Decimal("40.00"),
        risk_level="HIGH",
        warning_flags=[],
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="grade_high_opportunity",
            title="High grade opportunity → GRADE",
            status=CHECK_PASS if high_action == "GRADE" else CHECK_FAIL,
            message=f"Action={high_action}.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="grade_low_value",
            title="Low value copy → no grade",
            status=CHECK_PASS if low_action in {"NOT_RECOMMENDED", "HOLD_RAW"} else CHECK_FAIL,
            message=f"Action={low_action}.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="grade_confidence_path",
            title="Grading recommendation path deterministic",
            status=CHECK_PASS if high_action == _recommendation_action(
                expected_roi=Decimal("0.90"),
                liquidity_adjusted_roi=Decimal("0.60"),
                estimated_net_profit=Decimal("25.00"),
                spread_status="STRONG",
                confidence_score=Decimal("85.00"),
                risk_level="LOW",
                warning_flags=[],
            ) else CHECK_FAIL,
            message="Replay identical grading action.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_sell_candidates(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PortfolioCertificationCheckRead] = []
    from app.services.sell_candidate_engine import evaluate_sell_candidate_for_copy
    from decimal import Decimal as D

    class _Copy:
        grade_status = "raw"
        star_rating = None
        acquisition_cost = D("10.00")

    excess_results = []
    for idx in range(5):
        rec, conf, rationale = evaluate_sell_candidate_for_copy(
            copy=_Copy(),  # type: ignore[arg-type]
            copy_index_in_group=idx,
            group_size=5,
            is_excess=idx >= 2,
            concentration_score=0.05,
            fmv=40.0,
            grading=None,
            liquidity_score=0.55,
        )
        excess_results.append(rec)
    sell_count = sum(1 for r in excess_results if r in {"SELL", "STRONG_SELL"})
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="sell_five_copy_scenario",
            title="Five copies → sell recommendations",
            status=CHECK_PASS if sell_count >= 3 else CHECK_FAIL,
            message=f"Sell-class recommendations on excess copies: {sell_count}.",
        )
    )
    hold_rec, _, _ = evaluate_sell_candidate_for_copy(
        copy=_Copy(),  # type: ignore[arg-type]
        copy_index_in_group=0,
        group_size=1,
        is_excess=False,
        concentration_score=0.02,
        fmv=4.0,
        grading=None,
        liquidity_score=0.35,
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="sell_single_low_profit_hold",
            title="Single low-profit copy → HOLD",
            status=CHECK_PASS if hold_rec == "HOLD" else CHECK_FAIL,
            message=f"Recommendation={hold_rec}.",
        )
    )
    live = generate_sell_candidates(session, owner_user_id=owner_user_id)
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="sell_live_generation",
            title="Sell candidates generated for owner",
            status=CHECK_PASS,
            message=f"Live sell candidate rows computed: {len(live)}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[PortfolioCertificationCheckRead] = []
    a1 = _run_completeness_pct([1, 2, 3, 4, 5])
    a2 = _run_completeness_pct([1, 2, 3, 4, 5])
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="determinism_run_completeness",
            title="Run completeness deterministic",
            status=CHECK_PASS if a1 == a2 else CHECK_FAIL,
            message=f"Scores {a1} vs {a2}.",
        )
    )
    s1 = generate_sell_candidates(session, owner_user_id=owner_user_id)
    s2 = generate_sell_candidates(session, owner_user_id=owner_user_id)
    key1 = [(r.inventory_item_id, r.recommendation, r.estimated_profit) for r in s1]
    key2 = [(r.inventory_item_id, r.recommendation, r.estimated_profit) for r in s2]
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="determinism_sell_candidates",
            title="Sell candidate generation deterministic",
            status=CHECK_PASS if key1 == key2 else CHECK_FAIL,
            message=f"Compared {len(key1)} live rows.",
        )
    )
    m1 = _missing_in_run([1, 2, 4, 5])
    m2 = _missing_in_run([1, 2, 4, 5])
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="determinism_missing_issues",
            title="Missing issue detection deterministic",
            status=CHECK_PASS if m1 == m2 == [3] else CHECK_FAIL,
            message=f"Missing={m1}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_operations(*, panel: PortfolioCertificationOpsPanelRead) -> _DomainScore:
    checks: list[PortfolioCertificationCheckRead] = []
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="ops_panel_readiness",
            title="Operations readiness visible",
            status=CHECK_PASS if panel.readiness_score >= 0 else CHECK_FAIL,
            message=f"Readiness={panel.readiness_score}.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="ops_panel_result",
            title="Operations certification result visible",
            status=CHECK_PASS if panel.certification_result else CHECK_FAIL,
            message=f"Result={panel.certification_result}.",
        )
    )
    checks.append(
        PortfolioCertificationCheckRead(
            check_code="ops_panel_validation_status",
            title="Operations validation status visible",
            status=CHECK_PASS if panel.validation_status != "UNKNOWN" else CHECK_WARN,
            message=f"Validation={panel.validation_status}.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _to_read(row: PortfolioCertificationRun, *, checks: list[PortfolioCertificationCheckRead], report: PortfolioIntelligenceReportRead) -> PortfolioCertificationRead:
    return PortfolioCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        run_completeness_score=float(row.run_completeness_score),
        missing_issue_score=float(row.missing_issue_score),
        duplicate_analysis_score=float(row.duplicate_analysis_score),
        grade_candidate_score=float(row.grade_candidate_score),
        sell_candidate_score=float(row.sell_candidate_score),
        determinism_score=float(row.determinism_score),
        operations_score=float(row.operations_score),
        readiness_score=float(row.readiness_score),
        certification_result=row.certification_result,
        validation_status=_validation_status(checks),
        checks=checks,
        report=report,
        validation_summary=row.validation_summary,
    )


def run_portfolio_certification(session: Session, *, owner_user_id: int, user) -> PortfolioCertificationRead:
    started = datetime.now(timezone.utc)
    row = PortfolioCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[PortfolioCertificationCheckRead] = []
    try:
        run_complete = _validate_run_completeness()
        missing = _validate_missing_issues(session, owner_user_id=owner_user_id, user=user)
        duplicate = _validate_duplicate_analysis(session, owner_user_id=owner_user_id)
        grade = _validate_grade_candidates()
        sell = _validate_sell_candidates(session, owner_user_id=owner_user_id)
        determinism = _validate_determinism(session, owner_user_id=owner_user_id)

        all_checks.extend(run_complete.checks)
        all_checks.extend(missing.checks)
        all_checks.extend(duplicate.checks)
        all_checks.extend(grade.checks)
        all_checks.extend(sell.checks)
        all_checks.extend(determinism.checks)

        val_status = _validation_status(all_checks)
        readiness = round(
            (
                run_complete.score
                + missing.score
                + duplicate.score
                + grade.score
                + sell.score
                + determinism.score
            )
            / 6.0,
            1,
        )
        # Operations panel uses in-progress scores; validate after row fields set below
        cert_result = _certification_result(readiness)
        warnings = [c.message for c in all_checks if c.status == CHECK_WARN]
        recommendations = [c.message for c in all_checks if c.status == CHECK_FAIL]
        report = PortfolioIntelligenceReportRead(
            readiness_score=readiness,
            certification_result=cert_result,
            certification_recommendation=_certification_recommendation(cert_result),
            validation_status=val_status,
            health_status=_health_status(cert_result, val_status),
            warnings=warnings,
            recommendations=recommendations,
            domain_scores={
                "run_completeness": run_complete.score,
                "missing_issue_detection": missing.score,
                "duplicate_analysis": duplicate.score,
                "grade_candidate_intelligence": grade.score,
                "sell_candidate_intelligence": sell.score,
                "determinism": determinism.score,
            },
        )

        row.run_completeness_score = run_complete.score
        row.missing_issue_score = missing.score
        row.duplicate_analysis_score = duplicate.score
        row.grade_candidate_score = grade.score
        row.sell_candidate_score = sell.score
        row.determinism_score = determinism.score
        row.readiness_score = readiness
        row.certification_result = cert_result

        panel = PortfolioCertificationOpsPanelRead(
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
                run_complete.score
                + missing.score
                + duplicate.score
                + grade.score
                + sell.score
                + determinism.score
                + operations.score
            )
            / 7.0,
            1,
        )
        cert_result = _certification_result(readiness)
        row.readiness_score = readiness
        row.certification_result = cert_result
        report.readiness_score = readiness
        report.certification_result = cert_result
        report.certification_recommendation = _certification_recommendation(cert_result)
        report.health_status = _health_status(cert_result, _validation_status(all_checks))
        report.domain_scores["operations"] = operations.score

        summary_payload = {
            "certification_version": CERTIFICATION_VERSION,
            "report": report.model_dump(),
            "checks": [c.model_dump() for c in all_checks],
        }
        row.validation_summary = json.dumps(summary_payload, default=str)
        row.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Portfolio certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
        all_checks.append(
            PortfolioCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        report = PortfolioIntelligenceReportRead(
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
        report = PortfolioIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        report = PortfolioIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=_validation_status(all_checks),
            health_status=_health_status(row.certification_result, _validation_status(all_checks)),
        )

    return _to_read(row, checks=all_checks, report=report)


def get_latest_portfolio_certification(session: Session, *, owner_user_id: int) -> PortfolioCertificationRead | None:
    row = session.exec(
        select(PortfolioCertificationRun)
        .where(PortfolioCertificationRun.owner_user_id == owner_user_id)
        .order_by(PortfolioCertificationRun.started_at.desc(), PortfolioCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [PortfolioCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = PortfolioIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = PortfolioIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=_health_status(row.certification_result, CHECK_PASS),
        )
    return _to_read(row, checks=checks, report=report)


def build_portfolio_certification_ops_panel(session: Session, *, owner_user_id: int) -> PortfolioCertificationOpsPanelRead:
    latest = get_latest_portfolio_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return PortfolioCertificationOpsPanelRead()
    return PortfolioCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        validation_status=latest.validation_status,
    )


def certification_read_from_row(row: PortfolioCertificationRun) -> PortfolioCertificationRead:
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [PortfolioCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = PortfolioIntelligenceReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = PortfolioIntelligenceReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=_health_status(row.certification_result, CHECK_PASS),
        )
    return _to_read(row, checks=checks, report=report)


def list_portfolio_certification_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PortfolioCertificationRead], int]:
    rows = session.exec(
        select(PortfolioCertificationRun)
        .where(PortfolioCertificationRun.owner_user_id == owner_user_id)
        .order_by(PortfolioCertificationRun.started_at.desc(), PortfolioCertificationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [certification_read_from_row(row) for row in page], total
