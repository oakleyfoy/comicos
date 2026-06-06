"""P69 provider readiness / health (no secret storage)."""

from __future__ import annotations

from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.models.market_pricing_engine import (
    PROVIDER_COMIC_PRICE_GUIDE,
    PROVIDER_COVRPRICE,
    PROVIDER_EBAY_SOLD,
    PROVIDER_GOCOLLECT,
    PROVIDER_HERITAGE,
    PROVIDER_INTERNAL_SALE,
    PROVIDER_MANUAL,
    PROVIDER_STUB,
)
from app.services.ebay_oauth import (
    EbayOAuthAuthenticationError,
    EbayOAuthConfigurationError,
    acquire_ebay_oauth_access_token,
)
from app.services.ebay_sold_search_service import probe_ebay_sold_search_availability
from app.services.market_pricing_provider_registry import ensure_provider_registry
from app.services.market_refresh_service import get_latest_refresh_run
from app.services.market_pricing_engine_service import get_latest_p68_snapshots


def _ebay_configured(settings: Settings) -> bool:
    return bool(settings.ebay_api_client_id.strip() and settings.ebay_api_client_secret.strip())


def provider_readiness(
    session: Session,
    *,
    owner_user_id: int,
    settings: Settings | None = None,
) -> list[dict]:
    resolved_settings = settings or get_settings()
    rows = ensure_provider_registry(session, owner_user_id=owner_user_id)
    by_type = {r.provider_type: r for r in rows}
    refresh_run = get_latest_refresh_run(session, owner_user_id=owner_user_id)
    latest_snaps = get_latest_p68_snapshots(session, owner_user_id=owner_user_id, limit=1)
    last_fmv_generation = latest_snaps[0].generated_at.isoformat() if latest_snaps else None
    last_refresh_at = refresh_run.completed_at.isoformat() if refresh_run and refresh_run.completed_at else None
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
        metadata_json: dict[str, object] = row.metadata_json if row and isinstance(row.metadata_json, dict) else {}
        if provider_type == PROVIDER_EBAY_SOLD:
            if not _ebay_configured(resolved_settings):
                health = "NOT_CONFIGURED"
                enabled = False
                metadata_json = {
                    **metadata_json,
                    "sold_search_available": False,
                    "import_available": False,
                    "last_error": "Missing eBay credentials.",
                    "last_import_at": row.last_ingest_at.isoformat() if row and row.last_ingest_at else None,
                }
                detail = "EBAY_API_CLIENT_ID / EBAY_API_CLIENT_SECRET are not configured."
            else:
                try:
                    token = acquire_ebay_oauth_access_token(settings=resolved_settings)
                except EbayOAuthConfigurationError as exc:
                    health = "NOT_CONFIGURED"
                    enabled = False
                    metadata_json = {
                        **metadata_json,
                        "sold_search_available": False,
                        "import_available": False,
                        "last_error": str(exc),
                        "last_import_at": row.last_ingest_at.isoformat() if row and row.last_ingest_at else None,
                    }
                    detail = f"eBay OAuth configuration error: {exc}"
                except EbayOAuthAuthenticationError as exc:
                    health = "AUTH_FAILED"
                    enabled = False
                    metadata_json = {
                        **metadata_json,
                        "sold_search_available": False,
                        "import_available": False,
                        "last_error": str(exc),
                        "last_import_at": row.last_ingest_at.isoformat() if row and row.last_ingest_at else None,
                    }
                    detail = f"eBay OAuth authentication failed: {exc}"
                else:
                    health = "AUTHENTICATED"
                    enabled = True
                    sold_available, sold_error = probe_ebay_sold_search_availability(settings=resolved_settings)
                    metadata_json = {
                        **metadata_json,
                        "sold_search_available": sold_available,
                        "import_available": sold_available,
                        "last_error": sold_error,
                        "environment": token.environment,
                        "last_import_at": row.last_ingest_at.isoformat() if row and row.last_ingest_at else None,
                        "last_refresh_at": last_refresh_at,
                        "last_fmv_generation_at": last_fmv_generation,
                    }
                    detail = (
                        f"eBay OAuth token acquired for {token.environment}. "
                        f"Sold search {'available' if sold_available else 'unavailable'}. "
                        f"Import {'available' if sold_available else 'unavailable'}."
                    )
                    if sold_error:
                        detail = f"{detail} Last error: {sold_error}"
        if provider_type in (PROVIDER_GOCOLLECT, PROVIDER_COVRPRICE, PROVIDER_HERITAGE, PROVIDER_COMIC_PRICE_GUIDE):
            configured = False
            health = "NOT_CONFIGURED"
            enabled = False
            metadata_json = {}
        out.append(
            {
                "id": int(row.id or 0) if row else 0,
                "provider_type": provider_type,
                "enabled": enabled,
                "configured": configured,
                "health_status": health,
                "detail": detail,
                "last_ingest_at": row.last_ingest_at.isoformat() if row and row.last_ingest_at else None,
                "metadata_json": metadata_json,
            }
        )

    add(PROVIDER_INTERNAL_SALE, configured=True, detail="Owner sold inventory and live sale queue")
    add(PROVIDER_MANUAL, configured=True, detail="Manual FMV observations")
    add(PROVIDER_STUB, configured=True, detail="P66 stub — not live market data")
    add(
        PROVIDER_EBAY_SOLD,
        configured=_ebay_configured(resolved_settings),
        detail="eBay OAuth token acquisition for production keyset",
        enabled_override=True if _ebay_configured(resolved_settings) else False,
    )
    add(PROVIDER_GOCOLLECT, configured=False, detail="Integration not wired in P69")
    add(PROVIDER_COVRPRICE, configured=False, detail="Integration not wired in P69")
    add(PROVIDER_HERITAGE, configured=False, detail="Integration not wired in P69")
    add(PROVIDER_COMIC_PRICE_GUIDE, configured=False, detail="Integration not wired in P69")
    return out
