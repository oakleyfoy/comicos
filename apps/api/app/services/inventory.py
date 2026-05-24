from decimal import Decimal

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
from app.schemas.ops import (
    OpsInventoryDuplicateCandidateGroup,
    OpsInventoryDuplicateCopyRow,
)
from app.services.duplicate_candidate_reviews import (
    load_reviews_for_keys,
    reviewer_email_map,
)
from app.services.cover_images import list_cover_reads_for_inventory
from app.services.duplicate_ownership_intelligence import duplicate_ownership_inventory_context_for_owner
from app.services.inventory_intelligence import compute_inventory_intelligence
from app.services.inventory_risks import compute_inventory_risks
from app.services.order_states import derive_asset_state
from app.services.run_detection import run_detection_inventory_context_for_owner

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
            Variant.cover_name.label("cover_name"),
            Variant.printing.label("printing"),
            Variant.ratio.label("ratio"),
            Variant.variant_type.label("variant_type"),
            Variant.cover_artist.label("cover_artist"),
            Order.retailer.label("retailer"),
            Order.order_date.label("order_date"),
            InventoryCopy.acquisition_cost.label("acquisition_cost"),
            InventoryCopy.current_fmv.label("current_fmv"),
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
            ComicTitle.name.label("title"),
            Publisher.name.label("publisher"),
            ComicIssue.issue_number.label("issue_number"),
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
    risk_priority: str | None,
    risk_type: str | None,
    needs_attention: bool,
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
    if intelligence_health or ownership_intel:
        intel_allowlist = set()
        for inv_id, sig in intel_signals.items():
            if intelligence_health:
                if intelligence_health == "not_healthy":
                    if sig.inventory_health == "healthy":
                        continue
                elif sig.inventory_health != intelligence_health:
                    continue
            if ownership_intel and sig.ownership_state != ownership_intel:
                continue
            intel_allowlist.add(inv_id)

        if not intel_allowlist:
            return InventoryListResponse(page=page, page_size=page_size, total=0, items=[])

    risk_allowlist: set[int] | None = None
    if risk_priority or risk_type or needs_attention:
        risk_allowlist = {inv_id for inv_id in risks_by_inventory if inventory_matches_risk_filters(inv_id)}
        if not risk_allowlist:
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

    paginated_stmt = apply_inventory_sort(filtered_stmt, sort_by, sort_dir).offset(
        (page - 1) * page_size
    ).limit(page_size)

    total = session.exec(total_stmt).one()
    rows = session.exec(paginated_stmt).all()
    items = []
    for row in rows:
        row_map = dict(row._mapping)
        inv_pk = int(row_map["inventory_copy_id"])
        row_map["inventory_intelligence"] = intel_signals.get(inv_pk)
        row_map["duplicate_ownership"] = dup_attachments.get(inv_pk)
        row_map["run_detection"] = run_attachments.get(inv_pk)
        row_map["inventory_risks"] = risks_by_inventory.get(inv_pk, [])
        items.append(InventoryRow.model_validate(row_map))

    return InventoryListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=items,
    )


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
    merged["duplicate_ownership"] = dup_attachments.get(inventory_copy_id)
    _, run_attachments = run_detection_inventory_context_for_owner(
        session,
        user=current_user,
    )
    merged["run_detection"] = run_attachments.get(inventory_copy_id)
    _, _, risk_attach_map = compute_inventory_risks(session, current_user=current_user)
    merged["inventory_risks"] = risk_attach_map.get(inventory_copy_id, [])
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
