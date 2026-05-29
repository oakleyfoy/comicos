import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type PublicStorefrontInventoryItem,
  type PublicStorefrontResponse,
} from "../api/client";
import { StorefrontHeroPanel, StorefrontInventoryPanel } from "../components/storefront/StorefrontPublicPanels";

export function DealerStorefrontPage(): JSX.Element {
  const { publicSlug } = useParams();
  const [storefront, setStorefront] = useState<PublicStorefrontResponse | null>(null);
  const [inventory, setInventory] = useState<PublicStorefrontInventoryItem[]>([]);
  const [featured, setFeatured] = useState<PublicStorefrontInventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (publicSlug) {
      void refresh(publicSlug);
    }
  }, [publicSlug]);

  async function refresh(slug: string): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [storefrontResponse, inventoryResponse, featuredResponse] = await Promise.all([
        apiClient.getPublicStorefront(slug),
        apiClient.getPublicStorefrontInventory(slug, { limit: 50, offset: 0 }),
        apiClient.getPublicStorefrontFeatured(slug),
      ]);
      setStorefront(storefrontResponse);
      setInventory(inventoryResponse.items);
      setFeatured(featuredResponse.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Storefront unavailable.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        {error ? <p className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</p> : null}
        <StorefrontHeroPanel storefront={storefront} loading={loading} />
        {!loading && storefront ? <StorefrontInventoryPanel inventory={inventory} featured={featured} /> : null}
      </div>
    </div>
  );
}
