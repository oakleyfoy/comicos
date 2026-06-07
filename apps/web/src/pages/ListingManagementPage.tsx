import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P89ManagedListingRead, type P89ManagedListingStatus } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { PatriotPageLayout } from "../components/PatriotPageLayout";

const TABS: { key: P89ManagedListingStatus; label: string }[] = [
  { key: "DRAFT", label: "Drafts" },
  { key: "ACTIVE", label: "Active" },
  { key: "SOLD", label: "Sold" },
  { key: "EXPIRED", label: "Expired" },
  { key: "ARCHIVED", label: "Archived" },
];

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function ListingRow({
  row,
  onAction,
}: {
  row: P89ManagedListingRead;
  onAction: (action: string, id: number) => void;
}): JSX.Element {
  return (
    <article className="rounded-lg border border-blue-800 bg-white px-4 py-4 text-blue-950 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{row.comic_title || row.title}</h3>
          <p className="text-xs uppercase tracking-wide text-red-700">
            {row.marketplace} · {row.status}
          </p>
        </div>
        <div className="text-right text-sm">
          <p>Ask: {money(row.asking_price)}</p>
          {row.status === "SOLD" ? (
            <>
              <p>Sale: {money(row.sale_price)}</p>
              <p>
                Net profit:{" "}
                {row.profit?.cost_basis_known === false ? "Unknown" : money(row.net_profit ?? row.profit?.net_profit)}
              </p>
            </>
          ) : null}
        </div>
      </div>
      <p className="mt-2 text-xs text-blue-800">
        Listed: {row.listed_at ? new Date(row.listed_at).toLocaleDateString() : "—"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={`/listing-management/${row.id}`}
          className="rounded-md border border-blue-800 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-50"
        >
          View
        </Link>
        {row.status === "DRAFT" || row.status === "EXPIRED" ? (
          <button
            type="button"
            className="rounded-md border border-emerald-700 px-3 py-1.5 text-sm text-emerald-900"
            onClick={() => onAction("active", row.id)}
          >
            Mark Active
          </button>
        ) : null}
        {row.status === "ACTIVE" ? (
          <>
            <button type="button" className="rounded-md border border-blue-700 px-3 py-1.5 text-sm" onClick={() => onAction("sold", row.id)}>
              Mark Sold
            </button>
            <button type="button" className="rounded-md border border-amber-700 px-3 py-1.5 text-sm" onClick={() => onAction("expired", row.id)}>
              Mark Expired
            </button>
          </>
        ) : null}
        {row.status !== "ARCHIVED" && row.status !== "CANCELLED" ? (
          <button type="button" className="rounded-md border border-slate-500 px-3 py-1.5 text-sm" onClick={() => onAction("archive", row.id)}>
            Archive
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function ListingManagementPage(): JSX.Element {
  const [tab, setTab] = useState<P89ManagedListingStatus>("DRAFT");
  const [items, setItems] = useState<P89ManagedListingRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.listManagedListings({ status: tab, limit: 100 });
      setItems(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load listings.");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAction(action: string, id: number) {
    setMessage(null);
    try {
      if (action === "active") await apiClient.markManagedListingActive(id);
      if (action === "expired") await apiClient.markManagedListingExpired(id);
      if (action === "archive") await apiClient.archiveManagedListing(id);
      if (action === "sold") {
        window.location.href = `/listing-management/${id}?markSold=1`;
        return;
      }
      setMessage("Listing updated.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed.");
    }
  }

  const emptyHint = useMemo(() => `No ${tab.toLowerCase()} listings yet.`, [tab]);

  return (
    <PatriotPageLayout
      eyebrow="Sell"
      title="Listing Management"
      description="Track active listings, sold books, expired listings, and seller profit."
      showExpansionNav
      error={error}
    >
      {message ? <p className="mb-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{message}</p> : null}
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`rounded-full px-3 py-1 text-sm ${tab === t.key ? "bg-white text-red-800" : "border border-white/40 text-white"}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {loading ? <p className="text-sm text-blue-100">Loading…</p> : null}
      {!loading && items.length === 0 ? (
        <CollectorEmptyState title={emptyHint} description="Create a managed listing from a listing draft or inventory copy." />
      ) : null}
      <div className="space-y-3">
        {items.map((row) => (
          <ListingRow key={row.id} row={row} onAction={(a, id) => void handleAction(a, id)} />
        ))}
      </div>
    </PatriotPageLayout>
  );
}
