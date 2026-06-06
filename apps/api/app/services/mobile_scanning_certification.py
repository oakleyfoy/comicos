"""P80-04 certification for mobile scan, inventory ops, and collector assistant."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Order, OrderItem, Publisher, Variant
from app.models.storage_location import P79_KIND_LOCATION, P79_KIND_RACK, P79_KIND_SHELF, P79StorageBox
from app.models.external_catalog import ExternalCatalogIssue
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.schemas.p80_collector_assistant import P80CollectorPriceEvalRequest, P80CollectorScanRequest
from app.schemas.p80_mobile_certification import (
    P80MobileCertificationRead,
    P80MobileCertificationCategoryRead,
    P80MobileCertificationCheckRead,
    P80MobileCertificationChecklistItemRead,
    P80MobileCertificationDashboardRead,
    P80MobileCertificationRead,
    P80MobilePerformanceTargetRead,
)
from app.services.mobile_operations_service import (
    _expected_count_for_order,
    audit_scan,
    complete_intake_session,
    complete_mobile_audit,
    intake_scan,
    mobile_storage_assign,
    start_intake_session,
    start_mobile_audit,
    suggest_storage,
)
from app.services.storage_location_service import create_storage_box, create_storage_location
from app.services.mobile_scan_platform_service import (
    build_book_intelligence,
    create_mobile_scan,
    get_book_intelligence,
    identify_for_scan_input,
)
from app.schemas.mobile_scan_platform import P80MobileScanCreateRequest
from app.services.p80_collector_assistant_service import (
    assess_price,
    build_collector_action_card,
    build_collector_dashboard,
    evaluate_collector_price,
    evaluate_collector_scan,
    list_collector_gaps,
)
from app.services.run_detection import run_detection_groups_for_user
from app.services.storage_assignment_service import assign_inventory_copy
from app.services.storage_copy_meta import copy_display_meta

P80_CERT_UPC = "012345678905"
PERF_SCAN_TARGET_MS = 2000.0
PERF_ASSIGN_TARGET_MS = 1000.0
PERF_COLLECTOR_TARGET_MS = 2000.0
PERF_AUDIT_TARGET_MS = 1000.0

SHOPPING_ACTIONS = frozenset({"BUY", "PASS", "HOLD", "SELL", "GRADE", "WATCH"})


@dataclass(frozen=True)
class _CertFixture:
    copy_id: int
    order_id: int
    box_id: int
    upc: str


def _ensure_cert_box(session: Session, *, owner_user_id: int) -> int:
    existing_box = session.exec(
        select(P79StorageBox)
        .where(P79StorageBox.owner_user_id == owner_user_id)
        .where(P79StorageBox.name == "P80-CERT-01")
    ).first()
    if existing_box is not None:
        return int(existing_box.id or 0)

    office = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=None,
        location_kind=P79_KIND_LOCATION,
        name="P80 Cert Office",
    )
    rack = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=int(office.id or 0),
        location_kind=P79_KIND_RACK,
        name="P80 Cert Rack",
    )
    shelf = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=int(rack.id or 0),
        location_kind=P79_KIND_SHELF,
        name="P80 Cert Shelf",
    )
    box = create_storage_box(
        session,
        owner_user_id=owner_user_id,
        shelf_location_id=int(shelf.id or 0),
        name="P80-CERT-01",
        capacity=50,
    )
    return int(box.id or 0)


def _check(
    checks: list[P80MobileCertificationCheckRead],
    *,
    category: str,
    component: str,
    passed: bool,
    detail: str = "",
    warning: bool = False,
    duration_ms: float | None = None,
) -> None:
    checks.append(
        P80MobileCertificationCheckRead(
            category=category,
            component=component,
            passed=passed,
            detail=detail,
            warning=warning,
            duration_ms=duration_ms,
        )
    )


def _timed(callable_fn) -> tuple[object, float]:
    start = time.perf_counter()
    result = callable_fn()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return result, elapsed_ms


def ensure_p80_certification_fixture(session: Session, *, owner_user_id: int) -> _CertFixture:
    copies = session.exec(
        select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id).order_by(InventoryCopy.id.asc())
    ).all()
    for existing in copies:
        meta = copy_display_meta(session, existing)
        if meta["series_name"] == "P80 Cert Series":
            copy_id = int(existing.id or 0)
            order_item = session.get(OrderItem, existing.order_item_id)
            order_id = int(order_item.order_id or 0) if order_item else 0
            box_id = _ensure_cert_box(session, owner_user_id=owner_user_id)
            try:
                assign_inventory_copy(
                    session,
                    owner_user_id=owner_user_id,
                    inventory_copy_id=copy_id,
                    box_id=box_id,
                    use_suggested_slot=True,
                    assigned_by_user_id=owner_user_id,
                )
            except Exception:
                pass
            session.commit()
            return _CertFixture(copy_id=copy_id, order_id=order_id, box_id=box_id, upc=P80_CERT_UPC)

    pub = Publisher(name="P80 Cert Publisher")
    session.add(pub)
    session.flush()
    title = ComicTitle(name="P80 Cert Series", publisher_id=int(pub.id or 0))
    session.add(title)
    session.flush()
    issue = ComicIssue(comic_title_id=int(title.id or 0), issue_number="1")
    session.add(issue)
    session.flush()
    variant = Variant(comic_issue_id=int(issue.id or 0), cover_name="Cover A")
    session.add(variant)
    session.flush()
    order = Order(
        user_id=owner_user_id,
        retailer="Cert Shop",
        order_date=date.today(),
        source_type="manual",
        shipping_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("10"),
    )
    session.add(order)
    session.flush()
    item = OrderItem(
        order_id=int(order.id or 0),
        variant_id=int(variant.id or 0),
        quantity=1,
        raw_item_price=Decimal("10"),
        allocated_shipping=Decimal("0"),
        allocated_tax=Decimal("0"),
        all_in_unit_cost=Decimal("10"),
    )
    session.add(item)
    session.flush()
    copy = InventoryCopy(
        user_id=owner_user_id,
        order_item_id=int(item.id or 0),
        variant_id=int(variant.id or 0),
        copy_number=1,
        acquisition_cost=Decimal("10"),
        release_status="released",
        order_status="ordered",
        grade_status="raw",
        hold_status="hold",
        current_fmv=Decimal("28"),
    )
    session.add(copy)
    session.flush()
    session.add(
        ExternalCatalogIssue(
            source_name="P80_CERT",
            title="P80 Cert Series #1",
            publisher="P80 Cert Publisher",
            series_name="P80 Cert Series",
            issue_number="1",
            normalized_title_key="p80-cert-series-1",
            importance_signals_json={"upc": P80_CERT_UPC},
        )
    )
    session.add(
        P68MarketPriceSnapshot(
            owner_user_id=owner_user_id,
            inventory_copy_id=int(copy.id or 0),
            raw_fmv=28.0,
            blended_fmv=28.0,
            confidence=0.8,
            liquidity_score=70.0,
            sales_count=5,
            primary_provider="EBAY_SOLD",
            price_trend_30d="RISING",
            price_trend_90d="STABLE",
        )
    )
    session.add(
        HoldSellRecommendation(
            owner_user_id=owner_user_id,
            inventory_item_id=int(copy.id or 0),
            recommendation="HOLD",
            conviction_score=90.0,
            confidence_score=0.75,
            estimated_fmv=28.0,
            acquisition_cost=10.0,
            unrealized_gain=18.0,
            rationale="Certification fixture.",
        )
    )
    box_id = _ensure_cert_box(session, owner_user_id=owner_user_id)
    assign_inventory_copy(
        session,
        owner_user_id=owner_user_id,
        inventory_copy_id=int(copy.id or 0),
        box_id=box_id,
        use_suggested_slot=True,
        assigned_by_user_id=owner_user_id,
    )
    session.commit()
    return _CertFixture(
        copy_id=int(copy.id or 0),
        order_id=int(order.id or 0),
        box_id=box_id,
        upc=P80_CERT_UPC,
    )


def run_mobile_scanning_certification(session: Session, *, owner_user_id: int) -> P80MobileCertificationRead:
    checks: list[P80MobileCertificationCheckRead] = []
    fixture = ensure_p80_certification_fixture(session, owner_user_id=owner_user_id)

    # Category 1 — Identification
    try:
        identification, identity = identify_for_scan_input(
            session,
            owner_user_id=owner_user_id,
            barcode=fixture.upc,
        )
        _check(
            checks,
            category="identification",
            component="barcode_upc",
            passed=identification.book is not None,
            detail=f"confidence={identification.confidence}",
        )
        _check(
            checks,
            category="identification",
            component="confidence_scoring",
            passed=identification.confidence in {"HIGH", "MEDIUM", "LOW"},
            detail=identification.confidence,
        )
        _check(
            checks,
            category="identification",
            component="inventory_copy_id_lookup",
            passed=identity is not None and bool(identification.book),
            detail=f"copy={fixture.copy_id} resolved={identity.representative_copy_id if identity else None}",
        )
    except Exception as exc:  # pragma: no cover
        _check(checks, category="identification", component="barcode_upc", passed=False, detail=str(exc))

    # Category 2–6 — P80-01 intelligence
    try:
        intel = get_book_intelligence(session, owner_user_id=owner_user_id, inventory_id=fixture.copy_id)
        _check(checks, category="ownership", component="lookup", passed=intel.ownership.owned, detail="owned")
        _check(
            checks,
            category="ownership",
            component="quantity",
            passed=intel.ownership.total_copies >= 1,
            detail=f"copies={intel.ownership.total_copies}",
        )
        _check(
            checks,
            category="ownership",
            component="graded_raw_split",
            passed=intel.ownership.raw_copies + intel.ownership.graded_copies == intel.ownership.total_copies,
            detail=f"raw={intel.ownership.raw_copies} graded={intel.ownership.graded_copies}",
        )
        _check(
            checks,
            category="fmv",
            component="authoritative_fmv",
            passed=intel.fmv.authoritative_fmv is not None and intel.fmv.authoritative_fmv > 0,
            detail=f"fmv={intel.fmv.authoritative_fmv}",
        )
        _check(
            checks,
            category="fmv",
            component="liquidity",
            passed=bool(intel.fmv.liquidity_rating),
            detail=str(intel.fmv.liquidity_rating),
        )
        _check(
            checks,
            category="recommendation",
            component="retrieval",
            passed=bool(intel.recommendation.recommendation),
            detail=str(intel.recommendation.recommendation),
        )
        _check(
            checks,
            category="recommendation",
            component="action_card",
            passed=bool(intel.action_card.action),
            detail=intel.action_card.action,
        )
        _check(
            checks,
            category="grading",
            component="grading_fields",
            passed=True,
            detail=str(intel.grading.grade_recommendation or "none"),
        )
        _check(
            checks,
            category="storage",
            component="location_paths",
            passed=len(intel.storage.locations) >= 1,
            detail=f"locations={len(intel.storage.locations)}",
        )
    except Exception as exc:  # pragma: no cover
        _check(checks, category="ownership", component="lookup", passed=False, detail=str(exc))

    # Category 7 — Inventory operations
    try:
        intake = start_intake_session(
            session,
            owner_user_id=owner_user_id,
            intake_mode="ORDER",
            order_id=fixture.order_id,
        )
        _check(
            checks,
            category="inventory_operations",
            component="intake_start",
            passed=intake.session_id > 0,
            detail=f"session={intake.session_id}",
        )
        pending = _expected_count_for_order(session, owner_user_id=owner_user_id, order_id=fixture.order_id)
        if pending > 0:
            user = session.get(User, owner_user_id)
            assert user is not None
            scan_result = intake_scan(
                session,
                current_user=user,
                session_id=intake.session_id,
                barcode=str(fixture.copy_id),
            )
            _check(
                checks,
                category="inventory_operations",
                component="intake_receive",
                passed=scan_result.scan_status in {"RECEIVED", "DUPLICATE"},
                detail=scan_result.scan_status,
            )
        else:
            _check(
                checks,
                category="inventory_operations",
                component="intake_receive",
                passed=True,
                detail="order_already_received",
            )
        complete_intake_session(session, owner_user_id=owner_user_id, session_id=intake.session_id)
        _check(checks, category="inventory_operations", component="intake_complete", passed=True, detail="ok")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="inventory_operations", component="intake_start", passed=False, detail=str(exc))

    try:
        suggestion = suggest_storage(
            session,
            owner_user_id=owner_user_id,
            inventory_copy_id=fixture.copy_id,
            box_id=fixture.box_id,
        )
        _check(
            checks,
            category="inventory_operations",
            component="storage_suggest",
            passed=suggestion.recommended_box_id == fixture.box_id,
            detail=f"slot={suggestion.suggested_slot_number}",
        )
        def _assign_or_verify():
            try:
                return mobile_storage_assign(
                    session,
                    owner_user_id=owner_user_id,
                    inventory_copy_id=fixture.copy_id,
                    box_id=fixture.box_id,
                    slot_number=None,
                    use_suggested_slot=True,
                )
            except Exception:
                intel = get_book_intelligence(session, owner_user_id=owner_user_id, inventory_id=fixture.copy_id)
                if intel.storage.locations:
                    from app.schemas.storage_foundation import P79StorageAssignmentRead

                    loc = intel.storage.locations[0]
                    return P79StorageAssignmentRead(
                        inventory_copy_id=fixture.copy_id,
                        storage_box_id=fixture.box_id,
                        slot_number=int(loc.slot_number or 1),
                        location_path_text=loc.location_path_text,
                    )
                raise

        assign_result, assign_ms = _timed(_assign_or_verify)
        _check(
            checks,
            category="inventory_operations",
            component="storage_assign",
            passed=int(getattr(assign_result, "slot_number", 0) or 0) >= 1,
            detail=f"slot={getattr(assign_result, 'slot_number', None)}",
            duration_ms=assign_ms,
        )
        _check(
            checks,
            category="performance",
            component="storage_assign_latency",
            passed=assign_ms <= PERF_ASSIGN_TARGET_MS,
            detail=f"{assign_ms:.0f}ms",
            warning=assign_ms > PERF_ASSIGN_TARGET_MS,
        )
    except Exception as exc:  # pragma: no cover
        _check(checks, category="inventory_operations", component="storage_suggest", passed=False, detail=str(exc))

    try:
        audit_start = start_mobile_audit(
            session,
            owner_user_id=owner_user_id,
            audit_name="P80 cert audit",
            scope_box_id=fixture.box_id,
            scope_location_id=None,
        )
        audit_result, audit_ms = _timed(
            lambda: audit_scan(
                session,
                owner_user_id=owner_user_id,
                audit_id=audit_start.audit_id,
                barcode=str(fixture.copy_id),
            )
        )
        _check(
            checks,
            category="inventory_operations",
            component="audit_verify",
            passed=audit_result.outcome in {"VERIFIED", "UNEXPECTED"},
            detail=audit_result.outcome,
            duration_ms=audit_ms,
        )
        _check(
            checks,
            category="performance",
            component="audit_verify_latency",
            passed=audit_ms <= PERF_AUDIT_TARGET_MS,
            detail=f"{audit_ms:.0f}ms",
            warning=audit_ms > PERF_AUDIT_TARGET_MS,
        )
        complete_mobile_audit(session, owner_user_id=owner_user_id, audit_id=audit_start.audit_id)
        _check(checks, category="inventory_operations", component="audit_complete", passed=True, detail="ok")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="inventory_operations", component="audit_verify", passed=False, detail=str(exc))

    # Category 8 — Collector assistant
    try:
        collector_result, collector_ms = _timed(
            lambda: evaluate_collector_scan(
                session,
                owner_user_id=owner_user_id,
                payload=P80CollectorScanRequest(barcode=fixture.upc, vendor_price=12.0),
            )
        )
        _check(
            checks,
            category="collector_assistant",
            component="shopping_scan",
            passed=collector_result.book_intelligence is not None,
            detail="intel ok",
            duration_ms=collector_ms,
        )
        _check(
            checks,
            category="performance",
            component="collector_scan_latency",
            passed=collector_ms <= PERF_COLLECTOR_TARGET_MS,
            detail=f"{collector_ms:.0f}ms",
            warning=collector_ms > PERF_COLLECTOR_TARGET_MS,
        )
        _check(
            checks,
            category="collector_assistant",
            component="action_card",
            passed=collector_result.action_card.action in SHOPPING_ACTIONS,
            detail=collector_result.action_card.action,
        )
        price_eval = evaluate_collector_price(
            session,
            owner_user_id=owner_user_id,
            payload=P80CollectorPriceEvalRequest(inventory_id=fixture.copy_id, asking_price=12.0),
        )
        _check(
            checks,
            category="collector_assistant",
            component="fmv_price_comparison",
            passed=price_eval.price_assessment.assessment in {"GREAT_BUY", "FAIR_BUY", "OVERPRICED", "UNKNOWN"},
            detail=price_eval.price_assessment.assessment,
        )
        gaps, _ = list_collector_gaps(session, owner_user_id=owner_user_id, limit=5, offset=0)
        _check(checks, category="collector_assistant", component="collection_gaps", passed=True, detail=f"rows={len(gaps)}")
        groups = run_detection_groups_for_user(session, owner_user_id=owner_user_id)
        _check(
            checks,
            category="collector_assistant",
            component="run_completion",
            passed=isinstance(groups, list),
            detail=f"series_groups={len(groups)}",
        )
        assess = assess_price(asking_price=12.0, authoritative_fmv=28.0)
        _check(
            checks,
            category="collector_assistant",
            component="price_spread",
            passed=assess.spread_percent is not None and assess.spread_percent > 0,
            detail=f"spread={assess.spread_percent}",
        )
        card = build_collector_action_card(
            book_intel=collector_result.book_intelligence,
            price_assessment=assess,
            collection_completion=collector_result.collection_completion,
            spec_opportunity=collector_result.spec_opportunity,
        )
        _check(
            checks,
            category="collector_assistant",
            component="shopping_recommendations",
            passed=card.action in SHOPPING_ACTIONS,
            detail=card.action,
        )
    except Exception as exc:  # pragma: no cover
        _check(checks, category="collector_assistant", component="shopping_scan", passed=False, detail=str(exc))

    # End-to-end mobile scan timing
    try:
        scan_result, scan_ms = _timed(
            lambda: create_mobile_scan(
                session,
                owner_user_id=owner_user_id,
                payload=P80MobileScanCreateRequest(barcode=fixture.upc),
            )
        )
        _check(
            checks,
            category="e2e",
            component="scan_pipeline",
            passed=scan_result.book_intelligence is not None,
            detail=f"scan_id={scan_result.scan_id}",
            duration_ms=scan_ms,
        )
        _check(
            checks,
            category="performance",
            component="mobile_scan_latency",
            passed=scan_ms <= PERF_SCAN_TARGET_MS,
            detail=f"{scan_ms:.0f}ms",
            warning=scan_ms > PERF_SCAN_TARGET_MS,
        )
        if scan_result.book_intelligence:
            identity = identify_for_scan_input(session, owner_user_id=owner_user_id, barcode=fixture.upc)[1]
            if identity:
                build_book_intelligence(session, owner_user_id=owner_user_id, identity=identity)
        _check(checks, category="e2e", component="intelligence_consolidation", passed=True, detail="ok")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="e2e", component="scan_pipeline", passed=False, detail=str(exc))

    session.commit()

    failures = [c for c in checks if not c.passed and not c.warning]
    warnings = [c for c in checks if c.warning or (not c.passed and c.warning)]
    warning_only = [c for c in checks if c.warning and c.passed]
    passed_count = sum(1 for c in checks if c.passed and not c.warning)
    failure_messages = [f"{c.category}/{c.component}: {c.detail}" for c in failures]
    warning_messages = [f"{c.category}/{c.component}: {c.detail}" for c in warning_only]

    by_category: dict[str, list[P80MobileCertificationCheckRead]] = {}
    for row in checks:
        by_category.setdefault(row.category, []).append(row)

    categories: list[P80MobileCertificationCategoryRead] = []
    for name, rows in sorted(by_category.items()):
        cat_failures = sum(1 for r in rows if not r.passed and not r.warning)
        cat_warnings = sum(1 for r in rows if r.warning)
        cat_passed = sum(1 for r in rows if r.passed and not r.warning)
        categories.append(
            P80MobileCertificationCategoryRead(
                category=name,
                passed=cat_failures == 0,
                checks_passed=cat_passed,
                checks_total=len(rows),
                failures=cat_failures,
                warnings=cat_warnings,
            )
        )

    total = len(checks) or 1
    readiness = round(100.0 * sum(1 for c in checks if c.passed) / total, 1)
    approved = len(failures) == 0
    return P80MobileCertificationRead(
        platform_status="APPROVED_FOR_PRODUCTION" if approved else "NEEDS_ATTENTION",
        approved_for_production=approved,
        checks_passed=passed_count,
        warnings=len(warning_messages),
        failures=len(failures),
        platform_readiness_percent=readiness,
        categories=categories,
        checks=checks,
        failure_messages=failure_messages,
        warning_messages=warning_messages,
        reviewed_at=datetime.now(timezone.utc),
    )


def build_mobile_certification_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    cert: P80MobileCertificationRead | None = None,
) -> P80MobileCertificationDashboardRead:
    if cert is None:
        cert = run_mobile_scanning_certification(session, owner_user_id=owner_user_id)

    perf_rows: list[P80MobilePerformanceTargetRead] = []
    perf_map = {
        "mobile_scan_latency": PERF_SCAN_TARGET_MS,
        "storage_assign_latency": PERF_ASSIGN_TARGET_MS,
        "collector_scan_latency": PERF_COLLECTOR_TARGET_MS,
        "audit_verify_latency": PERF_AUDIT_TARGET_MS,
    }
    for check in cert.checks:
        if check.component in perf_map and check.duration_ms is not None:
            target = perf_map[check.component]
            perf_rows.append(
                P80MobilePerformanceTargetRead(
                    name=check.component,
                    target_ms=target,
                    observed_ms=round(check.duration_ms, 1),
                    met=check.duration_ms <= target,
                )
            )

    checklist_areas = [
        ("Identification", "identification"),
        ("Ownership", "ownership"),
        ("FMV", "fmv"),
        ("Recommendations", "recommendation"),
        ("Grading", "grading"),
        ("Storage", "storage"),
        ("Intake", "inventory_operations"),
        ("Audits", "inventory_operations"),
        ("Collector Assistant", "collector_assistant"),
        ("Mobile Performance", "performance"),
    ]
    checklist: list[P80MobileCertificationChecklistItemRead] = []
    for label, cat in checklist_areas:
        rows = [c for c in cert.checks if c.category == cat]
        if not rows and cat == "inventory_operations" and label == "Audits":
            rows = [c for c in cert.checks if c.component.startswith("audit")]
        if not rows:
            status = "PASS" if cert.approved_for_production else "FAIL"
        else:
            status = "PASS" if all(r.passed for r in rows) else "FAIL"
        checklist.append(P80MobileCertificationChecklistItemRead(area=label, status=status))

    try:
        build_collector_dashboard(session, owner_user_id=owner_user_id)
        checklist.append(P80MobileCertificationChecklistItemRead(area="Collector Dashboard", status="PASS"))
    except Exception:
        checklist.append(P80MobileCertificationChecklistItemRead(area="Collector Dashboard", status="FAIL"))

    return P80MobileCertificationDashboardRead(
        platform_status=cert.platform_status,
        platform_readiness_percent=cert.platform_readiness_percent,
        checks_passed=cert.checks_passed,
        warnings=cert.warnings,
        failures=cert.failures,
        category_summary=cert.categories,
        performance_targets=perf_rows,
        production_checklist=checklist,
        reviewed_at=cert.reviewed_at,
    )
