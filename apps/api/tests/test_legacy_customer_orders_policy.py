from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.services.legacy_customer_orders_policy import assert_legacy_customer_order_writes_allowed


def test_writes_allowed_when_flag_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEGACY_CUSTOMER_ORDERS_WRITES_ENABLED", "1")
    get_settings.cache_clear()
    assert_legacy_customer_order_writes_allowed()


def test_writes_blocked_when_flag_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEGACY_CUSTOMER_ORDERS_WRITES_ENABLED", "0")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        assert_legacy_customer_order_writes_allowed()
    assert exc.value.status_code == 410
