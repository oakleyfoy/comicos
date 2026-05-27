from decimal import Decimal
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import case, func, or_
from sqlmodel import Session, select

from app.models import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    InventoryFmvSnapshot,
    Order,
    OrderItem,
    Publisher,
    User,
    Variant,
)
from app.schemas.inventory import (
    BulkInventoryUpdateRequest,
    BulkInventoryUpdateResponse,
    InventoryDetailResponse,
    InventoryFmvSnapshotResponse,
    InventoryListResponse,
    InventoryRow,
    InventorySummaryResponse,
    InventoryUpdate,
    PortfolioPerformanceItem,
    PortfolioPerformanceResponse,
    ReleaseCalendarPresence,
)
from app.services.inventory_fmv import build_inventory_fmv_attachment, summarize_inventory_fmv
from app.services.acquisition_priority import inventory_acquisition_priority_teaser
from app.services.cover_images import list_cover_reads_for_inventory
from app.services.portfolio_registry import inventory_portfolio_teaser
from app.schemas.order_arrival_intelligence import OrderArrivalClassification
from app.schemas.ops import (
    OpsInventoryDuplicateCandidateGroup,
    OpsInventoryDuplicateCopyRow,
)
from app.services.duplicate_candidate_reviews import (
    load_reviews_for_keys,
    reviewer_email_map,
)
from app.services.duplicate_consolidation import inventory_duplicate_teaser
from app.services.duplicate_ownership_intelligence import duplicate_ownership_inventory_context_for_owner
from app.services.inventory_action_center import attachment_from_items, build_inventory_action_items
from app.services.inventory_intelligence import compute_inventory_intelligence
from app.services.inventory_risks import compute_inventory_risks
from app.services.order_arrival_intelligence import (
    batch_order_arrival_classifications,
    classifications_for_inventory_copy,
)
from app.services.order_states import derive_asset_state
from app.services.grading_roi import inventory_grading_roi_badge
from app.services.grading_reconciliation import inventory_grading_reconciliation_badge
from app.services.grading_recommendation import inventory_grading_recommendation_badge
from app.services.grading_risk import inventory_grading_risk_badge
from app.services.grading_submission import inventory_grading_submission_badge
from app.services.grading_spread import inventory_grading_spread_badge
from app.services.run_detection import run_detection_inventory_context_for_owner
from app.services.scan_sessions import originating_scan_session_for_inventory_copy
from app.services.grading_candidate_service import inventory_grading_badge
from app.services.portfolio_liquidity import inventory_portfolio_liquidity_teaser
from app.services.concentration_risk import inventory_concentration_risk_teaser
from app.services.portfolio_recommendation import inventory_portfolio_recommendation_teaser
from app.services.market_scoring import inventory_market_acquisition_score_teaser
from app.services.market_opportunity import inventory_market_opportunity_teaser
from app.services.portfolio_market_coupling import inventory_portfolio_market_coupling_teaser
from app.services.market_signal import inventory_market_signal_teaser

SORTABLE_FIELDS = {
    "title",
    "publisher",
    "purchase_date",
    "acquisition_cost",
    "current_fmv",
    "gain_loss",
    "star_rating",
}


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _split_metadata_identity_key(metadata_identity_key: str) -> tuple[str, str, str, str]:
    parts = metadata_identity_key.split("|")
    padded_parts = parts + [""] * (4 - len(parts))
    publisher, series_title, issue_number, variant = padded_parts[:4]
    return publisher, series_title, issue_number, variant


def gain_loss_expression():
    return case(
        (
            InventoryCopy.current_fmv.is_not(None),
            InventoryCopy.current_fmv - InventoryCopy.acquisition_cost,
        ),
        else_=None,
    )


def _asset_state_case_expression():
    return case(
        (InventoryCopy.order_status == "cancelled", "cancelled"),
        (InventoryCopy.order_status == "received", "in_hand"),
        (
            or_(
                InventoryCopy.release_status == "not_released_yet",
                InventoryCopy.order_status == "preordered",
            ),
            "preorder_not_released_yet",
        ),
        else_="ordered_not_received",
    )


def build_inventory_base_query(current_user: User):
    gain_loss_expr = gain_loss_expression().label("gain_loss")
    asset_state_expr = _asset_state_case_expression().label("asset_state")

    return (
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            ComicTitle.name.label("title"),
            Publisher.name.label("publisher"),
            ComicIssue.issue_number.label("issue_number"),
            ComicIssue.id.label("canonical_issue_id"),
            Variant.cover_name.label("cover_name"),
            Variant.printing.label("printing"),
            Variant.ratio.label("ratio"),
            Variant.variant_type.label("variant_type"),
            Variant.cover_artist.label("cover_artist"),
            Order.retailer.label("retailer"),
            Order.order_date.label("order_date"),
            InventoryCopy.acquisition_cost.label("acquisition_cost"),
            InventoryCopy.current_fmv.label("current_fmv"),
            InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
            InventoryCopy.canonical_series_id.label("canonical_series_id"),
            gain_loss_expr,
            InventoryCopy.grade_status.label("grade_status"),
            InventoryCopy.hold_status.label("hold_status"),
            InventoryCopy.star_rating.label("star_rating"),
            InventoryCopy.condition_notes.label("condition_notes"),
            Order.order_date.label("purchase_date"),
            InventoryCopy.release_date.label("release_date"),
            InventoryCopy.release_year.label("release_year"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.expected_ship_date.label("expected_ship_date"),
            InventoryCopy.received_at.label("received_at"),
            asset_state_expr,
            case((InventoryCopy.order_status == "received", True), else_=False).label("is_in_hand"),
        )
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.user_id == current_user.id)
    )


def build_inventory_detail_query(current_user: User):
    gain_loss_expr = gain_loss_expression().label("gain_loss")
    asset_state_expr = _asset_state_case_expression().label("asset_state")

    return (
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.copy_number.label("copy_number"),
            InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
            ComicTitle.name.label("title"),
            Publisher.name.label("publisher"),
            ComicIssue.issue_number.label("issue_number"),
            ComicIssue.id.label("canonical_issue_id"),
            Variant.cover_name.label("cover_name"),
            Variant.printing.label("printing"),
            Variant.ratio.label("ratio"),
            Variant.variant_type.label("variant_type"),
            Variant.cover_artist.label("cover_artist"),
            Order.retailer.label("retailer"),
            Order.order_date.label("order_date"),
            Order.source_type.label("source_type"),
            InventoryCopy.acquisition_cost.label("acquisition_cost"),
            InventoryCopy.current_fmv.label("current_fmv"),
            InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
            InventoryCopy.canonical_series_id.label("canonical_series_id"),
            gain_loss_expr,
            InventoryCopy.grade_status.label("grade_status"),
            InventoryCopy.hold_status.label("hold_status"),
            InventoryCopy.star_rating.label("star_rating"),
            InventoryCopy.condition_notes.label("condition_notes"),
            Order.id.label("order_id"),
            OrderItem.id.label("order_item_id"),
            Variant.id.label("variant_id"),
            Order.order_date.label("purchase_date"),
            InventoryCopy.release_date.label("release_date"),
            InventoryCopy.release_year.label("release_year"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.expected_ship_date.label("expected_ship_date"),
            InventoryCopy.received_at.label("received_at"),
            asset_state_expr,
            case((InventoryCopy.order_status == "received", True), else_=False).label("is_in_hand"),
            InventoryCopy.created_at.label("created_at"),
        )
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.user_id == current_user.id)
    )


def apply_inventory_filters(
    stmt,
    *,
    search: str | None,
    publisher: str | None,
    hold_status: str | None,
    grade_status: str | None,
    release_year: int | None,
    release_calendar: ReleaseCalendarPresence | None,
    asset_state: str | None,
):
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                ComicTitle.name.ilike(search_term),
                Publisher.name.ilike(search_term),
                ComicIssue.issue_number.ilike(search_term),
                Variant.cover_name.ilike(search_term),
            )
        )

    if publisher:
        stmt = stmt.where(Publisher.name == publisher)

    if hold_status:
        stmt = stmt.where(InventoryCopy.hold_status == hold_status)

    if grade_status:
        stmt = stmt.where(InventoryCopy.grade_status == grade_status)

    if release_year is not None:
        stmt = stmt.where(InventoryCopy.release_year == release_year)

    if release_calendar == "present":
        stmt = stmt.where(InventoryCopy.release_date.is_not(None))
    elif release_calendar == "missing":
        stmt = stmt.where(InventoryCopy.release_date.is_(None))

    if asset_state == "in_hand":
        stmt = stmt.where(InventoryCopy.order_status == "received")
    elif asset_state == "ordered_not_received":
        stmt = stmt.where(
            InventoryCopy.order_status.in_(("ordered", "shipped")),
            InventoryCopy.order_status != "cancelled",
        )
    elif asset_state == "preorder_not_released_yet":
        stmt = stmt.where(
            or_(
                InventoryCopy.release_status == "not_released_yet",
                InventoryCopy.order_status == "preordered",
            ),
            InventoryCopy.order_status != "cancelled",
        )
    elif asset_state == "cancelled":
        stmt = stmt.where(InventoryCopy.order_status == "cancelled")

    return stmt


def apply_inventory_sort(stmt, sort_by: str | None, sort_dir: str):
    resolved_sort = sort_by or "purchase_date"
    if resolved_sort not in SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail="Invalid sort_by value")

    sort_column_map = {
        "title": ComicTitle.name,
        "publisher": Publisher.name,
        "purchase_date": Order.order_date,
        "acquisition_cost": InventoryCopy.acquisition_cost,
        "current_fmv": InventoryCopy.current_fmv,
        "gain_loss": case(
            (
                InventoryCopy.current_fmv.is_not(None),
                InventoryCopy.current_fmv - InventoryCopy.acquisition_cost,
            ),
            else_=None,
        ),
        "star_rating": InventoryCopy.star_rating,
    }
    sort_column = sort_column_map[resolved_sort]
    direction = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    tie_breaker = InventoryCopy.id.desc() if sort_dir == "desc" else InventoryCopy.id.asc()

    return stmt.order_by(direction, tie_breaker)


def build_portfolio_performance_query(current_user: User):
    return (
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            ComicTitle.name.label("title"),
            Publisher.name.label("publisher"),
            ComicIssue.issue_number.label("issue_number"),
            Variant.cover_name.label("cover_name"),
            InventoryCopy.current_fmv.label("current_fmv"),
            gain_loss_expression().label("gain_loss"),
        )
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.user_id == current_user.id)
    )


def find_duplicate_inventory_candidates(
    session: Session,
    *,
    publisher: str | None = None,
    series_title: str | None = None,
    min_count: int = 2,
    review_status: str | None = None,
) -> list[OpsInventoryDuplicateCandidateGroup]:
    duplicate_key_stmt = (
        select(InventoryCopy.metadata_identity_key)
        .where(
            InventoryCopy.metadata_identity_key.is_not(None),
            InventoryCopy.metadata_identity_key != "",
        )
        .group_by(InventoryCopy.metadata_identity_key)
        .having(func.count(InventoryCopy.id) >= min_count)
    )
    duplicate_keys = [key for key in session.exec(duplicate_key_stmt).all() if key]
    if not duplicate_keys:
        return []

    rows = session.exec(
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
            InventoryCopy.acquisition_cost.label("acquisition_cost"),
            InventoryCopy.created_at.label("created_at"),
            User.id.label("user_id"),
            User.email.label("user_email"),
            Order.id.label("order_id"),
            Order.retailer.label("retailer"),
            Order.order_date.label("order_date"),
        )
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(User, User.id == InventoryCopy.user_id, isouter=True)
        .where(InventoryCopy.metadata_identity_key.in_(duplicate_keys))
        .order_by(
            InventoryCopy.metadata_identity_key.asc(),
            InventoryCopy.created_at.asc(),
            InventoryCopy.id.asc(),
        )
    ).all()

    grouped_candidates: dict[str, list] = {}
    for row in rows:
        grouped_candidates.setdefault(row.metadata_identity_key, []).append(row)

    duplicate_groups: list[OpsInventoryDuplicateCandidateGroup] = []
    for metadata_identity_key, grouped_rows in grouped_candidates.items():
        group_publisher, group_series_title, group_issue_number, group_variant = (
            _split_metadata_identity_key(metadata_identity_key)
        )
        if publisher and group_publisher != publisher:
            continue
        if series_title and group_series_title != series_title:
            continue

        duplicate_groups.append(
            OpsInventoryDuplicateCandidateGroup(
                metadata_identity_key=metadata_identity_key,
                count=len(grouped_rows),
                publisher=group_publisher,
                series_title=group_series_title,
                issue_number=group_issue_number,
                variant=group_variant,
                review_status="pending",
                notes=None,
                reviewed_at=None,
                reviewed_by=None,
                copies=[
                    OpsInventoryDuplicateCopyRow(
                        inventory_copy_id=row.inventory_copy_id,
                        user_id=row.user_id,
                        user_email=row.user_email,
                        order_id=row.order_id,
                        retailer=row.retailer,
                        order_date=row.order_date,
                        acquisition_cost=str(row.acquisition_cost),
                        created_at=row.created_at,
                    )
                    for row in grouped_rows
                ],
            )
        )

    identity_keys = [group.metadata_identity_key for group in duplicate_groups]
    reviews_map = load_reviews_for_keys(session, identity_keys)
    reviewer_ids = {
        row.reviewed_by_user_id
        for row in reviews_map.values()
        if row.reviewed_by_user_id is not None
    }
    emails_map = reviewer_email_map(session, reviewer_ids)

    enriched_groups: list[OpsInventoryDuplicateCandidateGroup] = []
    for group in duplicate_groups:
        review = reviews_map.get(group.metadata_identity_key)
        if review is None:
            resolved_review_status = "pending"
            reviewed_notes = None
            reviewed_at_value = None
            reviewed_by_value = None
        else:
            resolved_review_status = review.review_status
            reviewed_notes = review.notes
            reviewed_at_value = review.reviewed_at
            reviewed_by_value = (
                emails_map.get(review.reviewed_by_user_id)
                if review.reviewed_by_user_id is not None
                else None
            )

        enriched_groups.append(
            group.model_copy(
                update={
                    "review_status": resolved_review_status,
                    "notes": reviewed_notes,
                    "reviewed_at": reviewed_at_value,
                    "reviewed_by": reviewed_by_value,
                }
            )
        )

    if review_status is not None:
        enriched_groups = [grp for grp in enriched_groups if grp.review_status == review_status]

    enriched_groups.sort(
        key=lambda group: (
            -group.count,
            group.metadata_identity_key,
            group.copies[0].inventory_copy_id,
        )
    )
    return enriched_groups


def list_inventory(
    session: Session,
    current_user: User,
    *,
    page: int,
    page_size: int,
    search: str | None,
    publisher: str | None,
    hold_status: str | None,
    grade_status: str | None,
    release_year: int | None,
    release_calendar: ReleaseCalendarPresence | None,
    asset_state: str | None,
    intelligence_health: str | None,
    ownership_intel: str | None,
    valuation_scope: str | None = None,
    fmv_confidence_bucket: str | None = None,
    fmv_liquidity_bucket: str | None = None,
    fmv_stale_data: bool | None = None,
    fmv_currency_code: str | None = None,
    ownership_state: str | None = None,
    risk_priority: str | None,
    risk_type: str | None,
    needs_attention: bool,
    action_attention: bool,
    action_center_category: str | None,
    arrival_classification: OrderArrivalClassification | None,
    sort_by: str | None,
    sort_dir: str,
) -> InventoryListResponse:
    _, _, _, intel_signals = compute_inventory_intelligence(
        session,
        current_user=current_user,
        include_signals=True,
    )
    _, dup_attachments = duplicate_ownership_inventory_context_for_owner(
        session,
        user=current_user,
        dup_scan_classification="all",
    )
    _, run_attachments = run_detection_inventory_context_for_owner(
        session,
        user=current_user,
    )
    _, _all_risks, risks_by_inventory = compute_inventory_risks(
        session,
        current_user=current_user,
    )

    arrival_by_inventory = batch_order_arrival_classifications(session, user_id=int(current_user.id))

    actions_by_inventory: defaultdict[int, list] = defaultdict(list)
    for act in build_inventory_action_items(
        session,
        risk_rows=_all_risks,
        signals_map=intel_signals,
        arrival_map=arrival_by_inventory,
        user_id_scope=int(current_user.id),
    ):
        actions_by_inventory[act.inventory_copy_id].append(act)

    action_attention_allowlist: set[int] | None = None
    if action_attention:
        action_attention_allowlist = {
            inv_id for inv_id, grp in actions_by_inventory.items() if attachment_from_items(grp).urgent_lane
        }
        if not action_attention_allowlist:
            return InventoryListResponse(page=page, page_size=page_size, total=0, items=[])

    action_category_allowlist: set[int] | None = None
    if action_center_category:
        action_category_allowlist = {
            inv_id for inv_id, grp in actions_by_inventory.items()
            if any(str(a.action_category) == action_center_category for a in grp)
        }
        if not action_category_allowlist:
            return InventoryListResponse(page=page, page_size=page_size, total=0, items=[])

    def inventory_matches_risk_filters(inv_id: int) -> bool:
        if not (risk_priority or risk_type or needs_attention):
            return True
        row_risks = risks_by_inventory.get(inv_id, [])
        if not row_risks:
            return False
        for risk in row_risks:
            if risk_priority and risk.priority != risk_priority:
                continue
            if risk_type and risk.risk_type != risk_type:
                continue
            if needs_attention and risk.priority not in ("critical", "high"):
                continue
            return True
        return False

    intel_allowlist: set[int] | None = None
    if intelligence_health or ownership_intel or ownership_state:
        intel_allowlist = set()
        for inv_id, sig in intel_signals.items():
            if intelligence_health:
                if intelligence_health == "not_healthy":
                    if sig.inventory_health == "healthy":
                        continue
                elif sig.inventory_health != intelligence_health:
                    continue
            ownership_filter = ownership_state or ownership_intel
            if ownership_filter and sig.ownership_state != ownership_filter:
                continue
            intel_allowlist.add(inv_id)

        if not intel_allowlist:
            return InventoryListResponse(page=page, page_size=page_size, total=0, items=[])

    risk_allowlist: set[int] | None = None
    if risk_priority or risk_type or needs_attention:
        risk_allowlist = {inv_id for inv_id in risks_by_inventory if inventory_matches_risk_filters(inv_id)}
        if not risk_allowlist:
            return InventoryListResponse(page=page, page_size=page_size, total=0, items=[])

    arrival_allowlist: set[int] | None = None
    if arrival_classification:
        arrival_allowlist = {
            inv_id for inv_id, entries in arrival_by_inventory.items() if arrival_classification in entries
        }
        if not arrival_allowlist:
            return InventoryListResponse(page=page, page_size=page_size, total=0, items=[])

    filtered_stmt = apply_inventory_filters(
        build_inventory_base_query(current_user),
        search=search,
        publisher=publisher,
        hold_status=hold_status,
        grade_status=grade_status,
        release_year=release_year,
        release_calendar=release_calendar,
        asset_state=asset_state,
    )
    total_stmt = (
        select(func.count())
        .select_from(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.user_id == current_user.id)
    )
    total_stmt = apply_inventory_filters(
        total_stmt,
        search=search,
        publisher=publisher,
        hold_status=hold_status,
        grade_status=grade_status,
        release_year=release_year,
        release_calendar=release_calendar,
        asset_state=asset_state,
    )

    if intel_allowlist is not None:
        id_tuple = tuple(sorted(intel_allowlist))
        filtered_stmt = filtered_stmt.where(InventoryCopy.id.in_(id_tuple))
        total_stmt = total_stmt.where(InventoryCopy.id.in_(id_tuple))

    if risk_allowlist is not None:
        id_tuple = tuple(sorted(risk_allowlist))
        filtered_stmt = filtered_stmt.where(InventoryCopy.id.in_(id_tuple))
        total_stmt = total_stmt.where(InventoryCopy.id.in_(id_tuple))

    if arrival_allowlist is not None:
        id_tuple = tuple(sorted(arrival_allowlist))
        filtered_stmt = filtered_stmt.where(InventoryCopy.id.in_(id_tuple))
        total_stmt = total_stmt.where(InventoryCopy.id.in_(id_tuple))

    if action_attention_allowlist is not None:
        id_tuple = tuple(sorted(action_attention_allowlist))
        filtered_stmt = filtered_stmt.where(InventoryCopy.id.in_(id_tuple))
        total_stmt = total_stmt.where(InventoryCopy.id.in_(id_tuple))

    if action_category_allowlist is not None:
        id_tuple = tuple(sorted(action_category_allowlist))
        filtered_stmt = filtered_stmt.where(InventoryCopy.id.in_(id_tuple))
        total_stmt = total_stmt.where(InventoryCopy.id.in_(id_tuple))

    rows = session.exec(apply_inventory_sort(filtered_stmt, sort_by, sort_dir)).all()
    inventory_rows: list[InventoryRow] = []
    for row in rows:
        row_map = dict(row._mapping)
        inv_pk = int(row_map["inventory_copy_id"])
        row_map["inventory_intelligence"] = intel_signals.get(inv_pk)
        row_map["ownership_state"] = intel_signals.get(inv_pk).ownership_state if intel_signals.get(inv_pk) else None
        row_map["duplicate_ownership"] = dup_attachments.get(inv_pk)
        row_map["run_detection"] = run_attachments.get(inv_pk)
        row_map["inventory_risks"] = risks_by_inventory.get(inv_pk, [])
        row_map["order_arrival_classifications"] = arrival_by_inventory.get(inv_pk, [])
        row_map["inventory_action_center"] = attachment_from_items(actions_by_inventory.get(inv_pk, []))
        fmv_attachment = build_inventory_fmv_attachment(session, row=row_map, include_detail=False)
        row_map["current_market_fmv"] = fmv_attachment.current_market_fmv
        row_map["fmv_snapshot_id"] = fmv_attachment.fmv_snapshot_id
        row_map["fmv_method"] = fmv_attachment.fmv_method
        row_map["fmv_confidence_bucket"] = fmv_attachment.fmv_confidence_bucket
        row_map["fmv_liquidity_bucket"] = fmv_attachment.fmv_liquidity_bucket
        row_map["fmv_volatility_bucket"] = fmv_attachment.fmv_volatility_bucket
        row_map["fmv_stale_data"] = fmv_attachment.fmv_stale_data
        row_map["fmv_currency_code"] = fmv_attachment.fmv_currency_code
        row_map["valuation_scope"] = fmv_attachment.valuation_scope
        row_map["valuation_evidence_json"] = fmv_attachment.valuation_evidence_json
        inventory_rows.append(InventoryRow.model_validate(row_map))

    def _fmv_row_matches(row: InventoryRow) -> bool:
        if valuation_scope is not None and row.valuation_scope != valuation_scope:
            return False
        if fmv_confidence_bucket is not None and row.fmv_confidence_bucket != fmv_confidence_bucket:
            return False
        if fmv_liquidity_bucket is not None and row.fmv_liquidity_bucket != fmv_liquidity_bucket:
            return False
        if fmv_stale_data is not None and bool(row.fmv_stale_data) != fmv_stale_data:
            return False
        if fmv_currency_code is not None and (row.fmv_currency_code or "").upper() != fmv_currency_code.strip().upper():
            return False
        return True

    filtered_rows = [row for row in inventory_rows if _fmv_row_matches(row)]
    total = len(filtered_rows)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered_rows[start:end]

    return InventoryListResponse(page=page, page_size=page_size, total=total, items=items)


def inventory_summary(session: Session, current_user: User) -> InventorySummaryResponse:
    zero = Decimal("0.00")
    summary_stmt = select(
        func.count(InventoryCopy.id).label("total_copies"),
        func.coalesce(
            func.sum(case((InventoryCopy.order_status == "received", 1), else_=0)),
            0,
        ).label("in_hand_copies"),
        func.coalesce(
            func.sum(
                case(
                    (InventoryCopy.order_status.in_(("ordered", "shipped")), 1),
                    else_=0,
                )
            ),
            0,
        ).label("ordered_not_received_copies"),
        func.coalesce(
            func.sum(
                case(
                    (
                        or_(
                            InventoryCopy.release_status == "not_released_yet",
                            InventoryCopy.order_status == "preordered",
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("preordered_copies"),
        func.coalesce(
            func.sum(case((InventoryCopy.order_status == "cancelled", 1), else_=0)),
            0,
        ).label("cancelled_copies"),
        func.coalesce(func.sum(InventoryCopy.acquisition_cost), zero).label("total_cost_basis"),
        func.coalesce(func.sum(func.coalesce(InventoryCopy.current_fmv, zero)), zero).label(
            "total_current_fmv"
        ),
        func.coalesce(
            func.sum(
                func.coalesce(InventoryCopy.current_fmv, zero) - InventoryCopy.acquisition_cost
            ),
            zero,
        ).label("total_unrealized_gain_loss"),
        func.coalesce(
            func.sum(case((InventoryCopy.grade_status == "raw", 1), else_=0)),
            0,
        ).label("raw_count"),
        func.coalesce(
            func.sum(case((InventoryCopy.grade_status != "raw", 1), else_=0)),
            0,
        ).label("graded_count"),
        func.coalesce(
            func.sum(case((InventoryCopy.hold_status == "hold", 1), else_=0)),
            0,
        ).label("hold_count"),
        func.coalesce(
            func.sum(case((InventoryCopy.hold_status == "sell", 1), else_=0)),
            0,
        ).label("sell_count"),
    ).where(InventoryCopy.user_id == current_user.id)

    summary = session.exec(summary_stmt).one()

    return InventorySummaryResponse(
        total_copies=summary.total_copies,
        in_hand_copies=summary.in_hand_copies,
        ordered_not_received_copies=summary.ordered_not_received_copies,
        preordered_copies=summary.preordered_copies,
        cancelled_copies=summary.cancelled_copies,
        total_cost_basis=quantize_money(summary.total_cost_basis),
        total_current_fmv=quantize_money(summary.total_current_fmv),
        total_unrealized_gain_loss=quantize_money(summary.total_unrealized_gain_loss),
        raw_count=summary.raw_count,
        graded_count=summary.graded_count,
        hold_count=summary.hold_count,
        sell_count=summary.sell_count,
    )


def get_inventory_copy_detail(
    session: Session,
    current_user: User,
    inventory_copy_id: int,
) -> InventoryDetailResponse:
    row = session.exec(
        build_inventory_detail_query(current_user).where(InventoryCopy.id == inventory_copy_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    merged = dict(row._mapping)
    merged["cover_images"] = list_cover_reads_for_inventory(session, inventory_copy_id)
    _, _, _, intelligence_signals = compute_inventory_intelligence(
        session,
        current_user=current_user,
        include_signals=True,
    )
    _, dup_attachments = duplicate_ownership_inventory_context_for_owner(
        session,
        user=current_user,
        dup_scan_classification="all",
    )
    merged["inventory_intelligence"] = intelligence_signals.get(inventory_copy_id)
    merged["ownership_state"] = intelligence_signals.get(inventory_copy_id).ownership_state if intelligence_signals.get(inventory_copy_id) else None
    merged["duplicate_ownership"] = dup_attachments.get(inventory_copy_id)
    _, run_attachments = run_detection_inventory_context_for_owner(
        session,
        user=current_user,
    )
    merged["run_detection"] = run_attachments.get(inventory_copy_id)
    arrival_map = batch_order_arrival_classifications(session, user_id=int(current_user.id))
    _, risks_flat, risk_attach_map = compute_inventory_risks(session, current_user=current_user)
    merged["inventory_risks"] = risk_attach_map.get(inventory_copy_id, [])
    ledger = build_inventory_action_items(
        session,
        risk_rows=risks_flat,
        signals_map=intelligence_signals,
        arrival_map=arrival_map,
        user_id_scope=int(current_user.id),
    )
    scoped_actions = [a for a in ledger if a.inventory_copy_id == inventory_copy_id]
    merged["inventory_action_center"] = attachment_from_items(scoped_actions)
    merged["order_arrival_classifications"] = classifications_for_inventory_copy(
        session,
        inventory_copy_id=inventory_copy_id,
        user_id=int(current_user.id),
    )
    fmv_attachment = build_inventory_fmv_attachment(session, row=merged, include_detail=True)
    merged["current_market_fmv"] = fmv_attachment.current_market_fmv
    merged["fmv_snapshot_id"] = fmv_attachment.fmv_snapshot_id
    merged["fmv_method"] = fmv_attachment.fmv_method
    merged["fmv_confidence_bucket"] = fmv_attachment.fmv_confidence_bucket
    merged["fmv_liquidity_bucket"] = fmv_attachment.fmv_liquidity_bucket
    merged["fmv_volatility_bucket"] = fmv_attachment.fmv_volatility_bucket
    merged["fmv_stale_data"] = fmv_attachment.fmv_stale_data
    merged["fmv_currency_code"] = fmv_attachment.fmv_currency_code
    merged["valuation_scope"] = fmv_attachment.valuation_scope
    merged["valuation_evidence_json"] = fmv_attachment.valuation_evidence_json
    merged["inventory_fmv"] = fmv_attachment
    merged["originating_scan_session"] = originating_scan_session_for_inventory_copy(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
    )
    merged["grading_candidate"] = inventory_grading_badge(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["grading_spread"] = inventory_grading_spread_badge(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["grading_roi"] = inventory_grading_roi_badge(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["grading_submission"] = inventory_grading_submission_badge(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["grading_reconciliation"] = inventory_grading_reconciliation_badge(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["grading_recommendation"] = inventory_grading_recommendation_badge(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["grading_risk"] = inventory_grading_risk_badge(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["portfolio_intelligence"] = inventory_portfolio_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
        publisher_display_name=str(merged.get("publisher") or ""),
    )
    merged["duplicate_intelligence"] = inventory_duplicate_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["portfolio_liquidity"] = inventory_portfolio_liquidity_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["acquisition_priority"] = inventory_acquisition_priority_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["concentration_risk"] = inventory_concentration_risk_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["portfolio_recommendation"] = inventory_portfolio_recommendation_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["market_acquisition_score"] = inventory_market_acquisition_score_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["market_acquisition_signal"] = inventory_market_signal_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["market_acquisition_opportunity"] = inventory_market_opportunity_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_item_id=inventory_copy_id,
    )
    merged["portfolio_market_coupling"] = inventory_portfolio_market_coupling_teaser(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
    )
    return InventoryDetailResponse.model_validate(merged)


def get_inventory_fmv_history(
    session: Session,
    current_user: User,
    inventory_copy_id: int,
) -> list[InventoryFmvSnapshotResponse]:
    inventory_copy = session.exec(
        select(InventoryCopy.id).where(
            InventoryCopy.id == inventory_copy_id,
            InventoryCopy.user_id == current_user.id,
        )
    ).first()
    if inventory_copy is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    rows = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id == inventory_copy_id)
        .order_by(InventoryFmvSnapshot.changed_at.desc(), InventoryFmvSnapshot.id.desc())
    ).all()
    return [InventoryFmvSnapshotResponse.model_validate(row.model_dump()) for row in rows]


def portfolio_performance(session: Session, current_user: User) -> PortfolioPerformanceResponse:
    zero = Decimal("0.00")
    summary_stmt = select(
        func.coalesce(func.sum(InventoryCopy.acquisition_cost), zero).label("total_cost_basis"),
        func.coalesce(func.sum(func.coalesce(InventoryCopy.current_fmv, zero)), zero).label(
            "total_current_fmv"
        ),
        func.coalesce(
            func.sum(
                func.coalesce(InventoryCopy.current_fmv, zero) - InventoryCopy.acquisition_cost
            ),
            zero,
        ).label("total_unrealized_gain_loss"),
    ).where(InventoryCopy.user_id == current_user.id)
    summary = session.exec(summary_stmt).one()

    top_gainers_rows = session.exec(
        build_portfolio_performance_query(current_user)
        .where(InventoryCopy.current_fmv.is_not(None))
        .where(gain_loss_expression() > 0)
        .order_by(gain_loss_expression().desc(), InventoryCopy.id.asc())
        .limit(5)
    ).all()
    top_losers_rows = session.exec(
        build_portfolio_performance_query(current_user)
        .where(InventoryCopy.current_fmv.is_not(None))
        .where(gain_loss_expression() < 0)
        .order_by(gain_loss_expression().asc(), InventoryCopy.id.asc())
        .limit(5)
    ).all()
    highest_value_rows = session.exec(
        build_portfolio_performance_query(current_user)
        .where(InventoryCopy.current_fmv.is_not(None))
        .order_by(InventoryCopy.current_fmv.desc(), InventoryCopy.id.asc())
        .limit(5)
    ).all()

    return PortfolioPerformanceResponse(
        total_cost_basis=quantize_money(summary.total_cost_basis),
        total_current_fmv=quantize_money(summary.total_current_fmv),
        total_unrealized_gain_loss=quantize_money(summary.total_unrealized_gain_loss),
        top_gainers=[
            PortfolioPerformanceItem.model_validate(row._mapping) for row in top_gainers_rows
        ],
        top_losers=[
            PortfolioPerformanceItem.model_validate(row._mapping) for row in top_losers_rows
        ],
        highest_value_books=[
            PortfolioPerformanceItem.model_validate(row._mapping) for row in highest_value_rows
        ],
    )


def maybe_add_fmv_snapshot(
    session: Session,
    inventory_copy: InventoryCopy,
    updates: InventoryUpdate,
) -> None:
    update_data = updates.model_dump(exclude_unset=True)
    if "current_fmv" not in update_data:
        return

    new_fmv = update_data["current_fmv"]
    previous_fmv = inventory_copy.current_fmv
    if new_fmv is None or new_fmv == previous_fmv:
        return

    session.add(
        InventoryFmvSnapshot(
            inventory_copy_id=inventory_copy.id,
            previous_fmv=previous_fmv,
            new_fmv=new_fmv,
        )
    )


def apply_inventory_updates(copy: InventoryCopy, updates: InventoryUpdate) -> None:
    update_data = updates.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(copy, field_name, value)
    if "order_status" not in update_data and "received_at" in update_data and copy.received_at is not None:
        copy.order_status = "received"
    copy_asset_state = derive_asset_state(
        release_status=copy.release_status,
        order_status=copy.order_status,
    )
    if copy_asset_state == "preorder_not_released_yet" and copy.expected_ship_date is None:
        copy.expected_ship_date = copy.release_date


def update_inventory_copy(
    session: Session,
    current_user: User,
    inventory_copy_id: int,
    updates: InventoryUpdate,
) -> InventoryRow:
    inventory_copy = session.exec(
        select(InventoryCopy).where(
            InventoryCopy.id == inventory_copy_id,
            InventoryCopy.user_id == current_user.id,
        )
    ).first()
    if inventory_copy is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    maybe_add_fmv_snapshot(session, inventory_copy, updates)
    apply_inventory_updates(inventory_copy, updates)
    session.add(inventory_copy)
    session.commit()

    row_stmt = build_inventory_base_query(current_user).where(InventoryCopy.id == inventory_copy_id)
    row = session.exec(row_stmt).one()
    row_map = dict(row._mapping)
    _, _, _, sigs = compute_inventory_intelligence(
        session,
        current_user=current_user,
        include_signals=True,
    )
    _, dup_attachments = duplicate_ownership_inventory_context_for_owner(
        session,
        user=current_user,
        dup_scan_classification="all",
    )
    _, run_attachments = run_detection_inventory_context_for_owner(
        session,
        user=current_user,
    )
    row_map["inventory_intelligence"] = sigs.get(inventory_copy_id)
    row_map["duplicate_ownership"] = dup_attachments.get(inventory_copy_id)
    row_map["run_detection"] = run_attachments.get(inventory_copy_id)
    return InventoryRow.model_validate(row_map)


def bulk_update_inventory(
    session: Session,
    current_user: User,
    payload: BulkInventoryUpdateRequest,
) -> BulkInventoryUpdateResponse:
    copies = session.exec(
        select(InventoryCopy).where(InventoryCopy.id.in_(payload.inventory_copy_ids))
    ).all()

    if len(copies) != len(payload.inventory_copy_ids):
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    if any(copy.user_id != current_user.id for copy in copies):
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    for copy in copies:
        maybe_add_fmv_snapshot(session, copy, payload.updates)
        apply_inventory_updates(copy, payload.updates)
        session.add(copy)

    session.commit()
    return BulkInventoryUpdateResponse(updated_count=len(copies))
