import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type InventoryDetail } from "../api/client";
import { formatCurrencyAmount, formatUsdCurrency } from "../lib/currencyFormat";
import { StatusBanner } from "./StatusBanner";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function variantLine(detail: InventoryDetail): string {
  return [detail.cover_name, detail.printing, detail.ratio, detail.variant_type].filter(Boolean).join(" / ");
}

export function PortfolioInventoryDetailDrawer(props: {
  inventoryCopyId: number | null;
  onClose: () => void;
}): JSX.Element | null {
  const { inventoryCopyId, onClose } = props;
  const [detail, setDetail] = useState<InventoryDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (inventoryCopyId == null) {
      setDetail(null);
      setError(null);
      return;
    }

    let ignore = false;
    setLoading(true);
    setError(null);
    setDetail(null);

    void apiClient.getInventoryCopy(inventoryCopyId).then(
      (row) => {
        if (!ignore) {
          setDetail(row);
          setLoading(false);
        }
      },
      (err) => {
        if (!ignore) {
          setError(err instanceof ApiError ? err.message : "Unable to load this copy.");
          setLoading(false);
        }
      },
    );

    return () => {
      ignore = true;
    };
  }, [inventoryCopyId]);

  useEffect(() => {
    if (inventoryCopyId == null) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inventoryCopyId, onClose]);

  if (inventoryCopyId == null) {
    return null;
  }

  const marketFmv = detail?.current_market_fmv
    ? formatCurrencyAmount(detail.current_market_fmv, detail.fmv_currency_code ?? "USD")
    : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-slate-900/40"
        aria-label="Close inventory details"
        onClick={onClose}
      />
      <aside
        className="relative flex h-full w-full max-w-lg flex-col border-l border-slate-200 bg-white shadow-2xl sm:max-w-xl"
        aria-labelledby="portfolio-inventory-drawer-title"
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Inventory copy</p>
            <h2 id="portfolio-inventory-drawer-title" className="mt-1 text-lg font-semibold text-patriot-navy">
              {loading && !detail ? "Loading…" : detail ? `${detail.title} #${detail.issue_number}` : "Copy details"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
          {loading && !detail ? (
            <p className="text-sm text-slate-600">Loading copy details…</p>
          ) : null}
          {detail ? (
            <div className="space-y-5">
              <div className="flex gap-4">
                <div className="h-28 w-20 shrink-0 overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
                  {detail.cover_image_url ? (
                    <img src={detail.cover_image_url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <span className="flex h-full items-center justify-center text-2xl text-slate-400">📚</span>
                  )}
                </div>
                <div className="min-w-0 text-sm text-slate-700">
                  <p>{detail.publisher}</p>
                  {variantLine(detail) ? <p className="mt-1 text-slate-600">{variantLine(detail)}</p> : null}
                  <p className="mt-2 text-slate-600">
                    {detail.retailer} · Ordered {formatDate(detail.order_date)}
                  </p>
                  <p className="mt-1">
                    Paid {formatUsdCurrency(detail.acquisition_cost)}
                    {detail.received_at ? ` · Received ${formatDate(detail.received_at)}` : null}
                  </p>
                </div>
              </div>

              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Your FMV</dt>
                  <dd className="mt-1 font-semibold text-slate-900">
                    {detail.current_fmv ? formatUsdCurrency(detail.current_fmv) : "—"}
                  </dd>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Market FMV</dt>
                  <dd className="mt-1 font-semibold text-slate-900">{marketFmv ?? "—"}</dd>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Gain / loss</dt>
                  <dd className="mt-1 font-semibold text-slate-900">
                    {detail.gain_loss ? formatUsdCurrency(detail.gain_loss) : "—"}
                  </dd>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
                  <dd className="mt-1 font-semibold text-slate-900">
                    {detail.grade_status} · {detail.hold_status}
                  </dd>
                </div>
              </dl>

              {detail.inventory_intelligence ? (
                <div className="rounded-xl border border-slate-200 p-3 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Intelligence</p>
                  <p className="mt-2 text-slate-800">
                    Health: {detail.inventory_intelligence.inventory_health.replace(/_/g, " ")}
                    {detail.inventory_intelligence.has_cover_scan ? "" : " · No cover scan"}
                  </p>
                </div>
              ) : null}

              {detail.inventory_risks && detail.inventory_risks.length > 0 ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">Active risks</p>
                  <ul className="mt-2 space-y-1 text-amber-950">
                    {detail.inventory_risks.slice(0, 6).map((risk) => (
                      <li key={risk.risk_key}>
                        {risk.risk_type.replace(/_/g, " ")} ({risk.priority})
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {detail.condition_notes ? (
                <div className="rounded-xl border border-slate-200 p-3 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Condition notes</p>
                  <p className="mt-2 text-slate-800 whitespace-pre-wrap">{detail.condition_notes}</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <footer className="border-t border-slate-200 px-5 py-4">
          <Link
            to={`/inventory/${inventoryCopyId}`}
            className="inline-flex w-full justify-center rounded-2xl bg-patriot-blue px-4 py-3 text-sm font-semibold text-white hover:bg-blue-900"
          >
            Open full detail page
          </Link>
        </footer>
      </aside>
    </div>
  );
}
