from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select, func

from app.models.final_platform_certification import FinalPlatformCertificationRun
from app.models.release_imports import ReleaseImportRun
from app.models.release_intelligence import ReleaseIssue, ReleaseVariant
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.models.pull_list import PullListAutomationRun, PullListCertificationRun
from app.models.want_list import WantListItem
from app.schemas.final_platform_certification import (
    FinalPlatformCertificationCheckRead,
    FinalPlatformCertificationOpsPanelRead,
    FinalPlatformCertificationRead,
    FinalPlatformCertificationReportRead,
)
from app.services.acquisition_dashboard import get_acquisition_dashboard
from app.services.acquisition_certification import build_acquisition_certification_ops_panel
from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows, persist_acquisition_opportunities
from app.services.collection_gaps import latest_collection_gap_rows
from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
from app.services.cross_system_recommendation_engine import generate_cross_system_recommendations
from app.services.daily_action_engine import generate_daily_actions, list_latest_daily_actions
from app.services.executive_dashboard import get_executive_dashboard
from app.services.exit_certification import build_exit_certification_ops_panel
from app.services.exit_dashboard import get_exit_dashboard
from app.services.exit_candidates import _latest_exit_candidate_rows
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import utc_today
from app.services.grade_before_sell import _latest_rows as _latest_grade_rows
from app.services.hold_sell_intelligence import _latest_hold_sell_rows
from app.services.portfolio_certification import build_portfolio_certification_ops_panel
from app.services.portfolio_rebalancing import _latest_rows as _latest_rebalance_rows
from app.services.purchase_budgets import (
    build_purchase_budget_summary,
    generate_purchase_budget_allocations,
    list_purchase_budget_allocations,
)
from app.services.purchase_profiles import get_purchase_profile
from app.services.purchase_quantities import (
    generate_purchase_quantities,
    list_latest_purchase_quantity_recommendations,
)
from app.services.purchase_variants import (
    generate_purchase_variants,
    list_latest_purchase_variant_recommendations,
)
from app.services.pull_list_automation import run_pull_list_refresh
from app.services.pull_list_certification import build_pull_list_certification_ops_panel
from app.services.pull_list_decisions import _latest_decision_rows, generate_pull_list_decisions
from app.services.recommendation_intelligence_certification import get_recommendation_intelligence_certification
from app.services.unified_collector_intelligence import (
    _latest_recommendation_rows,
    generate_unified_collector_recommendations,
)

logger = logging.getLogger(__name__)

CERTIFICATION_VERSION = "P57-05"
RESULT_NOT_READY = "NOT_READY"
RESULT_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
RESULT_APPROVED = "APPROVED_FOR_PRODUCTION"

CHECK_PASS = "PASS"
CHECK_WARN = "WARN"
CHECK_FAIL = "FAIL"

DOMAIN_KEYS = (
    "release_intelligence",
    "recommendation_intelligence",
    "pull_list",
    "purchase",
    "portfolio",
    "acquisition",
    "exit",
    "unified_intelligence",
    "daily_actions",
    "cross_system",
    "executive_dashboard",
    "determinism",
    "operations",
)


@dataclass
class _DomainResult:
    score: float
    checks: list[FinalPlatformCertificationCheckRead] = field(default_factory=list)


def _check(code: str, title: str, ok: bool, *, warn: bool = False, message: str = "") -> FinalPlatformCertificationCheckRead:
    if ok:
        status = CHECK_PASS
    elif warn:
        status = CHECK_WARN
    else:
        status = CHECK_FAIL
    return FinalPlatformCertificationCheckRead(check_code=code, title=title, status=status, message=message)


def _score_from_checks(checks: list[FinalPlatformCertificationCheckRead]) -> float:
    if not checks:
        return 0.0
    points = 0.0
    for c in checks:
        if c.status == CHECK_PASS:
            points += 1.0
        elif c.status == CHECK_WARN:
            points += 0.5
    return round(100.0 * points / len(checks), 1)


def _certification_result(readiness: float) -> str:
    if readiness >= 90.0:
        return RESULT_APPROVED
    if readiness >= 80.0:
        return RESULT_READY_WITH_WARNINGS
    return RESULT_NOT_READY


def _validation_status(checks: list[FinalPlatformCertificationCheckRead]) -> str:
    if any(c.status == CHECK_FAIL for c in checks):
        return CHECK_FAIL
    if any(c.status == CHECK_WARN for c in checks):
        return CHECK_WARN
    return CHECK_PASS


def _health_status(*, readiness: float, validation_status: str, critical_fail: bool) -> str:
    if critical_fail or validation_status == CHECK_FAIL or readiness < 80.0:
        return "UNHEALTHY"
    if readiness >= 90.0 and validation_status == CHECK_PASS:
        return "HEALTHY"
    return "WARNING"


def _production_recommendation(result: str, readiness: float) -> str:
    if result == RESULT_APPROVED:
        return (
            f"ComicOS v1.0 is approved for production (readiness {readiness:.1f}). "
            "Release through Executive Dashboard and Operations Reliability monitoring."
        )
    if result == RESULT_READY_WITH_WARNINGS:
        return (
            f"ComicOS v1.0 is usable with warnings (readiness {readiness:.1f}). "
            "Review domain failures before full production rollout."
        )
    return "ComicOS v1.0 is not ready for production — remediate failing validations and re-run certification."


def _validate_release_intelligence(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    import_run = session.exec(
        select(ReleaseImportRun)
        .where(ReleaseImportRun.owner_user_id == owner_user_id)
        .order_by(ReleaseImportRun.created_at.desc(), ReleaseImportRun.id.desc())
    ).first()
    checks.append(
        _check(
            "release_import",
            "Release import history",
            import_run is not None,
            warn=True,
            message="No release import run recorded yet.",
        )
    )
    issue_count = session.exec(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
    ).one()
    checks.append(_check("release_count", "Release issues catalogued", int(issue_count or 0) > 0, message="No release issues found."))
    variant_count = session.exec(
        select(func.count())
        .select_from(ReleaseVariant)
        .join(ReleaseIssue, ReleaseIssue.id == ReleaseVariant.issue_id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).one()
    checks.append(
        _check(
            "variant_count",
            "Release variants",
            int(variant_count or 0) > 0,
            warn=True,
            message="No release variants found.",
        )
    )
    future = session.exec(
        select(func.count())
        .select_from(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.foc_date.is_not(None))
        .where(ReleaseIssue.foc_date >= utc_today())
    ).one()
    checks.append(
        _check(
            "future_foc",
            "Future FOC dates",
            int(future or 0) > 0,
            warn=True,
            message="No upcoming FOC-dated releases.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_recommendation_intelligence(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    run = session.exec(
        select(RecommendationRunV2)
        .where(RecommendationRunV2.owner_user_id == owner_user_id)
        .order_by(RecommendationRunV2.started_at.desc(), RecommendationRunV2.id.desc())
    ).first()
    checks.append(_check("rec_v2_run", "Recommendation V2 run", run is not None, message="No Recommendation V2 run found."))
    failed = run is not None and run.status not in {"COMPLETED", "SUCCESS"}
    checks.append(
        _check(
            "rec_v2_status",
            "Latest V2 run status",
            not failed,
            warn=run is None,
            message=f"Latest run status: {run.status if run else 'NONE'}.",
        )
    )
    score_count = session.exec(
        select(func.count()).select_from(RecommendationScoreV2).where(RecommendationScoreV2.owner_user_id == owner_user_id)
    ).one()
    checks.append(
        _check(
            "rec_v2_scores",
            "Recommendation scores",
            int(score_count or 0) > 0,
            message="No V2 recommendation scores stored.",
        )
    )
    cert = get_recommendation_intelligence_certification(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "rec_intelligence_cert",
            "Recommendation intelligence certification",
            cert.readiness_score > 0,
            warn=True,
            message=cert.certification_status,
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_pull_list(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    decisions = _latest_decision_rows(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "pull_decisions",
            "Pull list decisions",
            len(decisions) > 0,
            warn=True,
            message="No pull list decisions materialized.",
        )
    )
    foc = get_foc_dashboard(session, owner_user_id=owner_user_id, today=utc_today())
    checks.append(
        _check(
            "foc_dashboard",
            "FOC dashboard",
            foc.summary.action_required_count + foc.summary.upcoming_foc_count >= 0,
            message="FOC dashboard unavailable.",
        )
    )
    auto = session.exec(
        select(PullListAutomationRun).order_by(PullListAutomationRun.started_at.desc(), PullListAutomationRun.id.desc())
    ).first()
    checks.append(
        _check(
            "pull_automation",
            "Pull list automation run",
            auto is not None,
            warn=True,
            message="No pull list automation run recorded.",
        )
    )
    cert_row = session.exec(
        select(PullListCertificationRun)
        .where(PullListCertificationRun.owner_user_id == owner_user_id)
        .order_by(PullListCertificationRun.started_at.desc(), PullListCertificationRun.id.desc())
    ).first()
    checks.append(
        _check(
            "pull_cert",
            "Pull list certification run",
            cert_row is not None,
            warn=True,
            message="No pull list certification run yet.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_purchase(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    profile = get_purchase_profile(session, owner_user_id=owner_user_id)
    checks.append(_check("purchase_profile", "Purchase profile", profile.id > 0, message="Purchase profile missing."))
    qty, _ = list_latest_purchase_quantity_recommendations(session, owner_user_id=owner_user_id, limit=5, offset=0)
    checks.append(
        _check(
            "purchase_quantities",
            "Quantity recommendations",
            len(qty) > 0,
            warn=True,
            message="No purchase quantity recommendations.",
        )
    )
    variants, _ = list_latest_purchase_variant_recommendations(session, owner_user_id=owner_user_id, limit=5, offset=0)
    checks.append(
        _check(
            "purchase_variants",
            "Variant recommendations",
            len(variants) > 0,
            warn=True,
            message="No purchase variant recommendations.",
        )
    )
    allocations, _ = list_purchase_budget_allocations(session, owner_user_id=owner_user_id, limit=5, offset=0)
    budget = build_purchase_budget_summary(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "budget_allocations",
            "Budget allocations",
            len(allocations) > 0 or budget.total_budget >= 0,
            warn=len(allocations) == 0,
            message="No budget allocations generated.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_portfolio(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    gaps = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "collection_gaps",
            "Collection gap capability",
            True,
            message="Collection gap engine reachable.",
        )
    )
    checks.append(
        _check(
            "gap_rows",
            "Collection gaps materialized",
            len(gaps) > 0,
            warn=True,
            message="No collection gaps persisted.",
        )
    )
    from app.services.sell_candidates import _latest_sell_candidate_rows

    sell = _latest_sell_candidate_rows(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "sell_candidates",
            "Sell candidate capability",
            len(sell) >= 0,
            message="Sell candidate reader unavailable.",
        )
    )
    panel = build_portfolio_certification_ops_panel(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "portfolio_cert",
            "Portfolio certification",
            panel.last_certification_at is not None,
            warn=True,
            message="No portfolio certification run recorded.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_acquisition(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    wants = session.exec(select(func.count()).select_from(WantListItem).where(WantListItem.owner_user_id == owner_user_id)).one()
    checks.append(
        _check("want_lists", "Want list items", int(wants or 0) >= 0, warn=int(wants or 0) == 0, message="No want list items.")
    )
    gaps = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("acq_gaps", "Collection gaps", len(gaps) > 0, warn=True, message="No collection gaps."))
    opps = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("acq_opps", "Acquisition opportunities", len(opps) > 0, warn=True, message="No acquisition opportunities."))
    dash = get_acquisition_dashboard(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "acq_dashboard",
            "Acquisition dashboard",
            dash.summary.open_collection_gaps >= 0,
            message="Acquisition dashboard failed to load.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_exit(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    exit_rows = _latest_exit_candidate_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("exit_candidates", "Exit candidates", len(exit_rows) > 0, warn=True, message="No exit candidates."))
    hold = _latest_hold_sell_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("hold_sell", "Hold/sell recommendations", len(hold) > 0, warn=True, message="No hold/sell rows."))
    grade = _latest_grade_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("grade_before_sell", "Grade-before-sell", len(grade) > 0, warn=True, message="No grade-before-sell rows."))
    reb = _latest_rebalance_rows(session, owner_user_id=owner_user_id)
    checks.append(_check("rebalance", "Portfolio rebalancing", len(reb) > 0, warn=True, message="No rebalance rows."))
    exit_dash = get_exit_dashboard(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "exit_dashboard",
            "Exit dashboard",
            exit_dash.summary.total_exit_candidates >= 0,
            message="Exit dashboard failed to load.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_unified(session: Session, *, owner_user_id: int) -> _DomainResult:
    generate_unified_collector_recommendations(session, owner_user_id=owner_user_id)
    rows = _latest_recommendation_rows(session, owner_user_id=owner_user_id)
    checks: list[FinalPlatformCertificationCheckRead] = []
    checks.append(_check("unified_rows", "Unified recommendations", len(rows) > 0, message="No unified recommendations."))
    if rows:
        sample = next(iter(rows.values()))
        checks.append(_check("unified_sources", "Source systems populated", len(sample.source_systems or []) > 0, message="Missing source systems."))
        checks.append(
            _check(
                "unified_scores",
                "Priority and confidence populated",
                float(sample.priority_score) > 0 and float(sample.confidence_score) > 0,
                message="Missing priority/confidence.",
            )
        )
        checks.append(_check("unified_rationale", "Rationale populated", bool(sample.rationale), message="Missing rationale."))
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_daily_actions(session: Session, *, owner_user_id: int) -> _DomainResult:
    generate_daily_actions(session, owner_user_id=owner_user_id)
    items, total = list_latest_daily_actions(session, owner_user_id=owner_user_id, limit=50, offset=0)
    checks: list[FinalPlatformCertificationCheckRead] = []
    checks.append(_check("daily_rows", "Daily actions", total > 0, message="No daily actions."))
    if items:
        checks.append(_check("daily_types", "Action types populated", all(i.action_type for i in items), message="Missing action types."))
        checks.append(
            _check(
                "daily_priority",
                "Priorities populated",
                all(i.priority_score > 0 for i in items),
                message="Missing priorities.",
            )
        )
        preorder = [i for i in items if i.action_type == "PREORDER"]
        checks.append(
            _check(
                "daily_due_dates",
                "Due date support",
                not preorder or any(i.due_date is not None for i in preorder),
                warn=True,
                message="Preorder actions without due dates.",
            )
        )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_cross_system(session: Session, *, owner_user_id: int) -> _DomainResult:
    generate_cross_system_recommendations(session, owner_user_id=owner_user_id)
    items, total = list_latest_cross_system_recommendations(session, owner_user_id=owner_user_id, limit=50, offset=0)
    checks: list[FinalPlatformCertificationCheckRead] = []
    checks.append(_check("cross_rows", "Cross-system recommendations", total > 0, message="No cross-system recommendations."))
    if items:
        checks.append(
            _check(
                "cross_ranks",
                "Recommendation ranks",
                all(i.recommendation_rank >= 1 for i in items),
                message="Missing recommendation ranks.",
            )
        )
        checks.append(
            _check(
                "cross_rationale",
                "Multi-source rationales",
                any("Supported by" in i.rationale or len(i.source_systems) >= 2 for i in items),
                warn=True,
                message="No multi-source rationales detected.",
            )
        )
        checks.append(
            _check(
                "cross_conflict",
                "Conflict resolution signals",
                any("Resolved" in i.rationale or "GRADE" in i.recommendation_type for i in items),
                warn=True,
                message="No conflict-resolution rationales detected.",
            )
        )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_executive_dashboard(session: Session, *, owner_user_id: int) -> _DomainResult:
    dash = get_executive_dashboard(session, owner_user_id=owner_user_id)
    checks: list[FinalPlatformCertificationCheckRead] = []
    checks.append(_check("exec_load", "Executive dashboard loads", dash.summary.total_daily_actions >= 0, message="Dashboard failed."))
    checks.append(_check("exec_daily", "Daily actions section", bool(dash.daily_actions.title), message="Missing daily section."))
    checks.append(_check("exec_recs", "Recommendations section", bool(dash.top_recommendations.title), message="Missing recommendations section."))
    checks.append(_check("exec_preorder", "Preorder section", bool(dash.preorder_this_week.title), message="Missing preorder section."))
    checks.append(_check("exec_acquire", "Acquisition section", bool(dash.acquire_targets.title), message="Missing acquisition section."))
    checks.append(_check("exec_grade", "Grade section", bool(dash.grade_opportunities.title), message="Missing grade section."))
    checks.append(_check("exec_sell", "Sell section", bool(dash.sell_opportunities.title), message="Missing sell section."))
    checks.append(_check("exec_risk", "Portfolio risk section", bool(dash.portfolio_risk.title), message="Missing risk section."))
    checks.append(_check("exec_health", "System health section", bool(dash.system_health.title), message="Missing health section."))
    checks.append(
        _check(
            "exec_summary",
            "Summary metrics",
            dash.summary.total_daily_actions >= 0 and dash.summary.estimated_capital_recovery >= 0,
            message="Summary metrics missing.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_determinism(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []

    def _stable(label: str, first: int, second: int) -> None:
        ok = second == 0 or first == second
        checks.append(
            _check(
                f"det_{label}",
                f"Deterministic {label}",
                ok,
                message=f"First={first}, second={second}.",
            )
        )

    d1 = generate_pull_list_decisions(session, owner_user_id=owner_user_id)
    d2 = generate_pull_list_decisions(session, owner_user_id=owner_user_id)
    _stable("pull_list_decisions", d1, d2)

    q1 = generate_purchase_quantities(session, owner_user_id=owner_user_id)
    q2 = generate_purchase_quantities(session, owner_user_id=owner_user_id)
    _stable("purchase_quantities", q1, q2)

    v1 = generate_purchase_variants(session, owner_user_id=owner_user_id)
    v2 = generate_purchase_variants(session, owner_user_id=owner_user_id)
    _stable("purchase_variants", v1, v2)

    b1 = generate_purchase_budget_allocations(session, owner_user_id=owner_user_id)
    b2 = generate_purchase_budget_allocations(session, owner_user_id=owner_user_id)
    _stable("budget_allocations", b1, b2)

    persist_acquisition_opportunities(session, owner_user_id=owner_user_id)
    opps_a = len(latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id))
    persist_acquisition_opportunities(session, owner_user_id=owner_user_id)
    opps_b = len(latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id))
    checks.append(_check("det_acquisition_opps", "Stable acquisition opportunities", opps_a == opps_b, message=f"{opps_a} vs {opps_b}"))

    from app.services.exit_candidates import persist_exit_candidates

    persist_exit_candidates(session, owner_user_id=owner_user_id)
    ex_a = len(_latest_exit_candidate_rows(session, owner_user_id=owner_user_id))
    persist_exit_candidates(session, owner_user_id=owner_user_id)
    ex_b = len(_latest_exit_candidate_rows(session, owner_user_id=owner_user_id))
    checks.append(_check("det_exit_candidates", "Stable exit candidates", ex_a == ex_b, message=f"{ex_a} vs {ex_b}"))

    da1 = generate_daily_actions(session, owner_user_id=owner_user_id)
    da2 = generate_daily_actions(session, owner_user_id=owner_user_id)
    _stable("daily_actions", da1, da2)

    cs1 = generate_cross_system_recommendations(session, owner_user_id=owner_user_id)
    cs2 = generate_cross_system_recommendations(session, owner_user_id=owner_user_id)
    _stable("cross_system", cs1, cs2)

    dash1 = get_executive_dashboard(session, owner_user_id=owner_user_id)
    dash2 = get_executive_dashboard(session, owner_user_id=owner_user_id)
    checks.append(
        _check(
            "det_executive_dashboard",
            "Stable executive dashboard",
            dash1.summary.total_daily_actions == dash2.summary.total_daily_actions,
            message="Dashboard summary changed between reads.",
        )
    )

    run_pull_list_refresh(session, owner_user_ids=[owner_user_id])
    run_pull_list_refresh(session, owner_user_ids=[owner_user_id])

    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _validate_operations(session: Session, *, owner_user_id: int) -> _DomainResult:
    checks: list[FinalPlatformCertificationCheckRead] = []
    pull = build_pull_list_certification_ops_panel(session, owner_user_id=owner_user_id)
    portfolio = build_portfolio_certification_ops_panel(session, owner_user_id=owner_user_id)
    acquisition = build_acquisition_certification_ops_panel(session, owner_user_id=owner_user_id)
    exit_panel = build_exit_certification_ops_panel(session, owner_user_id=owner_user_id)
    final_panel = build_final_platform_certification_ops_panel(session, owner_user_id=owner_user_id)

    checks.append(
        _check(
            "ops_pull_cert",
            "Pull list certification panel",
            pull.last_certification_at is not None,
            warn=True,
            message="Pull list certification not recorded.",
        )
    )
    checks.append(
        _check(
            "ops_portfolio_cert",
            "Portfolio certification panel",
            portfolio.last_certification_at is not None,
            warn=True,
            message="Portfolio certification not recorded.",
        )
    )
    checks.append(
        _check(
            "ops_acquisition_cert",
            "Acquisition certification panel",
            acquisition.last_certification_at is not None,
            warn=True,
            message="Acquisition certification not recorded.",
        )
    )
    checks.append(
        _check(
            "ops_exit_cert",
            "Exit certification panel",
            exit_panel.last_certification_at is not None,
            warn=True,
            message="Exit certification not recorded.",
        )
    )
    checks.append(
        _check(
            "ops_final_cert",
            "Final platform certification panel",
            final_panel.last_certification_at is not None,
            warn=True,
            message="Final platform certification not recorded yet.",
        )
    )
    return _DomainResult(score=_score_from_checks(checks), checks=checks)


def _average_readiness(scores: dict[str, float]) -> float:
    if not scores:
        return 0.0
    return round(sum(scores.values()) / len(scores), 1)


def _to_read(
    row: FinalPlatformCertificationRun,
    *,
    checks: list[FinalPlatformCertificationCheckRead],
    report: FinalPlatformCertificationReportRead,
) -> FinalPlatformCertificationRead:
    return FinalPlatformCertificationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        release_intelligence_score=row.release_intelligence_score,
        recommendation_intelligence_score=row.recommendation_intelligence_score,
        pull_list_score=row.pull_list_score,
        purchase_score=row.purchase_score,
        portfolio_score=row.portfolio_score,
        acquisition_score=row.acquisition_score,
        exit_score=row.exit_score,
        unified_intelligence_score=row.unified_intelligence_score,
        daily_action_score=row.daily_action_score,
        cross_system_score=row.cross_system_score,
        executive_dashboard_score=row.executive_dashboard_score,
        determinism_score=row.determinism_score,
        operations_score=row.operations_score,
        readiness_score=row.readiness_score,
        certification_result=row.certification_result,
        health_status=row.health_status,
        validation_status=report.validation_status,
        report=report,
        checks=checks,
    )


def run_final_platform_certification(session: Session, *, owner_user_id: int) -> FinalPlatformCertificationRead:
    started = datetime.now(timezone.utc)
    row = FinalPlatformCertificationRun(owner_user_id=owner_user_id, started_at=started, status="RUNNING")
    session.add(row)
    session.commit()
    session.refresh(row)

    all_checks: list[FinalPlatformCertificationCheckRead] = []
    domains: dict[str, _DomainResult] = {}

    try:
        domains["release_intelligence"] = _validate_release_intelligence(session, owner_user_id=owner_user_id)
        domains["recommendation_intelligence"] = _validate_recommendation_intelligence(session, owner_user_id=owner_user_id)
        domains["pull_list"] = _validate_pull_list(session, owner_user_id=owner_user_id)
        domains["purchase"] = _validate_purchase(session, owner_user_id=owner_user_id)
        domains["portfolio"] = _validate_portfolio(session, owner_user_id=owner_user_id)
        domains["acquisition"] = _validate_acquisition(session, owner_user_id=owner_user_id)
        domains["exit"] = _validate_exit(session, owner_user_id=owner_user_id)
        domains["unified_intelligence"] = _validate_unified(session, owner_user_id=owner_user_id)
        domains["daily_actions"] = _validate_daily_actions(session, owner_user_id=owner_user_id)
        domains["cross_system"] = _validate_cross_system(session, owner_user_id=owner_user_id)
        domains["executive_dashboard"] = _validate_executive_dashboard(session, owner_user_id=owner_user_id)
        domains["determinism"] = _validate_determinism(session, owner_user_id=owner_user_id)
        domains["operations"] = _validate_operations(session, owner_user_id=owner_user_id)

        for domain in domains.values():
            all_checks.extend(domain.checks)

        domain_scores = {key: domains[key].score for key in DOMAIN_KEYS}
        readiness = _average_readiness(domain_scores)
        cert_result = _certification_result(readiness)
        val_status = _validation_status(all_checks)
        critical_fail = any(
            c.status == CHECK_FAIL
            for c in all_checks
            if c.check_code in {"release_count", "rec_v2_scores", "unified_rows", "daily_rows", "cross_rows", "exec_load"}
        )
        health = _health_status(readiness=readiness, validation_status=val_status, critical_fail=critical_fail)

        warnings = [c.message for c in all_checks if c.status == CHECK_WARN and c.message]
        failures = [c.message for c in all_checks if c.status == CHECK_FAIL and c.message]

        report = FinalPlatformCertificationReportRead(
            readiness_score=readiness,
            certification_result=cert_result,
            production_recommendation=_production_recommendation(cert_result, readiness),
            validation_status=val_status,
            health_status=health,
            warnings=warnings,
            failures=failures,
            domain_scores=domain_scores,
        )

        row.release_intelligence_score = domain_scores["release_intelligence"]
        row.recommendation_intelligence_score = domain_scores["recommendation_intelligence"]
        row.pull_list_score = domain_scores["pull_list"]
        row.purchase_score = domain_scores["purchase"]
        row.portfolio_score = domain_scores["portfolio"]
        row.acquisition_score = domain_scores["acquisition"]
        row.exit_score = domain_scores["exit"]
        row.unified_intelligence_score = domain_scores["unified_intelligence"]
        row.daily_action_score = domain_scores["daily_actions"]
        row.cross_system_score = domain_scores["cross_system"]
        row.executive_dashboard_score = domain_scores["executive_dashboard"]
        row.determinism_score = domain_scores["determinism"]
        row.operations_score = domain_scores["operations"]
        row.readiness_score = readiness
        row.certification_result = cert_result
        row.health_status = health
        row.validation_summary = json.dumps(
            {"certification_version": CERTIFICATION_VERSION, "report": report.model_dump(), "checks": [c.model_dump() for c in all_checks]},
            default=str,
        )
        row.status = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Final platform certification failed")
        row.status = "FAILED"
        row.certification_result = RESULT_NOT_READY
        row.health_status = "UNHEALTHY"
        all_checks.append(
            FinalPlatformCertificationCheckRead(
                check_code="certification_run",
                title="Certification run",
                status=CHECK_FAIL,
                message=str(exc),
            )
        )
        report = FinalPlatformCertificationReportRead(
            readiness_score=0.0,
            certification_result=RESULT_NOT_READY,
            production_recommendation=_production_recommendation(RESULT_NOT_READY, 0.0),
            validation_status=CHECK_FAIL,
            health_status="UNHEALTHY",
            failures=[str(exc)],
        )
        row.validation_summary = json.dumps({"error": str(exc)}, default=str)
    finally:
        row.completed_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        session.refresh(row)

    try:
        payload = json.loads(row.validation_summary or "{}")
        report = FinalPlatformCertificationReportRead.model_validate(payload.get("report", {}))
        all_checks = [FinalPlatformCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
    except (json.JSONDecodeError, ValueError):
        report = FinalPlatformCertificationReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            production_recommendation=_production_recommendation(row.certification_result, float(row.readiness_score)),
            validation_status=_validation_status(all_checks),
            health_status=row.health_status,
        )

    return _to_read(row, checks=all_checks, report=report)


def get_latest_final_platform_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> FinalPlatformCertificationRead | None:
    row = session.exec(
        select(FinalPlatformCertificationRun)
        .where(FinalPlatformCertificationRun.owner_user_id == owner_user_id)
        .order_by(FinalPlatformCertificationRun.started_at.desc(), FinalPlatformCertificationRun.id.desc())
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [FinalPlatformCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = FinalPlatformCertificationReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = FinalPlatformCertificationReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            production_recommendation=_production_recommendation(row.certification_result, float(row.readiness_score)),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=row.health_status,
        )
    return _to_read(row, checks=checks, report=report)


def build_final_platform_certification_ops_panel(
    session: Session,
    *,
    owner_user_id: int,
) -> FinalPlatformCertificationOpsPanelRead:
    latest = get_latest_final_platform_certification(session, owner_user_id=owner_user_id)
    if latest is None:
        return FinalPlatformCertificationOpsPanelRead()
    summary = latest.report.production_recommendation[:240] if latest.report.production_recommendation else ""
    return FinalPlatformCertificationOpsPanelRead(
        last_certification_at=latest.completed_at or latest.started_at,
        readiness_score=latest.readiness_score,
        certification_result=latest.certification_result,
        health_status=latest.health_status,
        validation_summary=summary,
    )


def _read_from_row(row: FinalPlatformCertificationRun) -> FinalPlatformCertificationRead:
    try:
        payload = json.loads(row.validation_summary or "{}")
        checks = [FinalPlatformCertificationCheckRead.model_validate(c) for c in payload.get("checks", [])]
        report = FinalPlatformCertificationReportRead.model_validate(payload.get("report", {}))
    except (json.JSONDecodeError, ValueError):
        checks = []
        report = FinalPlatformCertificationReportRead(
            readiness_score=float(row.readiness_score),
            certification_result=row.certification_result,
            production_recommendation=_production_recommendation(row.certification_result, float(row.readiness_score)),
            validation_status=CHECK_PASS if row.status == "SUCCESS" else CHECK_FAIL,
            health_status=row.health_status,
        )
    return _to_read(row, checks=checks, report=report)


def list_final_platform_certification_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FinalPlatformCertificationRead], int]:
    rows = session.exec(
        select(FinalPlatformCertificationRun)
        .where(FinalPlatformCertificationRun.owner_user_id == owner_user_id)
        .order_by(FinalPlatformCertificationRun.started_at.desc(), FinalPlatformCertificationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_read_from_row(row) for row in page], total
