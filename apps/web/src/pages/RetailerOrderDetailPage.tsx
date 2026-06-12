import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

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

function formatSummaryValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "None";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value, null, 2);
}

function enrichmentBadgeLabel(status: string | null | undefined): string | null {
  if (!status) return null;
  if (status === "matched") return "Matched";
  if (status === "partial_match") return "Partial Match";
  if (status === "needs_review") return "Needs Review";
  return status;
}

function enrichmentBadgeClass(status: string | null | undefined): string {
  if (status === "matched") {
    return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
  }
  if (status === "partial_match") {
    return "border-amber-400/30 bg-amber-400/10 text-amber-100";
  }
  return "border-rose-400/30 bg-rose-400/10 text-rose-100";
}

export function RetailerOrderDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const orderId = Number(id);
  const [order, setOrder] = useState<RetailerOrderSnapshotRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmStats, setConfirmStats] = useState<{
    inventoryCopies: number;
    linkedOrderId: number;
    retailer: string;
  } | null>(null);

  const debugSummary = useMemo(() => {
    if (!order) {
      return [];
    }
    return [
      ["Capture diagnostics", order.capture_quality_summary_json],
      ["Parser diagnostics", order.parser_quality_summary_json],
      ["Raw fields summary", order.raw_fields_summary_json],
    ] as const;
  }, [order]);

  useEffect(() => {
    let cancelled = false;
    if (!Number.isFinite(orderId)) {
      setError("Retailer order not found.");
      setIsLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setIsLoading(true);
    void apiClient
      .getRetailerOrder(orderId)
      .then((response) => {
        if (!cancelled) {
          setOrder(response);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof ApiError ? loadError.message : "Unable to load retailer order.");
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
  }, [orderId]);

  async function confirmOrder(): Promise<void> {
    if (!order) {
      return;
    }
    setIsSaving(true);
    setError(null);
    setNotice(null);
    setSuccess(null);
    setConfirmStats(null);
    try {
      const response = await apiClient.confirmRetailerOrder(order.id);
      setOrder(response);
      const copies = response.inventory_copies_created ?? response.total_ordered_quantity ?? 0;
      if (response.linked_order_id && copies > 0) {
        setConfirmStats({
          inventoryCopies: copies,
          linkedOrderId: response.linked_order_id,
          retailer: response.retailer,
        });
      }
      setSuccess(
        copies > 0
          ? `Confirmed. Created ${copies} inventory cop${copies === 1 ? "y" : "ies"} in your portfolio.`
          : "Retailer order confirmed.",
      );
    } catch (confirmError) {
      if (confirmError instanceof ApiError && confirmError.status === 408) {
        // The confirm request timed out client-side, but the backend may still be
        // finishing. Surface a non-blocking notice and refresh the order so the UI
        // self-heals once materialization completes (idempotent on the server).
        setNotice(confirmError.message);
        try {
          const refreshed = await apiClient.getRetailerOrder(order.id);
          setOrder(refreshed);
        } catch {
          // Leave the notice in place; user can refresh manually.
        }
      } else {
        setError(confirmError instanceof ApiError ? confirmError.message : "Unable to confirm retailer order.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Retailer Order"
        title="Retailer Order"
        description="Review the retailer snapshot directly, inspect the captured items, and confirm the order when it is ready for receiving."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {notice ? (
        <div className="mt-6">
          <StatusBanner tone="warning">{notice}</StatusBanner>
        </div>
      ) : null}
      {success ? (
        <div className="mt-6 space-y-3">
          <StatusBanner tone="success">{success}</StatusBanner>
          {confirmStats ? (
            <div className="flex flex-wrap gap-3 text-sm">
              <Link
                to={`/retailer-orders/${orderId}`}
                className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 font-medium text-emerald-100 hover:bg-emerald-400/20"
              >
                Retail order detail
              </Link>
              <Link
                to={`/dashboard?q=${encodeURIComponent(confirmStats.retailer)}`}
                className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 font-medium text-cyan-100 hover:bg-cyan-400/20"
              >
                Portfolio ({confirmStats.inventoryCopies} new)
              </Link>
              <Link
                to={`/dashboard?q=${encodeURIComponent(confirmStats.retailer)}`}
                className="rounded-lg border border-white/10 px-3 py-2 font-medium text-slate-200 hover:bg-white/5"
              >
                Filter inventory by retailer
              </Link>
            </div>
          ) : null}
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        {isLoading ? (
          <p className="text-sm text-slate-400">Loading retailer order...</p>
        ) : order ? (
          <>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Retailer Snapshot</p>
                <h2 className="mt-1 text-2xl font-semibold text-white">
                  {order.retailer} Order #{order.retailer_order_number}
                </h2>
                <p className="mt-2 text-sm text-slate-300">
                  {formatDate(order.order_date)} · {order.item_count} item{order.item_count === 1 ? "" : "s"} ·{" "}
                  {formatMoney(order.order_total)}
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <span
                  className={`inline-flex rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(order.review_status)}`}
                >
                  {order.review_status}
                </span>
                <button
                  type="button"
                  onClick={() => void confirmOrder()}
                  disabled={isSaving}
                  className="rounded-xl bg-cyan-400 px-4 py-2 font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? "Saving..." : "Confirm Retailer Order"}
                </button>
                <button
                  type="button"
                  onClick={() => navigate("/retailer-orders")}
                  className="rounded-xl border border-white/10 px-4 py-2 font-semibold text-white transition hover:bg-white/5"
                >
                  Back to Retailer Orders
                </button>
                <button
                  type="button"
                  onClick={() => navigate("/connected-retailers")}
                  className="rounded-xl border border-white/10 px-4 py-2 font-semibold text-white transition hover:bg-white/5"
                >
                  Back to Connected Retailers
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Items parsed</p>
                <p className="mt-2 text-2xl font-semibold text-white">{order.item_count}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Covers found</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {order.cover_image_count}/{order.item_count}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Product links found</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {order.product_url_count}/{order.item_count}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Prices found</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {order.price_count}/{order.item_count}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Release dates found</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {order.release_date_count}/{order.item_count}
                </p>
              </div>
            </div>

            {order.item_count === 0 || order.cover_image_count === 0 || order.price_count === 0 ? (
              <div className="mt-4">
                <StatusBanner tone="warning">This capture may be incomplete.</StatusBanner>
              </div>
            ) : null}

            {order.item_count > 0 &&
            (order.product_url_count < order.item_count || order.release_date_count < order.item_count) ? (
              <div className="mt-4">
                <StatusBanner tone="warning">
                  Some optional enrichment fields are missing (product links or release dates). ComicOS can fill
                  these later from catalog data.
                </StatusBanner>
              </div>
            ) : null}

            <div className="mt-6 grid gap-4">
              {order.items.map((item) => (
                <article
                  key={item.id}
                  className="grid gap-4 rounded-2xl border border-white/10 bg-slate-950/50 p-4 md:grid-cols-[120px,1fr]"
                >
                  <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/80">
                    {item.cover_image_url || item.image_url ? (
                      <img
                        src={item.cover_image_url || item.image_url || ""}
                        alt={item.title}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-36 items-center justify-center text-xs uppercase tracking-[0.16em] text-slate-500">
                        No cover image
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                        <p className="mt-1 text-sm text-slate-400">
                          {item.publisher ?? "Publisher missing"} · {item.issue_number ?? "Issue missing"}
                        </p>
                      </div>
                      <span className="rounded-full border border-white/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                        {item.item_status ?? "Status missing"}
                      </span>
                      {enrichmentBadgeLabel(item.enrichment_status) ? (
                        <span
                          className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] ${enrichmentBadgeClass(item.enrichment_status)}`}
                        >
                          {enrichmentBadgeLabel(item.enrichment_status)}
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-3 flex flex-wrap gap-3 text-sm text-slate-300">
                      <span>Qty {item.quantity}</span>
                      <span>Unit {formatMoney(item.unit_price)}</span>
                      <span>Line {formatMoney(item.total_price)}</span>
                      <span>Release {item.release_date ? formatDate(item.release_date) : "Missing"}</span>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-3">
                      {item.cover_name ? (
                        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200">
                          {item.cover_name}
                        </span>
                      ) : null}
                      {item.variant_type ? (
                        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200">
                          {item.variant_type}
                        </span>
                      ) : null}
                      {item.product_url ? (
                        <a
                          href={item.product_url}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-full border border-cyan-400/30 px-3 py-1 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/10"
                        >
                          Open product
                        </a>
                      ) : (
                        <span className="rounded-full border border-amber-400/30 px-3 py-1 text-xs text-amber-100">
                          Product URL missing
                        </span>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>

            <details className="mt-6 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <summary className="cursor-pointer list-none text-sm font-semibold text-white">
                Debug details
              </summary>
              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                {debugSummary.map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
                    <pre className="mt-3 whitespace-pre-wrap break-words text-xs text-slate-200">
                      {formatSummaryValue(value)}
                    </pre>
                  </div>
                ))}
              </div>
            </details>
          </>
        ) : (
          <StatusBanner tone="error">Retailer order not found.</StatusBanner>
        )}
      </section>
    </AppShell>
  );
}
