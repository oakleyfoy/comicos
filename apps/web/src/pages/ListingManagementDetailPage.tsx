import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError, apiClient, type P89ManagedListingRead } from "../api/client";
import { PatriotPageLayout } from "../components/PatriotPageLayout";

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function ListingManagementDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const [search] = useSearchParams();
  const listingId = Number(id);
  const [listing, setListing] = useState<P89ManagedListingRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [salePrice, setSalePrice] = useState("");
  const [shippingCharged, setShippingCharged] = useState("");
  const [fees, setFees] = useState("");
  const [shipCost, setShipCost] = useState("");
  const showSoldForm = search.get("markSold") === "1";

  const load = useCallback(async () => {
    if (!Number.isFinite(listingId)) return;
    setLoading(true);
    setError(null);
    try {
      setListing(await apiClient.getManagedListing(listingId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Listing not found.");
    } finally {
      setLoading(false);
    }
  }, [listingId]);

  useEffect(() => {
    void load();
  }, [load]);

  function patchField<K extends keyof P89ManagedListingRead>(key: K, value: P89ManagedListingRead[K]) {
    setListing((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function saveEdits() {
    if (!listing) return;
    setSaving(true);
    try {
      const updated = await apiClient.patchManagedListing(listing.id, {
        listing_url: listing.listing_url,
        asking_price: listing.asking_price ?? undefined,
        shipping_price: listing.shipping_price ?? undefined,
        minimum_price: listing.minimum_price ?? undefined,
        notes: listing.notes,
      });
      setListing(updated);
      setMessage("Saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function submitSold() {
    if (!listing) return;
    const price = Number(salePrice);
    if (!Number.isFinite(price)) {
      setError("Enter a valid sale price.");
      return;
    }
    try {
      const updated = await apiClient.markManagedListingSold(listing.id, {
        sale_price: price,
        shipping_charged: shippingCharged ? Number(shippingCharged) : undefined,
        marketplace_fees: fees ? Number(fees) : undefined,
        shipping_cost: shipCost ? Number(shipCost) : undefined,
      });
      setListing(updated);
      setMessage("Marked sold. Inventory not automatically updated.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not mark sold.");
    }
  }

  async function markInventorySold() {
    if (!listing) return;
    await apiClient.markInventorySoldForListing(listing.id);
    setMessage("Inventory marked sold.");
  }

  if (loading) {
    return (
      <PatriotPageLayout eyebrow="Sell" title="Listing detail" showExpansionNav>
        <p className="text-sm text-blue-100">Loading…</p>
      </PatriotPageLayout>
    );
  }

  if (!listing) {
    return (
      <PatriotPageLayout eyebrow="Sell" title="Listing detail" error={error} showExpansionNav>
        <Link to="/listing-management" className="text-blue-200 underline">
          Back
        </Link>
      </PatriotPageLayout>
    );
  }

  return (
    <PatriotPageLayout
      eyebrow="Sell"
      title={listing.comic_title || listing.title}
      description={`${listing.marketplace} · ${listing.status}`}
      showExpansionNav
      error={error}
      headerActions={
        <Link to="/listing-management" className="text-sm text-blue-100 underline">
          All listings
        </Link>
      }
    >
      {message ? <p className="mb-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{message}</p> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-blue-800 bg-white p-4 text-blue-950">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-blue-800">Listing info</h2>
          <label className="block text-sm">
            Listing URL
            <input
              className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
              value={listing.listing_url}
              onChange={(e) => patchField("listing_url", e.target.value)}
            />
          </label>
          <label className="mt-3 block text-sm">
            Notes
            <textarea
              className="mt-1 min-h-24 w-full rounded border border-blue-200 px-2 py-1.5"
              value={listing.notes}
              onChange={(e) => patchField("notes", e.target.value)}
            />
          </label>
          <button type="button" className="mt-3 rounded-md bg-red-800 px-3 py-1.5 text-sm text-white" onClick={() => void saveEdits()} disabled={saving}>
            Save
          </button>
        </section>
        <section className="rounded-lg border border-blue-800 bg-white p-4 text-blue-950">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-blue-800">Pricing</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block text-sm">
              Asking
              <input
                type="number"
                className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
                value={listing.asking_price ?? ""}
                onChange={(e) => patchField("asking_price", e.target.value ? Number(e.target.value) : null)}
              />
            </label>
            <label className="block text-sm">
              Shipping
              <input
                type="number"
                className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
                value={listing.shipping_price ?? ""}
                onChange={(e) => patchField("shipping_price", e.target.value ? Number(e.target.value) : null)}
              />
            </label>
            <label className="block text-sm">
              Minimum
              <input
                type="number"
                className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
                value={listing.minimum_price ?? ""}
                onChange={(e) => patchField("minimum_price", e.target.value ? Number(e.target.value) : null)}
              />
            </label>
          </div>
        </section>
        <section className="rounded-lg border border-blue-800 bg-white p-4 text-blue-950">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-blue-800">Profit</h2>
          {listing.profit ? (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt className="text-blue-600">Gross sale</dt>
                <dd>{money(listing.profit.gross_sale)}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Total costs</dt>
                <dd>{money(listing.profit.total_costs)}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Net profit</dt>
                <dd>{listing.profit.cost_basis_known ? money(listing.profit.net_profit) : "Unknown"}</dd>
              </div>
              <div>
                <dt className="text-blue-600">Margin</dt>
                <dd>{listing.profit.profit_margin != null ? `${listing.profit.profit_margin}%` : "—"}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-blue-800">Profit appears after you mark this listing sold.</p>
          )}
        </section>
        <section className="rounded-lg border border-blue-800 bg-white p-4 text-blue-950">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-blue-800">Status history</h2>
          <ul className="space-y-1 text-sm">
            {listing.status_history.map((ev, i) => (
              <li key={`${ev.status}-${i}`}>
                {ev.status} · {ev.at ? new Date(ev.at).toLocaleString() : "—"}
              </li>
            ))}
          </ul>
        </section>
      </div>
      {(showSoldForm || listing.status === "ACTIVE") && listing.status !== "SOLD" ? (
        <section className="mt-4 rounded-lg border border-emerald-800 bg-white p-4 text-blue-950">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-emerald-900">Mark sold</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block text-sm">
              Sale price
              <input className="mt-1 w-full rounded border px-2 py-1.5" value={salePrice} onChange={(e) => setSalePrice(e.target.value)} />
            </label>
            <label className="block text-sm">
              Shipping charged
              <input className="mt-1 w-full rounded border px-2 py-1.5" value={shippingCharged} onChange={(e) => setShippingCharged(e.target.value)} />
            </label>
            <label className="block text-sm">
              Marketplace fees
              <input className="mt-1 w-full rounded border px-2 py-1.5" value={fees} onChange={(e) => setFees(e.target.value)} />
            </label>
            <label className="block text-sm">
              Shipping cost
              <input className="mt-1 w-full rounded border px-2 py-1.5" value={shipCost} onChange={(e) => setShipCost(e.target.value)} />
            </label>
          </div>
          <button type="button" className="mt-3 rounded-md bg-emerald-800 px-3 py-1.5 text-sm text-white" onClick={() => void submitSold()}>
            Record sale
          </button>
        </section>
      ) : null}
      {listing.status === "SOLD" ? (
        <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Inventory not automatically updated.{" "}
          <button type="button" className="font-medium underline" onClick={() => void markInventorySold()}>
            Mark Inventory Sold
          </button>
        </div>
      ) : null}
    </PatriotPageLayout>
  );
}
