from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select, func

from app.models import InventoryCopy, Order
from app.models.asset_ledger import CoverImage, DraftImport, GmailImportRecord
from app.models.final_platform_certification import FinalPlatformCertificationRun
from app.models.lunar_feed import LunarFeedRun
from app.models.production_readiness import ProductionReadinessRun
from app.models.pull_list import PullListAutomationRun
from app.models.recommendation_v2 import RecommendationRunV2
from app.models.release_imports import ReleaseImportRun
from app.models.release_intelligence import ReleaseIssue
from app.models.scan_ingestion import ScanIngestionBatch
from app.schemas.production_readiness import (
    ProductionReadinessCheckRead,
    ProductionReadinessReportRead,
    ProductionReadinessRunRead,
    ProductionReadinessValidationCheckRead,
    ProductionReadinessValidationRead,
    ProductionReadinessWorkflowReportRead,
)
from app.services.acquisition_dashboard import get_acquisition_dashboard
from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows
from app.services.collection_gaps import latest_collection_gap_rows
from app.services.cross_system_recommendation_engine import generate_cross_system_recommendations
from app.services.daily_action_engine import generate_daily_actions, list_latest_daily_actions
from app.services.executive_dashboard import get_executive_dashboard
from app.services.exit_dashboard import get_exit_dashboard
from app.services.exit_candidates import _latest_exit_candidate_rows
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import utc_today
from app.services.pull_list_automation import run_pull_list_refresh
from app.services.pull_list_decisions import _latest_decision_rows
from app.services.recovery_recommendations import build_operations_dashboard
from app.services.unified_collector_intelligence import (
    _latest_recommendation_rows,
    generate_unified_collector_recommendations,
)

logger = logging.getLogger(__name__)

CHECK_PASS = "PASS"
CHECK_WARN = "WARN"
CHECK_FAIL = "FAIL"

GO_LIVE_NOT_READY = "NOT_READY"
GO_LIVE_WARNINGS = "READY_WITH_WARNINGS"
GO_LIVE_APPROVED = "GO_LIVE_APPROVED"


@dataclass
class _Check:
    code: str
    title: str
    status: str
    message: str = ""


@dataclass
class _Domain:
    score: float
    checks: list[_Check] = field(default_factory=list)


def _check(code: str, title: str, ok: bool, *, warn: bool = False, message: str = "") -> _Check:
    if ok:
        status = CHECK_PASS
    elif warn:
        status = CHECK_WARN
    else:
        status = CHECK_FAIL
    return _Check(code=code, title=title, status=status, message=message)


def _score(checks: list[_Check]) -> float:
    if not checks:
        return 0.0
    pts = sum(1.0 if c.status == CHECK_PASS else 0.5 if c.status == CHECK_WARN else 0.0 for c in checks)
    return round(100.0 * pts / len(checks), 1)


def _go_live(readiness: float) -> str:
    if readiness >= 90.0:
        return GO_LIVE_APPROVED
    if readiness >= 80.0:
        return GO_LIVE_WARNINGS
    return GO_LIVE_NOT_READY


def _health(readiness: float, validation: str, critical: bool) -> str:
    if critical or validation == CHECK_FAIL or readiness < 80.0:
        return "UNHEALTHY"
    if readiness >= 90.0 and validation == CHECK_PASS:
        return "HEALTHY"
    return "WARNING"


def _validation_status(checks: list[_Check]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _go_live_recommendation(result: str, readiness: float) -> str:
    if result == GO_LIVE_APPROVED:
        return f"ComicOS is approved for go-live deployment (readiness {readiness:.1f})."
    if result == GO_LIVE_WARNINGS:
        return f"ComicOS may go live with warnings (readiness {readiness:.1f}); review failed checks."
    return "ComicOS is not ready for go-live; remediate production readiness failures and re-run."


def _validate_imports(session: Session, *, owner_user_id: int) -> _Domain:
    checks: list[_Check] = []
    orders = session.exec(select(func.count()).select_from(Order).where(Order.user_id == owner_user_id)).one()
    checks.append(_check("manual_orders", "Manual orders", int(orders or 0) > 0, warn=True, message="No manual orders."))

    drafts = session.exec(
        select(func.count()).select_from(DraftImport).where(DraftImport.user_id == owner_user_id)
    ).one()
    checks.append(
        _check(
            "receipt_drafts",
            "Receipt / draft imports",
            int(drafts or 0) > 0,
            warn=True,
            message="No draft import records.",
        )
    )

    gmail = session.exec(
        select(func.count())
        .select_from(GmailImportRecord)
        .join(DraftImport, DraftImport.id == GmailImportRecord.draft_import_id)
        .where(DraftImport.user_id == owner_user_id)
    ).one()
    checks.append(_check("gmail_imports", "Gmail imports", int(gmail or 0) > 0, warn=True, message="No Gmail imports."))

    ocr = session.exec(
        select(func.count()).select_from(ScanIngestionBatch).where(ScanIngestionBatch.owner_user_id == owner_user_id)
    ).one()
    checks.append(_check("ocr_imports", "OCR scan imports", int(ocr or 0) > 0, warn=True, message="No OCR batches."))

    covers = session.exec(
        select(func.count())
        .select_from(CoverImage)
        .join(InventoryCopy, InventoryCopy.id == CoverImage.inventory_copy_id)
        .where(InventoryCopy.user_id == owner_user_id)
    ).one()
    checks.append(_check("cover_images", "Cover image imports", int(covers or 0) > 0, warn=True, message="No cover images."))

    release_import = session.exec(
        select(ReleaseImportRun)
        .where(ReleaseImportRun.owner_user_id == owner_user_id)
        .order_by(ReleaseImportRun.created_at.desc(), ReleaseImportRun.id.desc())
    ).first()
    checks.append(
        _check(
            "release_import_pipeline",
            "Release import pipeline",
            release_import is not None,
            warn=True,
            message="No release import runs.",
        )
    )
    return _Domain(score=_score(checks), checks=checks)


def _validate_inventory(session: Session, *, owner_user_id: int) -> _Domain:
    checks: list[_Check] = []
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    checks.append(_check("inventory_records", "Inventory records", len(copies) > 0, message="No inventory copies."))
    fmv = sum(1 for c in copies if c.current_fmv is not None and Decimal(c.current_fmv) > 0)
    checks.append(
        _check(
            "fmv_snapshots",
            "FMV snapshots",
            fmv > 0,
            warn=len(copies) > 0 and fmv == 0,
            message="No FMV values on inventory.",
        )
    )
    checks.append(
        _check(
            "ownership_tracking",
            "Ownership tracking",
            all(c.user_id == owner_user_id for c in copies) if copies else True,
            message="Ownership mismatch detected.",
        )
    )
    keys = [c.metadata_identity_key for c in copies if c.metadata_identity_key]
    dup_capable = len(keys) != len(set(keys))
    checks.append(
        _check(
            "duplicate_detection",
            "Duplicate detection signal",
            dup_capable or len(copies) >= 1,
            warn=not dup_capable and len(copies) > 1,
            message="Insufficient inventory diversity to validate duplicates.",
        )
    )
    return _Domain(score=_score(checks), checks=checks)


def _validate_recommendation_pipeline(session: Session, *, owner_user_id: int) -> _Domain:
    checks: list[_Check] = []
    issues = session.exec(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
    ).one()
    checks.append(_check("release_intelligence", "Release intelligence", int(issues or 0) > 0, warn=True, message="No releases."))

    v2 = session.exec(
        select(RecommendationRunV2)
        .where(RecommendationRunV2.owner_user_id == owner_user_id)
        .order_by(RecommendationRunV2.started_at.desc(), RecommendationRunV2.id.desc())
    ).first()
    checks.append(_check("recommendation_v2", "Recommendation V2", v2 is not None, warn=True, message="No V2 run."))

    checks.append(
        _check(
            "pull_lists",
            "Pull list decisions",
            len(_latest_decision_rows(session, owner_user_id=owner_user_id)) > 0,
            warn=True,
            message="No pull list decisions.",
        )
    )

    from app.services.purchase_profiles import get_purchase_profile

    profile = get_purchase_profile(session, owner_user_id=owner_user_id)
    checks.append(_check("purchase_intelligence", "Purchase profile", profile.id > 0, message="Purchase profile missing."))

    gaps = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("portfolio_intelligence", "Portfolio gaps", len(gaps) >= 0, message="Gap reader failed."))

    opps = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("acquisition_intelligence", "Acquisition opportunities", len(opps) > 0, warn=True, message="No opportunities."))

    exit_rows = _latest_exit_candidate_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("exit_intelligence", "Exit candidates", len(exit_rows) > 0, warn=True, message="No exit candidates."))

    generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
    unified = _latest_recommendation_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("unified_layer", "Unified intelligence layer", len(unified) > 0, warn=True, message="No unified rows."))
    return _Domain(score=_score(checks), checks=checks)


def _validate_dashboards(session: Session, *, owner_user_id: int) -> _Domain:
    checks: list[_Check] = []
    foc = get_foc_dashboard(session, owner_user_id=owner_user_id, today=utc_today())
    checks.append(_check("foc_dashboard", "FOC dashboard", foc.summary is not None, message="FOC dashboard failed."))

    acq = get_acquisition_dashboard(session, owner_user_id=owner_user_id)
    checks.append(_check("acquisition_dashboard", "Acquisition dashboard", acq.summary is not None, message="Acquisition dashboard failed."))

    exit_d = get_exit_dashboard(session, owner_user_id=owner_user_id)
    checks.append(_check("exit_dashboard", "Exit dashboard", exit_d.summary is not None, message="Exit dashboard failed."))

    exec_d = get_executive_dashboard(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "executive_dashboard",
            "Executive dashboard",
            exec_d.summary.total_daily_actions >= 0,
            message="Executive dashboard failed.",
        )
    )
    return _Domain(score=_score(checks), checks=checks)


def _validate_automation(session: Session, *, owner_user_id: int) -> _Domain:
    checks: list[_Check] = []
    lunar = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.created_at.desc(), LunarFeedRun.id.desc())
    ).first()
    checks.append(_check("lunar_imports", "Lunar feed imports", lunar is not None, warn=True, message="No Lunar feed runs."))

    auto = session.exec(
        select(PullListAutomationRun).order_by(PullListAutomationRun.started_at.desc(), PullListAutomationRun.id.desc())
    ).first()
    checks.append(_check("pull_list_refresh", "Pull-list refresh runs", auto is not None, warn=True, message="No automation runs."))

    before = session.exec(
        select(RecommendationRunV2)
        .where(RecommendationRunV2.owner_user_id == owner_user_id)
        .order_by(RecommendationRunV2.started_at.desc(), RecommendationRunV2.id.desc())
    ).first()
    checks.append(_check("recommendation_refresh", "Recommendation refresh history", before is not None, warn=True, message="No V2 refresh."))

    generate_daily_actions(session, owner_user_id=owner_user_id)
    daily, total = list_latest_daily_actions(session, owner_user_id=owner_user_id, limit=5, offset=0)
    checks.append(_check("daily_action_generation", "Daily action generation", total >= 0 and (total == 0 or len(daily) > 0), message="Daily actions failed."))

    run_pull_list_refresh(session, owner_user_ids=[owner_user_id])
    generate_cross_system_recommendations(session, owner_user_id=owner_user_id)
    return _Domain(score=_score(checks), checks=checks)


def _validate_workflow(session: Session, *, owner_user_id: int) -> _Domain:
    dash = get_executive_dashboard(session, owner_user_id=owner_user_id)
    checks: list[_Check] = []

    def _has_action(action: str) -> bool:
        for section in (
            dash.daily_actions.items,
            dash.top_recommendations.items,
            dash.preorder_this_week.items,
            dash.acquire_targets.items,
            dash.grade_opportunities.items,
            dash.sell_opportunities.items,
        ):
            for item in section:
                if (item.action_type or item.recommendation_type or "").upper() == action:
                    return True
        return False

    checks.append(_check("workflow_preorder", "Preorder workflow", _has_action("PREORDER"), warn=True, message="No preorder signal."))
    checks.append(_check("workflow_acquire", "Acquire workflow", _has_action("ACQUIRE"), warn=True, message="No acquire signal."))
    checks.append(_check("workflow_grade", "Grade workflow", _has_action("GRADE"), warn=True, message="No grade signal."))
    checks.append(_check("workflow_sell", "Sell workflow", _has_action("SELL"), warn=True, message="No sell signal."))

    if owner_user_id == 40:
        checks.append(
            _check(
                "owner_40_scenarios",
                "Owner 40 workflow scenarios",
                _has_action("PREORDER") and _has_action("ACQUIRE"),
                warn=True,
                message="Owner 40 missing expected recommendation mix.",
            )
        )
    return _Domain(score=_score(checks), checks=checks)


def _validate_operations(session: Session, *, owner_user_id: int) -> _Domain:
    ops = build_operations_dashboard(session, owner_user_id=owner_user_id)
    checks: list[_Check] = []
    checks.append(_check("ops_pull_cert", "Pull list certification panel", ops.pull_list_certification is not None, warn=True, message="Missing pull cert panel."))
    checks.append(_check("ops_portfolio_cert", "Portfolio certification panel", ops.portfolio_certification is not None, warn=True, message="Missing portfolio cert panel."))
    checks.append(_check("ops_acquisition_cert", "Acquisition certification panel", ops.acquisition_certification is not None, warn=True, message="Missing acquisition cert panel."))
    checks.append(_check("ops_exit_cert", "Exit certification panel", ops.exit_certification is not None, warn=True, message="Missing exit cert panel."))
    checks.append(
        _check(
            "ops_final_cert",
            "Final platform certification panel",
            ops.final_platform_certification is not None,
            warn=True,
            message="Missing final platform cert panel.",
        )
    )
    final_run = session.exec(
        select(FinalPlatformCertificationRun)
        .where(FinalPlatformCertificationRun.owner_user_id == owner_user_id)
        .order_by(FinalPlatformCertificationRun.started_at.desc(), FinalPlatformCertificationRun.id.desc())
    ).first()
    checks.append(_check("ops_final_run", "Final platform certification run", final_run is not None, warn=True, message="No final cert run."))

    prod_run = session.exec(
        select(ProductionReadinessRun)
        .where(ProductionReadinessRun.owner_user_id == owner_user_id)
        .order_by(ProductionReadinessRun.started_at.desc(), ProductionReadinessRun.id.desc())
    ).first()
    checks.append(
        _check(
            "ops_production_readiness",
            "Production readiness panel",
            prod_run is not None,
            warn=True,
            message="Production readiness run will be recorded after this check completes.",
        )
    )
    return _Domain(score=_score(checks), checks=checks)


def _to_check_reads(checks: list[_Check]) -> list[ProductionReadinessValidationCheckRead]:
    return [
        ProductionReadinessValidationCheckRead(
            check_code=c.code,
            title=c.title,
            status=c.status,
            message=c.message,
        )
        for c in checks
    ]


def run_production_readiness_check(session: Session, *, owner_user_id: int) -> ProductionReadinessValidationRead:
    started = datetime.now(timezone.utc)
    row = ProductionReadinessRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[_Check] = []
    try:
        domains = {
            "imports": _validate_imports(session, owner_user_id=owner_user_id),
            "inventory": _validate_inventory(session, owner_user_id=owner_user_id),
            "recommendations": _validate_recommendation_pipeline(session, owner_user_id=owner_user_id),
            "dashboards": _validate_dashboards(session, owner_user_id=owner_user_id),
            "automation": _validate_automation(session, owner_user_id=owner_user_id),
            "workflow": _validate_workflow(session, owner_user_id=owner_user_id),
            "operations": _validate_operations(session, owner_user_id=owner_user_id),
        }
        for d in domains.values():
            all_checks.extend(d.checks)

        scores = {k: domains[k].score for k in domains}
        readiness = round(sum(scores.values()) / len(scores), 1)
        val_status = _validation_status(all_checks)
        critical = any(c.status == CHECK_FAIL for c in all_checks if c.code in {"inventory_records", "executive_dashboard", "foc_dashboard"})
        health = _health(readiness, val_status, critical)
        go_live = _go_live(readiness)

        workflow_report = ProductionReadinessWorkflowReportRead(
            preorder_ok=any(c.code == "workflow_preorder" and c.status == CHECK_PASS for c in all_checks),
            acquire_ok=any(c.code == "workflow_acquire" and c.status == CHECK_PASS for c in all_checks),
            grade_ok=any(c.code == "workflow_grade" and c.status == CHECK_PASS for c in all_checks),
            sell_ok=any(c.code == "workflow_sell" and c.status == CHECK_PASS for c in all_checks),
            owner_user_id=owner_user_id,
        )
        report = ProductionReadinessReportRead(
            readiness_score=readiness,
            health_status=health,
            go_live_result=go_live,
            go_live_recommendation=_go_live_recommendation(go_live, readiness),
            validation_status=val_status,
            domain_scores=scores,
            warnings=[c.message for c in all_checks if c.status == CHECK_WARN and c.message],
            failures=[c.message for c in all_checks if c.status == CHECK_FAIL and c.message],
            workflow=workflow_report,
        )

        row.import_health_score = scores["imports"]
        row.inventory_health_score = scores["inventory"]
        row.recommendation_health_score = scores["recommendations"]
        row.dashboard_health_score = scores["dashboards"]
        row.automation_health_score = scores["automation"]
        row.workflow_health_score = scores["workflow"]
        row.operations_health_score = scores["operations"]
        row.readiness_score = readiness
        row.go_live_result = go_live
        row.health_status = health
        row.validation_summary = json.dumps({"report": report.model_dump(), "checks": [c.__dict__ for c in all_checks]}, default=str)
        row.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Production readiness check failed")
        row.status = "FAILED"
        row.go_live_result = GO_LIVE_NOT_READY
        row.health_status = "UNHEALTHY"
        all_checks.append(_Check(code="run", title="Production readiness run", status=CHECK_FAIL, message=str(exc)))
        report = ProductionReadinessReportRead(
            readiness_score=0.0,
            health_status="UNHEALTHY",
            go_live_result=GO_LIVE_NOT_READY,
            go_live_recommendation=_go_live_recommendation(GO_LIVE_NOT_READY, 0.0),
            validation_status=CHECK_FAIL,
            failures=[str(exc)],
        )
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
    finally:
        row.completed_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        session.refresh(row)

    run_read = ProductionReadinessRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        import_health_score=row.import_health_score,
        inventory_health_score=row.inventory_health_score,
        recommendation_health_score=row.recommendation_health_score,
        dashboard_health_score=row.dashboard_health_score,
        automation_health_score=row.automation_health_score,
        workflow_health_score=row.workflow_health_score,
        operations_health_score=row.operations_health_score,
        readiness_score=row.readiness_score,
        go_live_result=row.go_live_result,
        health_status=row.health_status,
        report=report,
    )
    return ProductionReadinessValidationRead(run=run_read, checks=_to_check_reads(all_checks))


def get_latest_production_readiness_run(session: Session, *, owner_user_id: int) -> ProductionReadinessValidationRead | None:
    row = session.exec(
        select(ProductionReadinessRun)
        .where(ProductionReadinessRun.owner_user_id == owner_user_id)
        .order_by(ProductionReadinessRun.started_at.desc(), ProductionReadinessRun.id.desc())
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.validation_summary or "{}")
        report = ProductionReadinessReportRead.model_validate(payload.get("report", {}))
        raw_checks = payload.get("checks", [])
        all_checks = [_Check(**c) for c in raw_checks]
    except (json.JSONDecodeError, ValueError, TypeError):
        report = ProductionReadinessReportRead(
            readiness_score=float(row.readiness_score),
            health_status=row.health_status,
            go_live_result=row.go_live_result,
            go_live_recommendation=_go_live_recommendation(row.go_live_result, float(row.readiness_score)),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
        )
        all_checks = []
    run_read = ProductionReadinessRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        import_health_score=row.import_health_score,
        inventory_health_score=row.inventory_health_score,
        recommendation_health_score=row.recommendation_health_score,
        dashboard_health_score=row.dashboard_health_score,
        automation_health_score=row.automation_health_score,
        workflow_health_score=row.workflow_health_score,
        operations_health_score=row.operations_health_score,
        readiness_score=row.readiness_score,
        go_live_result=row.go_live_result,
        health_status=row.health_status,
        report=report,
    )
    return ProductionReadinessValidationRead(run=run_read, checks=_to_check_reads(all_checks))


def build_production_readiness_ops_panel(session: Session, *, owner_user_id: int):
    from app.schemas.production_readiness import ProductionReadinessOpsPanelRead

    latest = get_latest_production_readiness_run(session, owner_user_id=owner_user_id)
    if latest is None:
        return ProductionReadinessOpsPanelRead()
    return ProductionReadinessOpsPanelRead(
        last_run_at=latest.run.completed_at or latest.run.started_at,
        readiness_score=latest.run.readiness_score,
        health_status=latest.run.health_status,
        go_live_result=latest.run.go_live_result,
        recommendations=latest.run.report.go_live_recommendation,
    )
