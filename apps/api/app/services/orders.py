from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    Order,
    OrderItem,
    Publisher,
    User,
    Variant,
)
from app.schemas.orders import (
    OrderCreate,
    OrderCreateResponse,
    OrderDetailItem,
    OrderDetailResponse,
    OrderItemCreate,
    OrderListResponse,
    OrderListRow,
)

CENT = Decimal("0.01")
ONE_HUNDRED = Decimal("100")
ORDER_SORTABLE_FIELDS = {"order_date", "retailer", "total_amount", "created_at"}


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value: Decimal) -> int:
    return int((quantize_money(value) * ONE_HUNDRED).to_integral_value())


def from_cents(value: int) -> Decimal:
    return Decimal(value) / ONE_HUNDRED


def allocate_by_subtotal(subtotals: list[Decimal], total_amount: Decimal) -> list[Decimal]:
    total_cents = to_cents(total_amount)
    subtotal_cents = [to_cents(subtotal) for subtotal in subtotals]
    total_subtotal_cents = sum(subtotal_cents)

    if total_cents == 0:
        return [Decimal("0.00") for _ in subtotals]

    if total_subtotal_cents == 0:
        base_share, remainder = divmod(total_cents, len(subtotals))
        cents = [base_share for _ in subtotals]
        for index in range(remainder):
            cents[index] += 1
        return [from_cents(value) for value in cents]

    weighted: list[tuple[int, int, int]] = []
    allocated_cents = 0
    for index, subtotal in enumerate(subtotal_cents):
        numerator = total_cents * subtotal
        base = numerator // total_subtotal_cents
        remainder = numerator % total_subtotal_cents
        weighted.append((index, base, remainder))
        allocated_cents += base

    remaining = total_cents - allocated_cents
    weighted.sort(key=lambda item: (-item[2], item[0]))
    cents_by_index = {index: base for index, base, _ in weighted}
    for index, _, _ in weighted[:remaining]:
        cents_by_index[index] += 1

    return [from_cents(cents_by_index[index]) for index in range(len(subtotals))]


def get_or_create_publisher(session: Session, name: str) -> Publisher:
    publisher = session.exec(select(Publisher).where(Publisher.name == name)).first()
    if publisher is not None:
        return publisher

    publisher = Publisher(name=name)
    session.add(publisher)
    session.flush()
    return publisher


def get_or_create_title(session: Session, publisher_id: int, name: str) -> ComicTitle:
    title = session.exec(
        select(ComicTitle).where(
            ComicTitle.publisher_id == publisher_id,
            ComicTitle.name == name,
        )
    ).first()
    if title is not None:
        return title

    title = ComicTitle(publisher_id=publisher_id, name=name)
    session.add(title)
    session.flush()
    return title


def get_or_create_issue(session: Session, comic_title_id: int, issue_number: str) -> ComicIssue:
    issue = session.exec(
        select(ComicIssue).where(
            ComicIssue.comic_title_id == comic_title_id,
            ComicIssue.issue_number == issue_number,
        )
    ).first()
    if issue is not None:
        return issue

    issue = ComicIssue(comic_title_id=comic_title_id, issue_number=issue_number)
    session.add(issue)
    session.flush()
    return issue


def get_or_create_variant(session: Session, comic_issue_id: int, item: OrderItemCreate) -> Variant:
    variant = session.exec(
        select(Variant).where(
            Variant.comic_issue_id == comic_issue_id,
            Variant.cover_name == item.cover_name,
            Variant.printing == item.printing,
            Variant.ratio == item.ratio,
            Variant.variant_type == item.variant_type,
            Variant.cover_artist == item.cover_artist,
        )
    ).first()
    if variant is not None:
        return variant

    variant = Variant(
        comic_issue_id=comic_issue_id,
        cover_name=item.cover_name,
        printing=item.printing,
        ratio=item.ratio,
        variant_type=item.variant_type,
        cover_artist=item.cover_artist,
    )
    session.add(variant)
    session.flush()
    return variant


def build_orders_base_query(current_user: User):
    return (
        select(
            Order.id.label("order_id"),
            Order.retailer.label("retailer"),
            Order.order_date.label("order_date"),
            Order.source_type.label("source_type"),
            Order.shipping_amount.label("shipping_amount"),
            Order.tax_amount.label("tax_amount"),
            Order.total_amount.label("total_amount"),
            func.count(OrderItem.id).label("total_items"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("total_copies"),
            Order.created_at.label("created_at"),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Variant, OrderItem.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(Order.user_id == current_user.id)
        .group_by(
            Order.id,
            Order.retailer,
            Order.order_date,
            Order.source_type,
            Order.shipping_amount,
            Order.tax_amount,
            Order.total_amount,
            Order.created_at,
        )
    )


def apply_orders_filters(
    stmt,
    *,
    retailer: str | None,
    search: str | None,
):
    if retailer:
        stmt = stmt.where(Order.retailer == retailer)

    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Order.retailer.ilike(search_term),
                Publisher.name.ilike(search_term),
                ComicTitle.name.ilike(search_term),
                ComicIssue.issue_number.ilike(search_term),
                Variant.cover_name.ilike(search_term),
            )
        )

    return stmt


def apply_orders_sort(stmt, sort_by: str | None, sort_dir: str):
    resolved_sort = sort_by or "order_date"
    if resolved_sort not in ORDER_SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail="Invalid sort_by value")

    sort_column_map = {
        "order_date": Order.order_date,
        "retailer": Order.retailer,
        "total_amount": Order.total_amount,
        "created_at": Order.created_at,
    }
    sort_column = sort_column_map[resolved_sort]
    direction = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    tie_breaker = Order.id.desc() if sort_dir == "desc" else Order.id.asc()
    return stmt.order_by(direction, tie_breaker)


def list_orders_for_user(
    session: Session,
    current_user: User,
    *,
    page: int,
    page_size: int,
    retailer: str | None,
    search: str | None,
    sort_by: str | None,
    sort_dir: str,
) -> OrderListResponse:
    filtered_stmt = apply_orders_filters(
        build_orders_base_query(current_user),
        retailer=retailer,
        search=search,
    )
    total_stmt = select(func.count()).select_from(filtered_stmt.subquery())
    paginated_stmt = apply_orders_sort(filtered_stmt, sort_by, sort_dir).offset(
        (page - 1) * page_size
    ).limit(page_size)

    total = session.exec(total_stmt).one()
    rows = session.exec(paginated_stmt).all()
    return OrderListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[OrderListRow.model_validate(row._mapping) for row in rows],
    )


def get_order_detail_for_user(
    session: Session,
    current_user: User,
    order_id: int,
) -> OrderDetailResponse:
    order = session.exec(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
    ).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    item_rows = session.exec(
        select(
            OrderItem.id.label("order_item_id"),
            Publisher.name.label("publisher"),
            ComicTitle.name.label("title"),
            ComicIssue.issue_number.label("issue_number"),
            Variant.cover_name.label("cover_name"),
            Variant.printing.label("printing"),
            Variant.ratio.label("ratio"),
            Variant.variant_type.label("variant_type"),
            Variant.cover_artist.label("cover_artist"),
            OrderItem.quantity.label("quantity"),
            OrderItem.raw_item_price.label("raw_item_price"),
            OrderItem.allocated_shipping.label("allocated_shipping"),
            OrderItem.allocated_tax.label("allocated_tax"),
            OrderItem.all_in_unit_cost.label("all_in_unit_cost"),
        )
        .join(Variant, OrderItem.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id.asc())
    ).all()

    order_item_ids = [row.order_item_id for row in item_rows]
    inventory_rows = session.exec(
        select(InventoryCopy.order_item_id, InventoryCopy.id)
        .where(InventoryCopy.order_item_id.in_(order_item_ids))
        .order_by(InventoryCopy.order_item_id.asc(), InventoryCopy.copy_number.asc())
    ).all()
    inventory_by_item_id: dict[int, list[int]] = {
        order_item_id: [] for order_item_id in order_item_ids
    }
    for inventory_row in inventory_rows:
        inventory_by_item_id[inventory_row.order_item_id].append(inventory_row.id)

    return OrderDetailResponse(
        order_id=order.id,
        retailer=order.retailer,
        order_date=order.order_date,
        source_type=order.source_type,
        shipping_amount=order.shipping_amount,
        tax_amount=order.tax_amount,
        total_amount=order.total_amount,
        created_at=order.created_at,
        items=[
            OrderDetailItem(
                **row._mapping,
                inventory_copy_ids=inventory_by_item_id.get(row.order_item_id, []),
            )
            for row in item_rows
        ],
    )


def create_order_for_user(
    session: Session,
    current_user: User,
    payload: OrderCreate,
) -> OrderCreateResponse:
    try:
        response = create_order_for_user_in_transaction(
            session=session,
            current_user=current_user,
            payload=payload,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return response


def create_order_for_user_in_transaction(
    session: Session,
    current_user: User,
    payload: OrderCreate,
) -> OrderCreateResponse:
    item_subtotals = [quantize_money(item.raw_item_price * item.quantity) for item in payload.items]
    shipping_allocations = allocate_by_subtotal(item_subtotals, payload.shipping_amount)
    tax_allocations = allocate_by_subtotal(item_subtotals, payload.tax_amount)
    order_total = quantize_money(
        sum(item_subtotals, Decimal("0")) + payload.shipping_amount + payload.tax_amount
    )

    order = Order(
        user_id=current_user.id,
        retailer=payload.retailer,
        order_date=payload.order_date,
        source_type=payload.source_type,
        shipping_amount=quantize_money(payload.shipping_amount),
        tax_amount=quantize_money(payload.tax_amount),
        total_amount=order_total,
    )
    session.add(order)
    session.flush()

    total_copies_created = 0
    for index, item in enumerate(payload.items):
        publisher = get_or_create_publisher(session, item.publisher)
        title = get_or_create_title(session, publisher.id, item.title)
        issue = get_or_create_issue(session, title.id, item.issue_number)
        variant = get_or_create_variant(session, issue.id, item)

        allocated_shipping = quantize_money(shipping_allocations[index])
        allocated_tax = quantize_money(tax_allocations[index])
        shipping_per_unit = allocated_shipping / item.quantity
        tax_per_unit = allocated_tax / item.quantity
        all_in_unit_cost = quantize_money(item.raw_item_price + shipping_per_unit + tax_per_unit)

        order_item = OrderItem(
            order_id=order.id,
            variant_id=variant.id,
            quantity=item.quantity,
            raw_item_price=quantize_money(item.raw_item_price),
            allocated_shipping=allocated_shipping,
            allocated_tax=allocated_tax,
            all_in_unit_cost=all_in_unit_cost,
        )
        session.add(order_item)
        session.flush()

        for copy_number in range(1, item.quantity + 1):
            inventory_copy = InventoryCopy(
                user_id=current_user.id,
                order_item_id=order_item.id,
                variant_id=variant.id,
                copy_number=copy_number,
                acquisition_cost=all_in_unit_cost,
            )
            session.add(inventory_copy)
            total_copies_created += 1

    return OrderCreateResponse(
        order_id=order.id,
        total_items=len(payload.items),
        total_copies_created=total_copies_created,
        all_in_total=order.total_amount,
    )
