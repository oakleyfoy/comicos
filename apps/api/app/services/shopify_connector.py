from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.security import decrypt_secret_value
from app.models.marketplace import MarketplaceCredential
from app.schemas.marketplace import MarketplaceCapabilityRead, MarketplaceExecutionRead
from app.services.marketplace_connector_base import MarketplaceConnectorBase
from app.services.marketplace_registry import get_marketplace

SHOPIFY_MARKETPLACE_CODE = "SHOPIFY"
EXECUTION_CONNECT = "CONNECT"
EXECUTION_DISCONNECT = "DISCONNECT"
EXECUTION_VALIDATE = "VALIDATE"
EXECUTION_PUBLISH = "PUBLISH"
EXECUTION_UPDATE = "UPDATE"
EXECUTION_ARCHIVE = "ARCHIVE"
EXECUTION_RESTORE = "RESTORE"
EXECUTION_IMPORT_ORDERS = "IMPORT_ORDERS"
EXECUTION_SYNC_INVENTORY = "SYNC_INVENTORY"

VALID_TOKEN_PREFIX = "shopify_valid_"


@dataclass
class _StubProduct:
    external_listing_id: str
    external_url: str
    status: str
    quantity: int
    payload: dict[str, Any]


@dataclass
class _StubOrder:
    external_order_id: str
    buyer_name: str
    buyer_email: str
    total_amount: str
    currency: str
    items: list[dict[str, Any]]


_STUB_PRODUCTS: dict[int, dict[str, _StubProduct]] = {}
_STUB_ORDERS: dict[int, list[_StubOrder]] = {}


def reset_shopify_stub_state() -> None:
    _STUB_PRODUCTS.clear()
    _STUB_ORDERS.clear()


def _credential_token(session: Session, *, account_id: int) -> str:
    row = session.exec(
        select(MarketplaceCredential)
        .where(MarketplaceCredential.account_id == account_id)
        .order_by(MarketplaceCredential.updated_at.desc(), MarketplaceCredential.id.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=422, detail="Shopify credentials are not configured.")
    return decrypt_secret_value(row.encrypted_payload)


def _external_product_id(listing_uuid: str) -> str:
    digest = hashlib.sha256(listing_uuid.encode("utf-8")).hexdigest()[:16]
    return f"shopify-product-{digest}"


def _has_valid_credentials(session: Session, *, account_id: int) -> bool:
    try:
        token = _credential_token(session, account_id=account_id)
    except HTTPException:
        return False
    return token.startswith(VALID_TOKEN_PREFIX)


class ShopifyConnector(MarketplaceConnectorBase):
    def connect(self, session: Session) -> MarketplaceExecutionRead:
        execution = self.create_execution(session, execution_type=EXECUTION_CONNECT)
        if self.account_id is None:
            self.fail_execution(session, execution_id=execution.id)
            raise HTTPException(status_code=422, detail="Shopify account is required to connect.")
        if not self.validate_credentials(session):
            self.fail_execution(session, execution_id=execution.id)
            raise HTTPException(status_code=422, detail="Shopify credential validation failed.")
        return self.complete_execution(session, execution_id=execution.id)

    def disconnect(self, session: Session) -> MarketplaceExecutionRead:
        execution = self.create_execution(session, execution_type=EXECUTION_DISCONNECT)
        return self.complete_execution(session, execution_id=execution.id)

    def validate_credentials(self, session: Session) -> bool:
        if self.account_id is None:
            return False
        execution = self.create_execution(session, execution_type=EXECUTION_VALIDATE)
        try:
            token = _credential_token(session, account_id=self.account_id)
            valid = token.startswith(VALID_TOKEN_PREFIX)
        except HTTPException:
            valid = False
        if valid:
            self.complete_execution(session, execution_id=execution.id)
            return True
        self.fail_execution(session, execution_id=execution.id)
        return False

    def get_capabilities(self, session: Session) -> list[MarketplaceCapabilityRead]:
        marketplace = get_marketplace(session, marketplace_id=self.marketplace_id)
        return list(marketplace.capabilities)

    def publish_listing(self, session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
        execution = self.create_execution(session, execution_type=EXECUTION_PUBLISH)
        if self.account_id is None or not _has_valid_credentials(session, account_id=self.account_id):
            self.fail_execution(session, execution_id=execution.id)
            raise HTTPException(status_code=422, detail="Shopify publish requires valid credentials.")
        listing_uuid = str(payload.get("canonical_listing", {}).get("listing_uuid") or uuid.uuid4())
        external_id = _external_product_id(listing_uuid)
        quantity = int(payload.get("canonical_listing", {}).get("quantity") or 1)
        product = _StubProduct(
            external_listing_id=external_id,
            external_url=f"https://shopify.example/products/{external_id}",
            status="ACTIVE",
            quantity=quantity,
            payload=payload,
        )
        account_products = _STUB_PRODUCTS.setdefault(self.account_id, {})
        account_products[external_id] = product
        result = {
            "external_listing_id": external_id,
            "external_url": product.external_url,
            "status": product.status,
            "quantity": product.quantity,
        }
        self.complete_execution(session, execution_id=execution.id)
        return result

    def update_listing(self, session: Session, *, external_listing_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        execution = self.create_execution(session, execution_type=EXECUTION_UPDATE)
        product = self._product_or_404(external_listing_id)
        if product.status == "ARCHIVED":
            self.fail_execution(session, execution_id=execution.id)
            raise HTTPException(status_code=409, detail="Archived Shopify products cannot be updated.")
        if "canonical_listing" in payload:
            canonical = payload["canonical_listing"]
            if "quantity" in canonical:
                product.quantity = int(canonical["quantity"])
        product.payload = payload
        result = {
            "external_listing_id": product.external_listing_id,
            "external_url": product.external_url,
            "status": product.status,
            "quantity": product.quantity,
        }
        self.complete_execution(session, execution_id=execution.id)
        return result

    def archive_listing(self, session: Session, *, external_listing_id: str) -> dict[str, Any]:
        execution = self.create_execution(session, execution_type=EXECUTION_ARCHIVE)
        product = self._product_or_404(external_listing_id)
        product.status = "ARCHIVED"
        self.complete_execution(session, execution_id=execution.id)
        return {"external_listing_id": external_listing_id, "status": product.status}

    def restore_listing(self, session: Session, *, external_listing_id: str) -> dict[str, Any]:
        execution = self.create_execution(session, execution_type=EXECUTION_RESTORE)
        product = self._product_or_404(external_listing_id)
        product.status = "ACTIVE"
        self.complete_execution(session, execution_id=execution.id)
        return {"external_listing_id": external_listing_id, "status": product.status}

    def import_orders(self, session: Session) -> list[dict[str, Any]]:
        execution = self.create_execution(session, execution_type=EXECUTION_IMPORT_ORDERS)
        if self.account_id is None:
            self.fail_execution(session, execution_id=execution.id)
            raise HTTPException(status_code=422, detail="Shopify account is required to import orders.")
        orders = list(_STUB_ORDERS.get(self.account_id, []))
        if not orders:
            products = _STUB_PRODUCTS.get(self.account_id, {})
            for external_id, product in products.items():
                canonical = product.payload.get("canonical_listing", {})
                order = _StubOrder(
                    external_order_id=f"shopify-order-{external_id}",
                    buyer_name="Shopify Customer",
                    buyer_email="customer@shopify.example",
                    total_amount=str(canonical.get("asking_price") or "0.00"),
                    currency=str(canonical.get("currency") or "USD"),
                    items=[
                        {
                            "external_item_id": f"{external_id}-line-1",
                            "title": str(canonical.get("listing_title") or "Shopify Product"),
                            "quantity": 1,
                            "unit_price": str(canonical.get("asking_price") or "0.00"),
                            "listing_id": canonical.get("listing_id"),
                            "inventory_copy_id": canonical.get("inventory_copy_id"),
                        }
                    ],
                )
                orders.append(order)
            _STUB_ORDERS[self.account_id] = orders
        payload = [
            {
                "external_order_id": order.external_order_id,
                "buyer_name": order.buyer_name,
                "buyer_email": order.buyer_email,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "items": order.items,
            }
            for order in orders
        ]
        self.complete_execution(session, execution_id=execution.id)
        return payload

    def sync_inventory(self, session: Session, *, external_listing_id: str, quantity: int) -> dict[str, Any]:
        execution = self.create_execution(session, execution_type=EXECUTION_SYNC_INVENTORY)
        product = self._product_or_404(external_listing_id)
        if product.status == "ARCHIVED":
            self.fail_execution(session, execution_id=execution.id)
            raise HTTPException(status_code=409, detail="Cannot sync inventory for archived Shopify products.")
        product.quantity = max(int(quantity), 0)
        self.complete_execution(session, execution_id=execution.id)
        return {
            "external_listing_id": external_listing_id,
            "quantity": product.quantity,
            "status": product.status,
        }

    def _product_or_404(self, external_listing_id: str) -> _StubProduct:
        if self.account_id is None:
            raise HTTPException(status_code=404, detail="Shopify product not found.")
        product = _STUB_PRODUCTS.get(self.account_id, {}).get(external_listing_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Shopify product not found.")
        return product
