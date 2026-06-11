import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, apiClient, type RetailerOrderSnapshotRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatMoney(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(parsed);
}

function statusBadgeClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "confirmed" || normalized === "captured") {
    return "border-emerald-400/20 bg-emerald-400/10 text-emerald-100";
  }
  if (normalized === "failed" || normalized === "needs_review") {
    return "border-rose-400/20 bg-rose-400/10 text-rose-100";
  }
  return "border-amber-400/20 bg-amber-400/10 text-amber-100";
}

export function RetailerOrdersPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const syncRunId = searchParams.get("syncRunId");
  const [orders, setOrders] = useState<RetailerOrderSnapshotRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const highlightedSyncRunId = useMemo(() => syncRunId?.trim() || null, [syncRunId]);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    void apiClient
      .getRetailerOrders()
      .then((response) => {
        if (!cancelled) {
          setOrders(response.items);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof ApiError ? loadError.message : "Unable to load retailer orders.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Retailer Orders"
        title="Retailer Orders"
        description="Review retailer-captured comic orders directly from the retailer snapshot, without routing through import drafts."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {highlightedSyncRunId ? (
        <div className="mt-6">
          <StatusBanner tone="info">Showing orders from sync run #{highlightedSyncRunId}.</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Captured Orders</p>
            <h2 className="mt-1 text-2xl font-semibold text-white">Synced retailer orders</h2>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {isLoading ? (
            <p className="text-sm text-slate-400">Loading retailer orders...</p>
          ) : orders.length === 0 ? (
            <p className="text-sm text-slate-400">No retailer orders have been captured yet.</p>
          ) : (
            orders.map((order) => (
              <article
                key={order.id}
                className="rounded-2xl border border-white/10 bg-slate-950/50 p-4 transition hover:border-cyan-300/40 hover:bg-slate-950/70"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {order.retailer} Order #{order.retailer_order_number}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      {formatDate(order.order_date)} · {order.item_count} item
                      {order.item_count === 1 ? "" : "s"}
                    </p>
                  </div>
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(order.review_status)}`}
                  >
                    {order.review_status}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap gap-3 text-sm text-slate-300">
                  <span>
                    Total: <span className="font-medium text-white">{formatMoney(order.order_total)}</span>
                  </span>
                  <span>{order.cover_image_count} covers</span>
                  <span>{order.product_url_count} product links</span>
                  <span>{order.price_count} prices</span>
                  <span>{order.release_date_count} release dates</span>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => navigate(`/retailer-orders/${order.id}`)}
                    className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 font-semibold text-cyan-100 transition hover:bg-cyan-400/20"
                  >
                    Review Order
                  </button>
                  <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Captured from {order.retailer}
                  </span>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </AppShell>
  );
}
