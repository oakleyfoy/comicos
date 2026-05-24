from __future__ import annotations

from datetime import date, datetime

ReleaseStatus = str
OrderStatus = str
AssetState = str


def default_release_status(*, release_date: date | None, today: date | None = None) -> ReleaseStatus:
    if release_date is None:
        return "unknown"
    resolved_today = today or date.today()
    if release_date > resolved_today:
        return "not_released_yet"
    return "released"


def default_order_status(
    *,
    release_status: ReleaseStatus,
    received_at: datetime | None,
    explicit_order_status: OrderStatus | None = None,
) -> OrderStatus:
    if explicit_order_status == "cancelled":
        return "cancelled"
    if explicit_order_status == "received" or received_at is not None:
        return "received"
    if explicit_order_status == "shipped":
        return "shipped"
    if explicit_order_status == "ordered":
        return "ordered"
    if explicit_order_status == "preordered":
        return "preordered"
    if release_status == "not_released_yet":
        return "preordered"
    return "ordered"


def default_expected_ship_date(
    *,
    release_date: date | None,
    release_status: ReleaseStatus,
    explicit_expected_ship_date: date | None,
) -> date | None:
    if explicit_expected_ship_date is not None:
        return explicit_expected_ship_date
    if release_status == "not_released_yet":
        return release_date
    return None


def derive_asset_state(*, release_status: ReleaseStatus, order_status: OrderStatus) -> AssetState:
    if order_status == "cancelled":
        return "cancelled"
    if order_status == "received":
        return "in_hand"
    if release_status == "not_released_yet" or order_status == "preordered":
        return "preorder_not_released_yet"
    return "ordered_not_received"


def is_in_hand_asset(*, order_status: OrderStatus) -> bool:
    return order_status == "received"
