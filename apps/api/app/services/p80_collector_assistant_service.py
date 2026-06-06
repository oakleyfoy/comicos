"""P80-03 collector shopping workflow on P80-01 intelligence and P52/P55 gaps."""

from __future__ import annotations

import re

from fastapi import HTTPException
from sqlmodel import Session

from app.schemas.mobile_scan_platform import P80BookIntelligenceRead
from app.schemas.p80_collector_assistant import (
    P80CollectionCompletionRead,
    P80CollectorActionCardRead,
    P80CollectorDashboardRead,
    P80CollectorOpportunityItemRead,
    P80CollectorPriceEvalRequest,
    P80CollectorPriceEvalResultRead,
    P80CollectorScanRequest,
    P80CollectorScanResultRead,
    P80PriceAssessmentRead,
    P80SpecOpportunityRead,
    PriceBuyAssessment,
)
from app.services.acquisition_opportunities import refresh_and_list_latest_acquisition_opportunities
from app.services.collection_gaps import (
    build_collection_gap_summary,
    refresh_and_list_latest_collection_gaps,
)
from app.services.grading_candidate_engine import REC_GRADE, REC_PRESS_AND_GRADE
from app.models.asset_ledger import InventoryCopy
from app.services.mobile_scan_platform_service import (
    _book_from_copy,
    build_book_intelligence,
    get_book_intelligence,
    identify_for_scan_input,
)
from app.schemas.p77_personalization import P77PersonalizationSnapshotRead
from app.services.p77_personalization_engine import load_personalization_context
from app.services.p77_personalization_service import personalization_for_scan
from app.services.run_detection import run_detection_groups_for_user
from app.services.unified_collector_intelligence import list_latest_unified_collector_recommendations

_DUPLICATE_INVENTORY_THRESHOLD = 4
_ISSUE_ONE_PATTERN = re.compile(r"^(?:0*1(?:\.0+)?|one|1st)$", re.IGNORECASE)


def _normalize_issue_label(value: str) -> str:
    return value.strip().lower().lstrip("#")


def _series_matches(*, scanned_series: str, scanned_publisher: str, group_title: str, group_publisher: str) -> bool:
    series_key = scanned_series.strip().lower()
    title_key = group_title.strip().lower()
    if not series_key:
        return False
    if series_key == title_key or series_key in title_key or title_key in series_key:
        pub = scanned_publisher.strip().lower()
        if pub and group_publisher.strip().lower() not in pub and pub not in group_publisher.strip().lower():
            return False
        return True
    return False


def _build_collection_completion(
    session: Session,
    *,
    owner_user_id: int,
    series_name: str,
    publisher: str,
    issue_number: str,
) -> P80CollectionCompletionRead | None:
    groups = run_detection_groups_for_user(session, owner_user_id=owner_user_id)
    match = None
    for group in groups:
        if _series_matches(
            scanned_series=series_name,
            scanned_publisher=publisher,
            group_title=group.title,
            group_publisher=group.publisher,
        ):
            match = group
            break
    if match is None:
        return None

    missing_labels: list[str] = []
    for row in match.missing_issues:
        if row.classification in {"confirmed_missing", "likely_missing"} and row.issue_number:
            missing_labels.append(row.issue_number)

    missing_labels = sorted(set(missing_labels), key=lambda v: (_normalize_issue_label(v), v))[:12]
    known = max(match.known_issue_count, match.distinct_issue_count)
    owned = match.distinct_issue_count
    completion_pct: float | None = None
    if known > 0:
        completion_pct = round(100.0 * owned / known, 1)

    scanned_norm = _normalize_issue_label(issue_number) if issue_number else ""
    scanned_missing = bool(
        scanned_norm and any(_normalize_issue_label(label) == scanned_norm for label in missing_labels)
    )
    label = "Series Completion" if match.series_status == "probable_ongoing_series" else "Current Run Completion"

    return P80CollectionCompletionRead(
        label=label,
        owned_issue_count=owned,
        known_issue_count=known,
        completion_percent=completion_pct,
        missing_issue_numbers=missing_labels,
        suggested_next_purchases=missing_labels[:5],
        scanned_issue_is_missing=scanned_missing,
        gap_completion_opportunity=scanned_missing,
    )


def _build_spec_opportunity(
    *,
    issue_number: str,
    series_name: str,
    book_intel: P80BookIntelligenceRead | None,
) -> P80SpecOpportunityRead:
    if book_intel is None:
        return P80SpecOpportunityRead(detected=False)
    issue = (issue_number or "").strip()
    is_first = bool(issue and _ISSUE_ONE_PATTERN.match(issue.replace("#", "")))
    rec = (book_intel.recommendation.recommendation or "").upper()
    score = book_intel.recommendation.conviction_score
    signals: list[str] = []
    if is_first:
        signals.append("First issue")
    if series_name and issue == "1":
        signals.append("New series launch")
    if book_intel.fmv.price_trend_30d and book_intel.fmv.price_trend_30d.upper() in {"RISING", "UP"}:
        signals.append("Rising demand")
    if book_intel.fmv.sales_velocity is not None and book_intel.fmv.sales_velocity >= 1.0:
        signals.append("Strong liquidity")
    if score is not None and score >= 80:
        signals.append("High recommendation score")

    detected = is_first and (score is None or score >= 65 or rec in {"BUY", "ACQUIRE", "WATCH"})
    if not detected:
        return P80SpecOpportunityRead(detected=False)

    opp_score = score if score is not None else 75.0
    recommendation = "BUY" if rec in {"BUY", "ACQUIRE", "PREORDER"} or not book_intel.ownership.owned else rec or "WATCH"
    return P80SpecOpportunityRead(
        detected=True,
        score=round(opp_score, 1),
        signals=signals[:6],
        recommendation=recommendation,
    )


def assess_price(*, asking_price: float, authoritative_fmv: float | None) -> P80PriceAssessmentRead:
    if asking_price <= 0:
        raise HTTPException(status_code=422, detail="asking_price must be positive.")
    if authoritative_fmv is None or authoritative_fmv <= 0:
        return P80PriceAssessmentRead(
            asking_price=asking_price,
            authoritative_fmv=authoritative_fmv,
            spread_percent=None,
            assessment="UNKNOWN",
        )
    spread = round(100.0 * (authoritative_fmv - asking_price) / asking_price, 1)
    if asking_price <= authoritative_fmv * 0.85:
        assessment: PriceBuyAssessment = "GREAT_BUY"
    elif asking_price <= authoritative_fmv * 1.1:
        assessment = "FAIR_BUY"
    else:
        assessment = "OVERPRICED"
    return P80PriceAssessmentRead(
        asking_price=asking_price,
        authoritative_fmv=authoritative_fmv,
        spread_percent=spread,
        assessment=assessment,
    )


def build_collector_action_card(
    *,
    book_intel: P80BookIntelligenceRead | None,
    price_assessment: P80PriceAssessmentRead | None,
    collection_completion: P80CollectionCompletionRead | None,
    spec_opportunity: P80SpecOpportunityRead | None,
    personalization: P77PersonalizationSnapshotRead | None = None,
    copy_target: int | None = None,
) -> P80CollectorActionCardRead:
    reasons: list[str] = []
    if book_intel is None:
        return P80CollectorActionCardRead(action="WATCH", reasons=["Identification incomplete — verify manually."])

    ownership = book_intel.ownership
    recommendation = book_intel.recommendation
    grading = book_intel.grading
    fmv = book_intel.fmv
    rec = (recommendation.recommendation or "HOLD").upper()
    score = recommendation.conviction_score

    target = copy_target or _DUPLICATE_INVENTORY_THRESHOLD
    inventory_exceeded = ownership.total_copies > max(target, 1) and ownership.total_copies >= _DUPLICATE_INVENTORY_THRESHOLD
    if inventory_exceeded and not (collection_completion and collection_completion.gap_completion_opportunity):
        reasons.append(f"User owns {ownership.total_copies} copies")
        reasons.append("Inventory target exceeded")
        if price_assessment and price_assessment.assessment == "OVERPRICED":
            reasons.append("Over market price")
        if fmv.price_trend_30d and fmv.price_trend_30d.upper() in {"FALLING", "DOWN", "DECLINING"}:
            reasons.append("FMV declining")
        return P80CollectorActionCardRead(
            action="PASS",
            reasons=reasons[:6],
            inventory_target_exceeded=True,
        )

    if price_assessment and price_assessment.assessment == "OVERPRICED" and ownership.total_copies >= 2:
        reasons.append("Over market price")
        reasons.append(f"User owns {ownership.total_copies} copies")
        return P80CollectorActionCardRead(action="PASS", reasons=reasons[:6])

    if collection_completion and collection_completion.gap_completion_opportunity:
        action = "BUY"
        reasons.append("Gap completion opportunity")
        if collection_completion.missing_issue_numbers:
            reasons.append(f"Missing #{collection_completion.missing_issue_numbers[0]} in run context")
    elif spec_opportunity and spec_opportunity.detected and not ownership.owned:
        action = "BUY"
        reasons.append("Spec opportunity detected")
        reasons.extend(spec_opportunity.signals[:2])
    elif price_assessment and price_assessment.assessment == "GREAT_BUY" and not inventory_exceeded:
        action = "BUY"
        reasons.append("Under market price")
    elif not ownership.owned and rec in {"BUY", "ACQUIRE", "PREORDER"}:
        action = "BUY"
        reasons.append("Recommendation favors acquisition")
        reasons.append("User owns 0 copies")
    elif rec == "SELL":
        action = "SELL"
        reasons.append("Sell intelligence active")
    elif grading.grade_recommendation in {REC_GRADE, REC_PRESS_AND_GRADE}:
        action = "GRADE"
        reasons.append(f"Grading recommendation: {grading.grade_recommendation}")
        if grading.estimated_roi_pct is not None:
            reasons.append(f"Estimated ROI {grading.estimated_roi_pct:.1f}%")
    elif rec == "WATCH":
        action = "WATCH"
        reasons.append("Watch recommendation")
    else:
        action = "HOLD"
        reasons.append("Default hold posture")

    if score is not None:
        reasons.append(f"Recommendation score {score:.0f}")
    if fmv.price_trend_30d and fmv.price_trend_30d.upper() in {"RISING", "UP"}:
        reasons.append("FMV increasing")
    if fmv.liquidity_rating and str(fmv.liquidity_rating).upper() in {"HIGH", "VERY_HIGH"}:
        reasons.append("Strong liquidity")
    if price_assessment and price_assessment.assessment == "GREAT_BUY" and action != "BUY":
        action = "BUY"
        reasons.append("Vendor price below FMV")

    if personalization is not None:
        pscore = personalization.personalized_score or 0.0
        if personalization.budget_state == "RED" and action == "BUY" and pscore < 72.0:
            action = "PASS"
            reasons = personalization.reasons[:4] + ["Budget exhausted — personalized PASS"]
        elif action == "BUY" and pscore < 50.0 and not (collection_completion and collection_completion.gap_completion_opportunity):
            action = "PASS"
            reasons = personalization.reasons[:4] + [f"Personalized score {pscore:.0f}"]
        else:
            reasons = personalization.reasons[:2] + reasons
            if personalization.personalized_score is not None:
                reasons.append(f"Personalized score {personalization.personalized_score:.0f}")

    return P80CollectorActionCardRead(action=action, reasons=reasons[:6])


def evaluate_collector_scan(
    session: Session,
    *,
    owner_user_id: int,
    payload: P80CollectorScanRequest,
) -> P80CollectorScanResultRead:
    identification, identity = identify_for_scan_input(
        session,
        owner_user_id=owner_user_id,
        barcode=payload.barcode,
        manual_entry=payload.manual_entry,
    )
    book_intel: P80BookIntelligenceRead | None = None
    collection_completion: P80CollectionCompletionRead | None = None
    spec_opportunity: P80SpecOpportunityRead | None = None
    if identity is not None:
        book_intel = build_book_intelligence(session, owner_user_id=owner_user_id, identity=identity)
        collection_completion = _build_collection_completion(
            session,
            owner_user_id=owner_user_id,
            series_name=identity.series_name,
            publisher=identity.publisher,
            issue_number=identity.issue_number,
        )
        spec_opportunity = _build_spec_opportunity(
            issue_number=identity.issue_number,
            series_name=identity.series_name,
            book_intel=book_intel,
        )

    price_assessment: P80PriceAssessmentRead | None = None
    if payload.vendor_price is not None and payload.vendor_price > 0:
        fmv_value = book_intel.fmv.authoritative_fmv if book_intel else None
        price_assessment = assess_price(asking_price=float(payload.vendor_price), authoritative_fmv=fmv_value)

    personalization: P77PersonalizationSnapshotRead | None = None
    copy_target: int | None = None
    if book_intel is not None and identity is not None:
        ctx = load_personalization_context(session, owner_user_id=owner_user_id)
        copy_target = ctx.profile.default_copy_count
        personalization = personalization_for_scan(
            session,
            owner_user_id=owner_user_id,
            global_score=book_intel.recommendation.conviction_score,
            publisher=identity.publisher,
            series_name=identity.series_name,
            title=identity.title,
            owned_copies=book_intel.ownership.total_copies,
            gap_completion=bool(collection_completion and collection_completion.gap_completion_opportunity),
            estimated_fmv=book_intel.fmv.authoritative_fmv,
        )

    action_card = build_collector_action_card(
        book_intel=book_intel,
        price_assessment=price_assessment,
        collection_completion=collection_completion,
        spec_opportunity=spec_opportunity,
        personalization=personalization,
        copy_target=copy_target,
    )

    return P80CollectorScanResultRead(
        identification=identification,
        book_intelligence=book_intel,
        collection_completion=collection_completion,
        spec_opportunity=spec_opportunity,
        action_card=action_card,
        price_assessment=price_assessment,
        personalization=personalization,
    )


def evaluate_collector_price(
    session: Session,
    *,
    owner_user_id: int,
    payload: P80CollectorPriceEvalRequest,
) -> P80CollectorPriceEvalResultRead:
    identification = None
    book_intel: P80BookIntelligenceRead | None = None
    resolved_identity = None
    fmv_override = payload.authoritative_fmv

    if payload.inventory_id is not None:
        book_intel = get_book_intelligence(session, owner_user_id=owner_user_id, inventory_id=payload.inventory_id)
        copy = session.get(InventoryCopy, payload.inventory_id)
        if copy is not None:
            resolved_identity = _book_from_copy(session, copy, source="inventory_lookup")
        if fmv_override is None:
            fmv_override = book_intel.fmv.authoritative_fmv
    elif payload.barcode or payload.manual_entry:
        identification, resolved_identity = identify_for_scan_input(
            session,
            owner_user_id=owner_user_id,
            barcode=payload.barcode,
            manual_entry=payload.manual_entry,
        )
        if resolved_identity is not None:
            book_intel = build_book_intelligence(session, owner_user_id=owner_user_id, identity=resolved_identity)
            if fmv_override is None:
                fmv_override = book_intel.fmv.authoritative_fmv

    price_assessment = assess_price(asking_price=float(payload.asking_price), authoritative_fmv=fmv_override)
    personalization: P77PersonalizationSnapshotRead | None = None
    copy_target: int | None = None
    action_card = None
    if book_intel is not None and resolved_identity is not None:
        ctx = load_personalization_context(session, owner_user_id=owner_user_id)
        copy_target = ctx.profile.default_copy_count
        personalization = personalization_for_scan(
            session,
            owner_user_id=owner_user_id,
            global_score=book_intel.recommendation.conviction_score,
            publisher=resolved_identity.publisher,
            series_name=resolved_identity.series_name,
            title=resolved_identity.title,
            owned_copies=book_intel.ownership.total_copies,
            gap_completion=False,
            estimated_fmv=book_intel.fmv.authoritative_fmv,
        )
    if book_intel is not None:
        action_card = build_collector_action_card(
            book_intel=book_intel,
            price_assessment=price_assessment,
            collection_completion=None,
            spec_opportunity=None,
            personalization=personalization,
            copy_target=copy_target,
        )

    return P80CollectorPriceEvalResultRead(
        identification=identification,
        price_assessment=price_assessment,
        action_card=action_card,
        personalization=personalization,
    )


def list_collector_gaps(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list, int]:
    return refresh_and_list_latest_collection_gaps(
        session,
        owner_user_id=owner_user_id,
        limit=limit,
        offset=offset,
    )


def list_collector_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[P80CollectorOpportunityItemRead], int]:
    lim = max(1, min(limit, 100))
    off = max(0, offset)
    items: list[P80CollectorOpportunityItemRead] = []

    acq_items, _ = refresh_and_list_latest_acquisition_opportunities(
        session,
        owner_user_id=owner_user_id,
        limit=50,
        offset=0,
    )
    for row in acq_items:
        title = f"{row.series_name} #{row.issue_number}".strip()
        items.append(
            P80CollectorOpportunityItemRead(
                kind="acquisition",
                title=title or row.series_name,
                subtitle=row.publisher,
                score=row.priority_score,
                recommendation=row.opportunity_type,
                rationale=row.rationale,
            )
        )

    unified, _ = list_latest_unified_collector_recommendations(
        session,
        owner_user_id=owner_user_id,
        limit=50,
        offset=0,
    )
    for row in unified:
        items.append(
            P80CollectorOpportunityItemRead(
                kind="unified_recommendation",
                title=row.title,
                subtitle=row.recommendation_type or "",
                score=row.priority_score,
                recommendation=row.recommendation_type,
                rationale=row.rationale,
            )
        )

    items.sort(key=lambda r: (-(r.score or 0), r.title.lower()))
    total = len(items)
    return items[off : off + lim], total


def build_collector_dashboard(session: Session, *, owner_user_id: int) -> P80CollectorDashboardRead:
    summary = build_collection_gap_summary(session, owner_user_id=owner_user_id)
    gaps, _ = refresh_and_list_latest_collection_gaps(
        session,
        owner_user_id=owner_user_id,
        limit=12,
        offset=0,
    )
    opportunities, _ = list_collector_opportunities(session, owner_user_id=owner_user_id, limit=30, offset=0)
    acquisitions = [o for o in opportunities if o.kind == "acquisition"][:8]
    spec_ops = [o for o in opportunities if o.recommendation in {"BUY", "ACQUIRE"} and (o.score or 0) >= 70][:6]
    watch = [o for o in opportunities if o.recommendation in {"WATCH", "HOLD"}][:6]

    gap_summary: dict[str, int | float] = {
        "total_gaps": summary.total_gaps,
        "average_completion_percent": summary.average_completion_percent,
    }
    gap_summary.update({f"priority_{k}": v for k, v in summary.by_priority.items()})

    return P80CollectorDashboardRead(
        gap_summary=gap_summary,
        collection_gaps=gaps,
        recommended_acquisitions=acquisitions,
        spec_opportunities=spec_ops,
        books_to_watch=watch,
    )
