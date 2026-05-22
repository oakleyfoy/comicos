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
)

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


def gain_loss_expression():
    return case(
        (
            InventoryCopy.current_fmv.is_not(None),
            InventoryCopy.current_fmv - InventoryCopy.acquisition_cost,
        ),
        else_=None,
    )


def build_inventory_base_query(current_user: User):
    gain_loss_expr = gain_loss_expression().label("gain_loss")

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
    sort_by: str | None,
    sort_dir: str,
) -> InventoryListResponse:
    filtered_stmt = apply_inventory_filters(
        build_inventory_base_query(current_user),
        search=search,
        publisher=publisher,
        hold_status=hold_status,
        grade_status=grade_status,
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
    )

    paginated_stmt = apply_inventory_sort(filtered_stmt, sort_by, sort_dir).offset(
        (page - 1) * page_size
    ).limit(page_size)

    total = session.exec(total_stmt).one()
    rows = session.exec(paginated_stmt).all()
    items = [InventoryRow.model_validate(row._mapping) for row in rows]

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

    return InventoryDetailResponse.model_validate(row._mapping)


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
    return InventoryRow.model_validate(row._mapping)


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
