"""Policy for retiring legacy customer_order / order_item writes (catalog unification B1)."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import get_settings

LEGACY_CUSTOMER_ORDERS_RETIRED_DETAIL = (
    "Legacy customer orders are retired. New inventory should use catalog acquisitions "
    "(Add Comics / acquisitions API). Existing orders remain readable."
)


def legacy_customer_orders_writes_enabled() -> bool:
    return get_settings().legacy_customer_orders_writes_enabled


def assert_legacy_customer_order_writes_allowed() -> None:
    if legacy_customer_orders_writes_enabled():
        return
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=LEGACY_CUSTOMER_ORDERS_RETIRED_DETAIL,
    )
