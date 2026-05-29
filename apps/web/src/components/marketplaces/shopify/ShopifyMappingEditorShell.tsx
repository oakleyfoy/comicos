import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type {
  ShopifyProductMappingCreateRequest,
  ShopifyProductMappingResponse,
  ShopifyProductMappingUpdateRequest,
} from "../../../api/client";

export function ShopifyMappingEditorShell({
  mapping,
  canManage,
  submitting,
  onSubmit,
}: {
  mapping: ShopifyProductMappingResponse | null;
  canManage: boolean;
  submitting: boolean;
  onSubmit: (payload: ShopifyProductMappingCreateRequest | ShopifyProductMappingUpdateRequest) => Promise<void>;
}): JSX.Element {
  const [inventoryItemId, setInventoryItemId] = useState("");
  const [marketplaceListingDraftId, setMarketplaceListingDraftId] = useState("");
  const [storefrontProductIdentifier, setStorefrontProductIdentifier] = useState("");
  const [mappingStatus, setMappingStatus] = useState("mapped");

  useEffect(() => {
    setInventoryItemId(mapping ? String(mapping.inventory_item_id) : "");
    setMarketplaceListingDraftId(mapping ? String(mapping.marketplace_listing_draft_id) : "");
    setStorefrontProductIdentifier(mapping ? mapping.storefront_product_identifier : "");
    setMappingStatus(mapping ? mapping.mapping_status : "mapped");
  }, [mapping]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    if (mapping) {
      await onSubmit({
        storefront_product_identifier: storefrontProductIdentifier.trim(),
        mapping_status: mappingStatus,
      });
      return;
    }
    await onSubmit({
      inventory_item_id: Number(inventoryItemId),
      marketplace_listing_draft_id: Number(marketplaceListingDraftId),
      storefront_product_identifier: storefrontProductIdentifier.trim(),
      mapping_status: mappingStatus,
    });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Mapping editor</p>
      <h2 className="mt-1 text-base font-semibold text-white">{mapping ? "Edit product mapping" : "Create product mapping"}</h2>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Inventory item id</span>
            <input
              type="number"
              disabled={!!mapping}
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 disabled:opacity-60"
              value={inventoryItemId}
              onChange={(event) => setInventoryItemId(event.target.value)}
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Listing draft id</span>
            <input
              type="number"
              disabled={!!mapping}
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 disabled:opacity-60"
              value={marketplaceListingDraftId}
              onChange={(event) => setMarketplaceListingDraftId(event.target.value)}
            />
          </label>
        </div>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Shopify product identifier</span>
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={storefrontProductIdentifier}
            onChange={(event) => setStorefrontProductIdentifier(event.target.value)}
            placeholder="shopify-product-123"
          />
        </label>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Mapping status</span>
          <select
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={mappingStatus}
            onChange={(event) => setMappingStatus(event.target.value)}
          >
            <option value="mapped">mapped</option>
            <option value="unmapped">unmapped</option>
            <option value="invalid">invalid</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={!canManage || submitting}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Saving..." : mapping ? "Update mapping" : "Create mapping"}
        </button>
      </form>
    </section>
  );
}
