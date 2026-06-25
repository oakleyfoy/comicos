import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type RetailerOrderItemSnapshotRead,
  type RetailerOrderReEnrichResponse,
  type RetailerOrderSnapshotRead,
} from "../api/client";
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

function reviewReleaseLabel(item: RetailerOrderItemSnapshotRead): string {
  if (item.release_date) {
    return formatDate(item.release_date);
  }
  // A missing release date is expected before catalog enrichment completes; it is
  // not an import failure, so frame it as pending catalog review.
  return "Catalog review pending";
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

function orderReviewStatusKey(status: string | null | undefined): string {
  return (status ?? "").trim().toLowerCase();
}

function retailerOrderIsConfirmed(order: RetailerOrderSnapshotRead): boolean {
  if (order.linked_order_id != null || order.linked_acquisition_id != null) {
    return true;
  }
  return orderReviewStatusKey(order.review_status) === "confirmed";
}

function inventoryCopyCount(order: RetailerOrderSnapshotRead): number {
  return order.inventory_copies_created ?? order.total_ordered_quantity ?? 0;
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
  const [isReenriching, setIsReenriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<RetailerOrderReEnrichResponse | null>(null);

  const orderConfirmed = order != null && retailerOrderIsConfirmed(order);
  const orderCopyCount = order ? inventoryCopyCount(order) : 0;

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

  function applyConfirmedOrderState(next: RetailerOrderSnapshotRead): void {
    setOrder(next);
    const copies = inventoryCopyCount(next);
    if (copies > 0 && (next.linked_order_id != null || next.linked_acquisition_id != null || retailerOrderIsConfirmed(next))) {
      setConfirmStats({
        inventoryCopies: copies,
        linkedOrderId: next.linked_order_id ?? next.linked_acquisition_id ?? 0,
        retailer: next.retailer,
      });
      setSuccess(
        `Confirmed. Created ${copies} inventory cop${copies === 1 ? "y" : "ies"} in your portfolio.`,
      );
      return;
    }
    if (retailerOrderIsConfirmed(next)) {
      setSuccess("Retailer order confirmed.");
    }
  }

  async function pollRetailerOrderUntilConfirmed(
    retailerOrderId: number,
    options: { attempts: number; intervalMs: number },
  ): Promise<RetailerOrderSnapshotRead | null> {
    const { attempts, intervalMs } = options;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      if (attempt > 0) {
        await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
      }
      try {
        const refreshed = await apiClient.getRetailerOrder(retailerOrderId);
        if (retailerOrderIsConfirmed(refreshed) && inventoryCopyCount(refreshed) > 0) {
          return refreshed;
        }
      } catch {
        // Keep polling until attempts are exhausted.
      }
    }
    return null;
  }

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
      const response = await apiClient.confirmRetailerOrder(order.id, order.item_count);
      applyConfirmedOrderState(response);
    } catch (confirmError) {
      if (confirmError instanceof ApiError && confirmError.status === 408) {
        const timeoutNotice =
          confirmError.message || "Confirmation may still be processing. Refresh or check your Portfolio.";
        const refreshed = await pollRetailerOrderUntilConfirmed(order.id, { attempts: 15, intervalMs: 2_000 });
        if (refreshed) {
          applyConfirmedOrderState(refreshed);
        } else {
          setNotice(timeoutNotice);
        }
      } else {
        const maybeDone = await pollRetailerOrderUntilConfirmed(order.id, { attempts: 5, intervalMs: 1_500 });
        if (maybeDone) {
          applyConfirmedOrderState(maybeDone);
        } else {
          const legacyRetired =
            confirmError instanceof ApiError &&
            confirmError.status === 410 &&
            confirmError.message.toLowerCase().includes("legacy customer orders");
          setError(
            legacyRetired
              ? "Add to portfolio is blocked by a server setting (legacy order retirement). Deploy the latest API or ask ops to enable retailer portfolio adds."
              : confirmError instanceof ApiError && confirmError.status === 500
                ? "Add to portfolio failed on the server (often the production DB no longer has legacy order tables). Run or deploy the latest ComicOS API with retailer acquisition materialization, then try again."
                : confirmError instanceof ApiError
                  ? confirmError.message
                  : "Unable to confirm retailer order.",
          );
        }
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function reenrichOrder(): Promise<void> {
    if (!order) {
      return;
    }
    setIsReenriching(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiClient.reenrichRetailerOrder(order.id);
      setEnrichResult(result);
      const matched = Number(result.enrichment_summary?.matched_items ?? 0);
      const needsReview = Number(result.enrichment_summary?.needs_review_items ?? 0);
      setSuccess(
        `Catalog enrichment complete: ${matched} matched, ${needsReview} need review.`,
      );
      try {
        const refreshed = await apiClient.getRetailerOrder(order.id);
        setOrder(refreshed);
      } catch {
        // Non-fatal: diagnostics are still shown from the re-enrich response.
      }
    } catch (reenrichError) {
      setError(
        reenrichError instanceof ApiError
          ? reenrichError.message
          : "Unable to re-run catalog enrichment.",
      );
    } finally {
      setIsReenriching(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Retailer Order"
        title="Retailer Order"
        description="Captured retailer orders stay here until you confirm them into your ComicOS portfolio (inventory)."
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
                  {orderConfirmed ? "CONFIRMED" : order.review_status}
                </span>
                {orderConfirmed ? (
                  <Link
                    to={`/dashboard?q=${encodeURIComponent(order.retailer)}`}
                    className="rounded-xl bg-emerald-400 px-4 py-2 font-semibold text-slate-950 transition hover:bg-emerald-300"
                  >
                    Open portfolio
                    {orderCopyCount > 0 ? ` (${orderCopyCount})` : ""}
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => void confirmOrder()}
                    disabled={isSaving}
                    className="rounded-xl bg-cyan-400 px-4 py-2 font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSaving ? "Adding to portfolio…" : "Add to portfolio"}
                  </button>
                )}
                {orderConfirmed && order.linked_order_id ? (
                  <button
                    type="button"
                    onClick={() => void confirmOrder()}
                    disabled={isSaving}
                    className="rounded-xl border border-white/10 px-4 py-2 font-semibold text-white transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSaving ? "Syncing…" : "Re-sync portfolio link"}
                  </button>
                ) : null}
                {order.linked_order_id ? (
                  <button
                    type="button"
                    onClick={() => void reenrichOrder()}
                    disabled={isReenriching}
                    className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isReenriching ? "Matching catalog..." : "Re-run catalog enrichment"}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => navigate("/retailer-orders")}
                  className="rounded-xl border border-white/10 px-4 py-2 font-semibold text-white transition hover:bg-white/5"
                >
                  Back to Retailer Orders
                </button>
                <button
                  type="button"
                  onClick={() => navigate("/connected-retailers/import")}
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

            {enrichResult ? (
              <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Catalog enrichment diagnostics
                  </p>
                  <p className="text-sm text-slate-300">
                    {Number(enrichResult.enrichment_summary?.matched_items ?? 0)} matched ·{" "}
                    {Number(enrichResult.enrichment_summary?.needs_review_items ?? 0)} need review
                  </p>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="text-slate-500">
                      <tr>
                        <th className="py-1 pr-3 font-medium">Series</th>
                        <th className="py-1 pr-3 font-medium">Issue</th>
                        <th className="py-1 pr-3 font-medium">Candidates</th>
                        <th className="py-1 pr-3 font-medium">Score</th>
                        <th className="py-1 pr-3 font-medium">Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {enrichResult.lines.map((line) => {
                        const reason = line.rejection_reason ?? "";
                        const catalogMissing =
                          !line.matched &&
                          (reason.includes("no_candidates") || reason.includes("missing"));
                        return (
                          <tr key={line.line_index} className="border-t border-white/5">
                            <td className="py-1 pr-3 text-slate-200">
                              {line.series_search_title || line.raw_title || "—"}
                            </td>
                            <td className="py-1 pr-3">{line.parsed_issue_number || "—"}</td>
                            <td className="py-1 pr-3">{line.candidate_count}</td>
                            <td className="py-1 pr-3">{line.match_score ?? "—"}</td>
                            <td className="py-1 pr-3">
                              {line.matched ? (
                                <span className="text-emerald-300">Matched</span>
                              ) : catalogMissing ? (
                                <span className="text-amber-300">Catalog missing</span>
                              ) : (
                                <span className="text-slate-400">
                                  Needs review{reason ? ` (${reason})` : ""}
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            {!orderConfirmed ? (
              <div className="mt-4">
                <StatusBanner tone="info">
                  <strong className="font-semibold">CAPTURED</strong> means Midtown data is saved in ComicOS only.
                  Books are not in your portfolio until you click <strong className="font-semibold">Add to portfolio</strong>.
                  Catalog badges can stay on “Review pending” until background matching runs; that does not block adding.
                </StatusBanner>
              </div>
            ) : null}

            {isSaving ? (
              <div className="mt-4">
                <StatusBanner tone="info">
                  Creating inventory and linking your default portfolio collection. Large orders can take up to a few
                  minutes—this page will update when finished.
                </StatusBanner>
              </div>
            ) : null}

            {order.item_count === 0 || order.cover_image_count === 0 || order.price_count === 0 ? (
              <div className="mt-4">
                <StatusBanner tone="warning">This capture may be incomplete.</StatusBanner>
              </div>
            ) : null}

            {order.item_count > 0 && order.release_date_count < order.item_count ? (
              <div className="mt-4">
                <StatusBanner tone="info">
                  Some release dates are still pending catalog review. ComicOS fills release and FOC dates from
                  catalog data once each book is matched.
                </StatusBanner>
              </div>
            ) : null}

            <div className="mt-6 grid gap-4">
              {order.items.map((item) => (
                <article
                  key={item.id}
                  className="flex gap-4 rounded-2xl border border-white/10 bg-slate-950/50 p-4"
                >
                  <div
                    data-testid="retailer-review-cover"
                    className="h-[120px] w-20 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-slate-900/80 sm:h-[132px] sm:w-[88px]"
                  >
                    {item.cover_image_url || item.image_url ? (
                      <img
                        src={item.cover_image_url || item.image_url || ""}
                        alt={item.title}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center px-1 text-center text-[10px] uppercase tracking-[0.14em] text-slate-500">
                        No cover
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
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
                      <span>Release {reviewReleaseLabel(item)}</span>
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
                      <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                        Catalog: {enrichmentBadgeLabel(item.enrichment_status) ?? "Review pending"}
                      </span>
                      {item.product_url ? (
                        <a
                          href={item.product_url}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-full border border-cyan-400/30 px-3 py-1 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/10"
                        >
                          Open product
                        </a>
                      ) : null}
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

              <div className="mt-4 overflow-x-auto">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Per-line diagnostics</p>
                <table className="mt-2 w-full min-w-[640px] text-left text-xs text-slate-300">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="py-1 pr-3">Title</th>
                      <th className="py-1 pr-3">Enrichment</th>
                      <th className="py-1 pr-3">Catalog match</th>
                      <th className="py-1 pr-3">Release date</th>
                      <th className="py-1 pr-3">Product URL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((item) => (
                      <tr key={item.id} className="border-t border-white/5">
                        <td className="py-1 pr-3 text-slate-200">{item.title}</td>
                        <td className="py-1 pr-3">{item.enrichment_status ?? "pending"}</td>
                        <td className="py-1 pr-3">{item.catalog_match_id ?? "none"}</td>
                        <td className="py-1 pr-3">{item.release_date ? formatDate(item.release_date) : "missing"}</td>
                        <td className="py-1 pr-3">{item.product_url ? "present" : "missing"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
