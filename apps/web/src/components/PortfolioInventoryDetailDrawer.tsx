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

export function PortfolioInventoryCardExpand(props: {
  inventoryCopyId: number;
  onClose: () => void;
}): JSX.Element {
  const { inventoryCopyId, onClose } = props;
  const [detail, setDetail] = useState<InventoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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

  const marketFmv = detail?.current_market_fmv
    ? formatCurrencyAmount(detail.current_market_fmv, detail.fmv_currency_code ?? "USD")
    : null;

  return (
    <div
      className="border-t border-slate-200 bg-slate-50 px-3 py-4"
      aria-labelledby={`portfolio-card-expand-${inventoryCopyId}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p
          id={`portfolio-card-expand-${inventoryCopyId}`}
          className="text-xs font-semibold uppercase tracking-wide text-slate-500"
        >
          Copy details
        </p>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-[10px] font-semibold text-slate-700 hover:bg-slate-100"
        >
          Close
        </button>
      </div>

      {error ? (
        <div className="mt-3">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {loading && !detail ? <p className="mt-3 text-sm text-slate-600">Loading details…</p> : null}

      {detail ? (
        <div className="mt-3 space-y-4">
          <div className="flex gap-3">
            <div className="h-24 w-16 shrink-0 overflow-hidden rounded-md border border-slate-200 bg-white">
              {detail.cover_image_url ? (
                <img src={detail.cover_image_url} alt="" className="h-full w-full object-cover" />
              ) : (
                <span className="flex h-full items-center justify-center text-xl text-slate-400">📚</span>
              )}
            </div>
            <div className="min-w-0 text-xs text-slate-700">
              <p className="text-sm font-semibold text-patriot-navy">
                {detail.title} #{detail.issue_number}
              </p>
              <p className="mt-1">{detail.publisher}</p>
              {variantLine(detail) ? <p className="text-slate-600">{variantLine(detail)}</p> : null}
              <p className="mt-2 text-slate-600">
                {detail.retailer} · Ordered {formatDate(detail.order_date)}
              </p>
              <p>
                Paid {formatUsdCurrency(detail.acquisition_cost)}
                {detail.received_at ? ` · Received ${formatDate(detail.received_at)}` : null}
              </p>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Your FMV</dt>
              <dd className="mt-0.5 font-semibold text-slate-900">
                {detail.current_fmv ? formatUsdCurrency(detail.current_fmv) : "—"}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Market</dt>
              <dd className="mt-0.5 font-semibold text-slate-900">{marketFmv ?? "—"}</dd>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Gain / loss</dt>
              <dd className="mt-0.5 font-semibold text-slate-900">
                {detail.gain_loss ? formatUsdCurrency(detail.gain_loss) : "—"}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Status</dt>
              <dd className="mt-0.5 font-semibold text-slate-900">
                {detail.grade_status} · {detail.hold_status}
              </dd>
            </div>
          </dl>

          {detail.inventory_intelligence ? (
            <p className="text-xs text-slate-700">
              Health: {detail.inventory_intelligence.inventory_health.replace(/_/g, " ")}
              {detail.inventory_intelligence.has_cover_scan ? "" : " · No cover scan"}
            </p>
          ) : null}

          {detail.inventory_risks && detail.inventory_risks.length > 0 ? (
            <ul className="text-xs text-amber-900">
              {detail.inventory_risks.slice(0, 4).map((risk) => (
                <li key={risk.risk_key}>
                  {risk.risk_type.replace(/_/g, " ")} ({risk.priority})
                </li>
              ))}
            </ul>
          ) : null}

          {detail.condition_notes ? (
            <p className="text-xs text-slate-700 whitespace-pre-wrap">{detail.condition_notes}</p>
          ) : null}

          <Link
            to={`/inventory/${inventoryCopyId}`}
            className="inline-flex rounded-lg border border-patriot-blue bg-white px-3 py-1.5 text-[10px] font-semibold text-patriot-blue hover:bg-blue-50"
          >
            Open full detail page
          </Link>
        </div>
      ) : null}
    </div>
  );
}
