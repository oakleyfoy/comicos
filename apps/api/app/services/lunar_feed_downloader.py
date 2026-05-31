from __future__ import annotations

from app.services.lunar_authenticated_client import (
    LUNAR_RESOURCES_PATH,
    LunarAuthenticatedClient,
    LunarAuthenticationError,
    LunarDownloadedCsv,
    LunarResourceNotFoundError,
    authenticated_client_factory,
)
from app.services.lunar_credentials import LunarCredentialsError, require_lunar_credentials


def download_latest_monthly_products_csv(
    *,
    client: LunarAuthenticatedClient | None = None,
    resources_path: str = LUNAR_RESOURCES_PATH,
) -> LunarDownloadedCsv:
    owns_client = client is None
    active_client = client or LunarAuthenticatedClient()
    try:
        require_lunar_credentials()
        active_client.login()
        return active_client.download_product_csv(resources_path=resources_path)
    finally:
        if owns_client:
            active_client.close()


def download_monthly_products_csv(
    period: str,
    *,
    client: LunarAuthenticatedClient | None = None,
    resources_path: str = LUNAR_RESOURCES_PATH,
) -> LunarDownloadedCsv:
    owns_client = client is None
    active_client = client or LunarAuthenticatedClient()
    try:
        require_lunar_credentials()
        active_client.login()
        return active_client.download_product_csv(period=period, resources_path=resources_path)
    finally:
        if owns_client:
            active_client.close()


def download_monthly_products_with_related_products_csv(
    period: str | None = None,
    *,
    client: LunarAuthenticatedClient | None = None,
    resources_path: str = LUNAR_RESOURCES_PATH,
) -> LunarDownloadedCsv:
    owns_client = client is None
    active_client = client or LunarAuthenticatedClient()
    try:
        require_lunar_credentials()
        active_client.login()
        return active_client.download_product_csv(
            period=period,
            with_related_products=True,
            resources_path=resources_path,
        )
    finally:
        if owns_client:
            active_client.close()


__all__ = [
    "LunarAuthenticationError",
    "LunarCredentialsError",
    "LunarResourceNotFoundError",
    "download_latest_monthly_products_csv",
    "download_monthly_products_csv",
    "download_monthly_products_with_related_products_csv",
    "authenticated_client_factory",
]
