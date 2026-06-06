"""P69 provider readiness / health (no secret storage)."""

from __future__ import annotations

from sqlmodel import Session

from app.core.config import get_settings
from app.models.market_pricing_engine import (
    PROVIDER_COMIC_PRICE_GUIDE,
    PROVIDER_COVRPRICE,
    PROVIDER_CSV_IMPORT,
    PROVIDER_EBAY_SOLD,
    PROVIDER_GOCOLLECT,
    PROVIDER_HERITAGE,
    PROVIDER_INTERNAL_SALE,
    PROVIDER_MANUAL,
    PROVIDER_STUB,
)
from app.services.market_pricing_provider_registry import ensure_provider_registry
from app.services.p68_feature_flags import p68_ebay_provider_enabled
from app.services.p69_feature_flags import p69_csv_import_enabled


def _ebay_configured() -> bool:
    settings = get_settings()
    client_id = settings.ebay_api_client_id.strip()
    return bool(client_id)


def provider_readiness(session: Session, *, owner_user_id: int) -> list[dict]:
    rows = ensure_provider_registry(session, owner_user_id=owner_user_id)
    by_type = {r.provider_type: r for r in rows}
    out: list[dict] = []

    def add(
        provider_type: str,
        *,
        configured: bool,
        detail: str,
        enabled_override: bool | None = None,
    ) -> None:
        row = by_type.get(provider_type)
        enabled = enabled_override if enabled_override is not None else (row.enabled if row else False)
        health = row.health_status if row else "UNKNOWN"
        if provider_type == PROVIDER_EBAY_SOLD:
            if not _ebay_configured():
                health = "NOT_CONFIGURED"
                enabled = False
            elif not p68_ebay_provider_enabled():
                health = "DISABLED"
                enabled = False
            else:
                health = "READY"
                enabled = True
        if provider_type == PROVIDER_CSV_IMPORT:
            enabled = p69_csv_import_enabled()
            health = "OK" if enabled else "DISABLED"
            configured = True
        if provider_type in (PROVIDER_GOCOLLECT, PROVIDER_COVRPRICE, PROVIDER_HERITAGE, PROVIDER_COMIC_PRICE_GUIDE):
            configured = False
            health = "NOT_CONFIGURED"
            enabled = False
        out.append(
            {
                "provider_type": provider_type,
                "enabled": enabled,
                "configured": configured,
                "health_status": health,
                "detail": detail,
                "last_ingest_at": row.last_ingest_at.isoformat() if row and row.last_ingest_at else None,
            }
        )

    add(PROVIDER_INTERNAL_SALE, configured=True, detail="Owner sold inventory and live sale queue")
    add(PROVIDER_CSV_IMPORT, configured=True, detail="CSV sold comps upload")
    add(PROVIDER_MANUAL, configured=True, detail="Manual FMV observations")
    add(PROVIDER_STUB, configured=True, detail="P66 stub — not live market data")
    add(
        PROVIDER_EBAY_SOLD,
        configured=_ebay_configured(),
        detail="Waiting for eBay API credentials; no live scrape",
        enabled_override=p68_ebay_provider_enabled() and _ebay_configured(),
    )
    add(PROVIDER_GOCOLLECT, configured=False, detail="Integration not wired in P69")
    add(PROVIDER_COVRPRICE, configured=False, detail="Integration not wired in P69")
    add(PROVIDER_HERITAGE, configured=False, detail="Integration not wired in P69")
    add(PROVIDER_COMIC_PRICE_GUIDE, configured=False, detail="Integration not wired in P69")
    return out
