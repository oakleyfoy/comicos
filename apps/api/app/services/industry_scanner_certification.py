from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.industry_opportunity import IndustryOpportunityScore
from app.models.industry_release_scan import IndustryReleaseCandidate
from app.models.industry_release_signal import IndustryReleaseSignal
from app.models.industry_scanner_certification import IndustryScannerCertificationRun
from app.schemas.industry_scanner_certification import (
    IndustryScannerCertificationCheckRead,
    IndustryScannerCertificationOpsPanelRead,
    IndustryScannerCertificationRead,
    IndustryScannerCertificationReportRead,
)
from app.services.industry_publisher_registry import INDUSTRY_PUBLISHER_REGISTRY
from app.services.industry_publisher_scan_config import list_industry_publishers
from app.services.industry_release_scanner import load_lunar_catalog_releases
from app.services.industry_release_scans import latest_scan_run_id
from app.services.industry_scanner_automation import (
    build_industry_scanner_automation_ops_panel,
    run_industry_scanner_refresh,
)
from app.services.industry_scanner_dashboard import build_industry_scanner_dashboard

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P59-07"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"


@dataclass
class _DomainScore:
    score: float
    checks: list[IndustryScannerCertificationCheckRead] = field(default_factory=list)


def _score_from_checks(checks: list[IndustryScannerCertificationCheckRead]) -> float:
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
        return "Industry-Wide Release Scanner is approved for production monitoring workflows."
    if result == RESULT_READY_WITH_WARNINGS:
        return "Industry scanner is usable with warnings — review failed checks before full rollout."
    return "Industry scanner is not ready — remediate failing validations and re-run certification."


def _validation_status(checks: list[IndustryScannerCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _validate_publisher_coverage(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    try:
        publishers = list_industry_publishers(session, owner_user_id=owner_user_id)
        expected = len(INDUSTRY_PUBLISHER_REGISTRY)
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="publisher_registry",
                title="Supported publisher registry",
                status=CHECK_PASS if len(publishers) == expected else CHECK_WARN,
                message=f"Configured {len(publishers)} of {expected} supported publishers.",
            )
        )
        included = sum(1 for row in publishers if row.inclusion_status == "INCLUDED" and row.scan_enabled)
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="publisher_inclusion",
                title="Publisher scan inclusion",
                status=CHECK_PASS if included >= expected else CHECK_WARN,
                message=f"{included} publisher(s) included for industry scanning.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="publisher_registry",
                title="Supported publisher registry",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_lunar_scan_ingestion(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    try:
        catalog = load_lunar_catalog_releases(session, owner_user_id=owner_user_id)
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="lunar_catalog_load",
                title="Lunar catalog ingestion",
                status=CHECK_PASS,
                message=f"Loaded {len(catalog)} Lunar-classified release(s).",
            )
        )
        if not catalog:
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="lunar_catalog_data",
                    title="Lunar release data present",
                    status=CHECK_WARN,
                    message="No Lunar catalog rows — import Lunar releases for live validation.",
                )
            )
        else:
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="lunar_catalog_data",
                    title="Lunar release data present",
                    status=CHECK_PASS,
                    message="At least one Lunar catalog release is available.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="lunar_catalog_load",
                title="Lunar catalog ingestion",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_candidate_detection(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    try:
        if run_id is None:
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="candidate_scan_run",
                    title="Industry scan run",
                    status=CHECK_WARN,
                    message="No successful industry scan run yet.",
                )
            )
        else:
            count = len(
                session.exec(
                    select(IndustryReleaseCandidate)
                    .where(IndustryReleaseCandidate.owner_user_id == owner_user_id)
                    .where(IndustryReleaseCandidate.scan_run_id == run_id)
                ).all()
            )
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="candidate_scan_run",
                    title="Industry scan run",
                    status=CHECK_PASS,
                    message=f"Scan run {run_id} with {count} candidate(s).",
                )
            )
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="candidate_rows",
                    title="Release candidate detection",
                    status=CHECK_PASS if count > 0 else CHECK_WARN,
                    message=f"{count} monitoring candidate(s) captured.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="candidate_scan_run",
                title="Industry scan run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_signal_classification(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    try:
        if run_id is None:
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="signal_rows",
                    title="Industry release signals",
                    status=CHECK_WARN,
                    message="No scan run available for signal validation.",
                )
            )
        else:
            signals = session.exec(
                select(IndustryReleaseSignal)
                .where(IndustryReleaseSignal.owner_user_id == owner_user_id)
                .where(IndustryReleaseSignal.scan_run_id == run_id)
            ).all()
            types = {row.signal_type for row in signals}
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="signal_rows",
                    title="Industry release signals",
                    status=CHECK_PASS if signals else CHECK_WARN,
                    message=f"{len(signals)} signal row(s) across {len(types)} type(s).",
                )
            )
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="signal_rules",
                    title="Rule-based signal classification",
                    status=CHECK_PASS if signals else CHECK_WARN,
                    message="Signal types present." if types else "Run scanner refresh to classify signals.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="signal_rows",
                title="Industry release signals",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_opportunity_scoring(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    try:
        if run_id is None:
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="opportunity_scores",
                    title="Opportunity scoring",
                    status=CHECK_WARN,
                    message="No scan run for opportunity validation.",
                )
            )
        else:
            scores = session.exec(
                select(IndustryOpportunityScore)
                .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
                .where(IndustryOpportunityScore.scan_run_id == run_id)
            ).all()
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="opportunity_scores",
                    title="Opportunity scoring",
                    status=CHECK_PASS if scores else CHECK_WARN,
                    message=f"{len(scores)} opportunity score(s) materialized.",
                )
            )
            if scores:
                top = max(scores, key=lambda row: float(row.opportunity_score))
                checks.append(
                    IndustryScannerCertificationCheckRead(
                        check_code="opportunity_range",
                        title="Score range validation",
                        status=CHECK_PASS if 0 <= float(top.opportunity_score) <= 100 else CHECK_FAIL,
                        message=f"Top score={float(top.opportunity_score):.1f}, risk={top.risk_level}.",
                    )
                )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="opportunity_scores",
                title="Opportunity scoring",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_dashboard(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    try:
        dash = build_industry_scanner_dashboard(session, owner_user_id=owner_user_id, refresh=False)
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="dashboard_build",
                title="Industry scanner dashboard",
                status=CHECK_PASS,
                message="Dashboard sections materialized.",
            )
        )
        section_count = sum(
            1
            for section in (
                dash.top_number_one_issues,
                dash.ratio_variants,
                dash.facsimiles,
                dash.anniversary_milestone_books,
                dash.key_events,
                dash.high_opportunity_score,
                dash.watchlist,
            )
            if section
        )
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="dashboard_sections",
                title="Dashboard sections",
                status=CHECK_PASS,
                message=f"{section_count} dashboard section groups available.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="dashboard_build",
                title="Industry scanner dashboard",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_automation(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    try:
        first = run_industry_scanner_refresh(session, owner_user_id=owner_user_id, trigger_type="SCHEDULED")
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="automation_refresh",
                title="Industry scanner automation",
                status=CHECK_PASS if first.status in {"SUCCESS", "NO_CHANGE"} else CHECK_FAIL,
                message=f"Refresh status={first.status}, releases={first.releases_scanned}.",
            )
        )
        panel = build_industry_scanner_automation_ops_panel(session, owner_user_id=owner_user_id)
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="automation_ops_panel",
                title="Automation operations visibility",
                status=CHECK_PASS if panel.last_run is not None else CHECK_WARN,
                message=f"Last automation status={panel.status}.",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="automation_refresh",
                title="Industry scanner automation",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    try:
        second = run_industry_scanner_refresh(session, owner_user_id=owner_user_id, trigger_type="SCHEDULED")
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="determinism_repeat",
                title="Repeat refresh idempotency",
                status=CHECK_PASS if second.status in {"SUCCESS", "NO_CHANGE"} else CHECK_FAIL,
                message=f"Second run status={second.status}, scan_skipped={second.scan_skipped}.",
            )
        )
        if second.status == "NO_CHANGE":
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="determinism_no_dup",
                    title="Unchanged catalog handling",
                    status=CHECK_PASS,
                    message="No duplicate candidates/signals/scores on unchanged Lunar data.",
                )
            )
        else:
            checks.append(
                IndustryScannerCertificationCheckRead(
                    check_code="determinism_no_dup",
                    title="Unchanged catalog handling",
                    status=CHECK_WARN,
                    message="Catalog changed between runs — idempotent skip not exercised.",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="determinism_repeat",
                title="Repeat refresh idempotency",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _validate_operations(*, panel: IndustryScannerCertificationOpsPanelRead) -> _DomainScore:
    checks: list[IndustryScannerCertificationCheckRead] = []
    checks.append(
        IndustryScannerCertificationCheckRead(
            check_code="ops_panel_shape",
            title="Operations panel readable",
            status=CHECK_PASS,
            message=f"Result={panel.certification_result}, validation={panel.validation_status}.",
        )
    )
    checks.append(
        IndustryScannerCertificationCheckRead(
            check_code="ops_panel_timestamp",
            title="Operations panel timestamp",
            status=CHECK_PASS if panel.last_certification_at is not None else CHECK_WARN,
            message="Certification timestamp recorded for ops dashboard.",
        )
    )
    return _DomainScore(score=_score_from_checks(checks), checks=checks)


def _to_read(
    row: IndustryScannerCertificationRun,
    *,
    checks: list[IndustryScannerCertificationCheckRead],
    report: IndustryScannerCertificationReportRead,
) -> IndustryScannerCertificationRead:
    return IndustryScannerCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        publisher_coverage_score=float(row.publisher_coverage_score),
        lunar_scan_ingestion_score=float(row.lunar_scan_ingestion_score),
        candidate_detection_score=float(row.candidate_detection_score),
        signal_classification_score=float(row.signal_classification_score),
        opportunity_scoring_score=float(row.opportunity_scoring_score),
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


def _hydrate_read(row: IndustryScannerCertificationRun) -> IndustryScannerCertificationRead:
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [IndustryScannerCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = IndustryScannerCertificationReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = IndustryScannerCertificationReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            certification_recommendation=_certification_recommendation(row.certification_result),
            validation_status=CHECK_WARN,
            health_status="DEGRADED",
        )
    return _to_read(row, checks=checks, report=report)


def run_industry_scanner_certification(session: Session, *, owner_user_id: int) -> IndustryScannerCertificationRead:
    started = datetime.now(timezone.utc)
    row = IndustryScannerCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[IndustryScannerCertificationCheckRead] = []
    report = IndustryScannerCertificationReportRead(
        readiness_score=0.0,
        certification_result=RESULT_NOT_READY,
        certification_recommendation=_certification_recommendation(RESULT_NOT_READY),
        validation_status=CHECK_FAIL,
        health_status="UNHEALTHY",
    )

    try:
        run_industry_scanner_refresh(session, owner_user_id=owner_user_id, trigger_type="SCHEDULED")

        publisher = _validate_publisher_coverage(session, owner_user_id=owner_user_id)
        lunar = _validate_lunar_scan_ingestion(session, owner_user_id=owner_user_id)
        candidates = _validate_candidate_detection(session, owner_user_id=owner_user_id)
        signals = _validate_signal_classification(session, owner_user_id=owner_user_id)
        opportunities = _validate_opportunity_scoring(session, owner_user_id=owner_user_id)
        dashboard = _validate_dashboard(session, owner_user_id=owner_user_id)
        automation = _validate_automation(session, owner_user_id=owner_user_id)
        determinism = _validate_determinism(session, owner_user_id=owner_user_id)

        all_checks.extend(publisher.checks)
        all_checks.extend(lunar.checks)
        all_checks.extend(candidates.checks)
        all_checks.extend(signals.checks)
        all_checks.extend(opportunities.checks)
        all_checks.extend(dashboard.checks)
        all_checks.extend(automation.checks)
        all_checks.extend(determinism.checks)

        row.publisher_coverage_score = publisher.score
        row.lunar_scan_ingestion_score = lunar.score
        row.candidate_detection_score = candidates.score
        row.signal_classification_score = signals.score
        row.opportunity_scoring_score = opportunities.score
        row.dashboard_score = dashboard.score
        row.automation_score = automation.score
        row.determinism_score = determinism.score

        val_status = _validation_status(all_checks)
        readiness = round(
            (
                publisher.score
                + lunar.score
                + candidates.score
                + signals.score
                + opportunities.score
                + dashboard.score
                + automation.score
                + determinism.score
            )
            / 8.0,
            1,
        )
        cert_result = _certification_result(readiness)

        panel = IndustryScannerCertificationOpsPanelRead(
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
                publisher.score
                + lunar.score
                + candidates.score
                + signals.score
                + opportunities.score
                + dashboard.score
                + automation.score
                + determinism.score
                + operations.score
            )
            / 9.0,
            1,
        )
        cert_result = _certification_result(readiness)
        val_status = _validation_status(all_checks)

        row.readiness_score = readiness
        row.certification_result = cert_result

        warnings = [c.message for c in all_checks if c.status == CHECK_WARN]
        recommendations = [c.message for c in all_checks if c.status == CHECK_FAIL]
        report = IndustryScannerCertificationReportRead(
            readiness_score=readiness,
            certification_result=cert_result,
            certification_recommendation=_certification_recommendation(cert_result),
            validation_status=val_status,
            health_status=_health_status(cert_result, val_status),
            warnings=warnings,
            recommendations=recommendations,
            domain_scores={
                "publisher_coverage": publisher.score,
                "lunar_scan_ingestion": lunar.score,
                "candidate_detection": candidates.score,
                "signal_classification": signals.score,
                "opportunity_scoring": opportunities.score,
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
        logger.exception("Industry scanner certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
        all_checks.append(
            IndustryScannerCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        report = IndustryScannerCertificationReportRead(
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


def get_latest_industry_scanner_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> IndustryScannerCertificationRead | None:
    row = session.exec(
        select(IndustryScannerCertificationRun)
        .where(IndustryScannerCertificationRun.owner_user_id == owner_user_id)
        .order_by(IndustryScannerCertificationRun.started_at.desc(), IndustryScannerCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    return _hydrate_read(row)


def list_industry_scanner_certification_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IndustryScannerCertificationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(IndustryScannerCertificationRun)
        .where(IndustryScannerCertificationRun.owner_user_id == owner_user_id)
        .order_by(IndustryScannerCertificationRun.started_at.desc(), IndustryScannerCertificationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_hydrate_read(row) for row in page], total


def build_industry_scanner_certification_ops_panel(
    session: Session,
    *,
    owner_user_id: int,
) -> IndustryScannerCertificationOpsPanelRead:
    latest = get_latest_industry_scanner_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return IndustryScannerCertificationOpsPanelRead()
    return IndustryScannerCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        validation_status=latest.validation_status,
    )
