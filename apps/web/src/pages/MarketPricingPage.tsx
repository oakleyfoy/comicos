import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P89MarketPriceSnapshotRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { PatriotPageLayout } from "../components/PatriotPageLayout";

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function PricingCard({
  row,
  onCreateDraft,
}: {
  row: P89MarketPriceSnapshotRead;
  onCreateDraft?: (row: P89MarketPriceSnapshotRead) => void;
}): JSX.Element {
  return (
    <article className="rounded-lg border border-blue-800 bg-white px-4 py-4 text-blue-950 shadow-sm">
      <h3 className="text-base font-semibold text-blue-950">{row.display_title || row.series}</h3>
      {row.variant ? <p className="text-xs text-blue-700">Variant: {row.variant}</p> : null}
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase tracking-wide text-blue-600">Quick Sale</dt>
          <dd className="font-medium">{money(row.quick_sale_price)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-blue-600">Market</dt>
          <dd className="font-medium">{money(row.market_price)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-blue-600">Premium</dt>
          <dd className="font-medium">{money(row.premium_price)}</dd>
        </div>
      </dl>
      <p className="mt-2 text-sm text-blue-800">
        Confidence: <span className="font-medium">{row.pricing_confidence}</span>
        {" · "}
        {row.sales_velocity_label || row.sales_velocity}
        {" · "}
        Trend: {row.trend_direction}
      </p>
      {onCreateDraft ? (
        <button
          type="button"
          className="mt-3 rounded-md border border-blue-800 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-50"
          onClick={() => onCreateDraft(row)}
        >
          Create Listing Draft
        </button>
      ) : null}
    </article>
  );
}

function Section({
  title,
  items,
  onCreateDraft,
}: {
  title: string;
  items: P89MarketPriceSnapshotRead[];
  onCreateDraft?: (row: P89MarketPriceSnapshotRead) => void;
}): JSX.Element | null {
  if (items.length === 0) {
    return null;
  }
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold text-white">{title}</h2>
      <ul className="space-y-4">
        {items.map((row) => (
          <li key={row.id}>
            <PricingCard row={row} onCreateDraft={onCreateDraft} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function MarketPricingPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<Awaited<ReturnType<typeof apiClient.getMarketPricingDashboard>> | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  async function createDraftFromSnapshot(row: P89MarketPriceSnapshotRead) {
    try {
      const draft = await apiClient.createListingDraft({
        market_price_snapshot_id: row.id,
        marketplace: "EBAY",
      });
      setMessage(`Draft #${draft.id} created. Open Listing Drafts to review.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create listing draft.");
    }
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDashboard(await apiClient.getMarketPricingDashboard());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load market pricing.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasRows =
    dashboard &&
    (dashboard.highest_value_books.length > 0 ||
      dashboard.fastest_selling_books.length > 0 ||
      dashboard.largest_price_increases.length > 0 ||
      dashboard.largest_price_decreases.length > 0 ||
      dashboard.highest_confidence_pricing.length > 0);

  return (
    <PatriotPageLayout
      eyebrow="Sell"
      title="Market Pricing Intelligence"
      description="Realistic selling estimates based on marketplace activity."
      showExpansionNav
      error={error}
      onRetry={() => void load()}
    >
      {message ? (
        <p className="mb-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{message}</p>
      ) : null}
      {loading ? <p className="text-sm text-blue-100">Loading…</p> : null}
      {!loading && !hasRows ? (
        <CollectorEmptyState
          title="No market pricing snapshots yet."
          description="Run market pricing generation after marketplace listings are stored so ComicOS can estimate quick, market, and premium prices."
        />
      ) : null}
      {dashboard && hasRows ? (
        <div className="space-y-10">
          <Section title="Highest Value Books" items={dashboard.highest_value_books} onCreateDraft={(r) => void createDraftFromSnapshot(r)} />
          <Section title="Fastest Selling Books" items={dashboard.fastest_selling_books} onCreateDraft={(r) => void createDraftFromSnapshot(r)} />
          <Section title="Largest Price Increases" items={dashboard.largest_price_increases} onCreateDraft={(r) => void createDraftFromSnapshot(r)} />
          <Section title="Largest Price Decreases" items={dashboard.largest_price_decreases} onCreateDraft={(r) => void createDraftFromSnapshot(r)} />
          <Section title="Highest Confidence Pricing" items={dashboard.highest_confidence_pricing} onCreateDraft={(r) => void createDraftFromSnapshot(r)} />
        </div>
      ) : null}
    </PatriotPageLayout>
  );
}
