import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type InventoryDetail,
  type InventoryItem,
  type InventoryUpdatePayload,
} from "../api/client";
import { formatCurrencyAmount, formatUsdCurrency } from "../lib/currencyFormat";
import { FavoriteStarRating } from "./FavoriteStarRating";
import { StatusBanner } from "./StatusBanner";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatDateSafe(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime()) || d.getFullYear() < 1971) return "—";
  return formatDate(value);
}

function variantLine(item: InventoryItem | InventoryDetail): string {
  return [item.cover_name, item.printing, item.ratio, item.variant_type].filter(Boolean).join(" / ");
}

const PANELS = [
  { id: "catalog", label: "Catalog" },
  { id: "valuation", label: "Valuation" },
  { id: "acquisition", label: "Order" },
  { id: "copy", label: "Copy & notes" },
] as const;

const selectClass =
  "rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 outline-none focus:border-blue-500";

export function PortfolioInventoryCardExpand(props: {
  item: InventoryItem;
  inventoryCopyId: number;
  onClose: () => void;
  isSaving: boolean;
  fMvDrafts: Record<number, string>;
  gradeDrafts: Record<number, InventoryItem["grade_status"]>;
  holdDrafts: Record<number, InventoryItem["hold_status"]>;
  starDrafts: Record<number, string>;
  normalizeDecimalInput: (value: string) => string | null;
  onFmvDraftChange: (id: number, value: string) => void;
  onGradeDraftChange: (id: number, value: InventoryItem["grade_status"]) => void;
  onHoldDraftChange: (id: number, value: InventoryItem["hold_status"]) => void;
  onStarDraftChange: (id: number, value: string) => void;
  onSave: (id: number, payload: InventoryUpdatePayload) => Promise<void>;
  onOpenNotes: (item: InventoryItem) => void;
}): JSX.Element {
  const {
    item,
    inventoryCopyId,
    onClose,
    isSaving,
    fMvDrafts,
    gradeDrafts,
    holdDrafts,
    starDrafts,
    normalizeDecimalInput,
    onFmvDraftChange,
    onGradeDraftChange,
    onHoldDraftChange,
    onStarDraftChange,
    onSave,
    onOpenNotes,
  } = props;

  const [panelIndex, setPanelIndex] = useState(0);
  const [detail, setDetail] = useState<InventoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError(null);

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

  const panel = PANELS[panelIndex];
  const marketFmv = item.current_market_fmv
    ? formatCurrencyAmount(item.current_market_fmv, item.fmv_currency_code ?? "USD")
    : null;
  const variant = variantLine(item) || "Standard cover";

  const goPrev = () => setPanelIndex((i) => (i <= 0 ? PANELS.length - 1 : i - 1));
  const goNext = () => setPanelIndex((i) => (i >= PANELS.length - 1 ? 0 : i + 1));

  return (
    <div
      className="border-t border-slate-200 bg-slate-50 px-3 py-3"
      aria-labelledby={`portfolio-card-expand-${inventoryCopyId}`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={goPrev}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            aria-label="Previous detail section"
          >
            ‹
          </button>
          <p
            id={`portfolio-card-expand-${inventoryCopyId}`}
            className="min-w-[7rem] text-center text-xs font-semibold uppercase tracking-wide text-slate-600"
          >
            {panel.label}
          </p>
          <button
            type="button"
            onClick={goNext}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            aria-label="Next detail section"
          >
            ›
          </button>
        </div>
        <div className="flex items-center gap-1">
          {PANELS.map((p, idx) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPanelIndex(idx)}
              className={`h-1.5 w-1.5 rounded-full ${
                idx === panelIndex ? "bg-patriot-blue" : "bg-slate-300"
              }`}
              aria-label={`Show ${p.label}`}
            />
          ))}
          <button
            type="button"
            onClick={onClose}
            className="ml-2 rounded-lg border border-slate-300 bg-white px-2 py-1 text-[10px] font-semibold text-slate-700 hover:bg-slate-100"
          >
            Close
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-3">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {loading && !detail ? <p className="mt-3 text-sm text-slate-600">Loading details…</p> : null}

      <div className="mt-3 min-h-[8rem]">
        {panel.id === "catalog" ? (
          <div className="flex gap-4">
            <div className="h-32 w-24 shrink-0 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              {item.cover_image_url ? (
                <img src={item.cover_image_url} alt="" className="h-full w-full object-cover" />
              ) : (
                <span className="flex h-full items-center justify-center text-2xl text-slate-400">📚</span>
              )}
            </div>
            <dl className="min-w-0 space-y-2 text-xs text-slate-700">
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Title</dt>
                <dd className="font-semibold text-patriot-navy">
                  {item.title} #{item.issue_number}
                </dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Publisher</dt>
                <dd>{item.publisher}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Variant</dt>
                <dd>{variant}</dd>
              </div>
              {item.release_year != null ? (
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-slate-500">Release year</dt>
                  <dd>{item.release_year}</dd>
                </div>
              ) : null}
              {item.catalog_match_id != null ? (
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-slate-500">Catalog match</dt>
                  <dd>#{item.catalog_match_id}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}

        {panel.id === "valuation" ? (
          <div className="space-y-3 text-xs">
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-white p-2">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Market FMV</dt>
                <dd className="mt-0.5 font-semibold text-slate-900">{marketFmv ?? "—"}</dd>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-2">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Your FMV</dt>
                <dd className="mt-0.5 font-semibold text-slate-900">
                  {item.current_fmv ? formatUsdCurrency(item.current_fmv) : "—"}
                </dd>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-2">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Gain / loss</dt>
                <dd className="mt-0.5 font-semibold text-slate-900">
                  {item.gain_loss ? formatUsdCurrency(item.gain_loss) : "—"}
                </dd>
              </div>
            </dl>
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
              <span className="text-slate-500">Set your FMV</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={fMvDrafts[inventoryCopyId] ?? ""}
                onChange={(event) => onFmvDraftChange(inventoryCopyId, event.target.value)}
                className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-900 outline-none focus:border-blue-500"
              />
              <button
                type="button"
                disabled={isSaving}
                onClick={() =>
                  void onSave(inventoryCopyId, {
                    current_fmv: normalizeDecimalInput(fMvDrafts[inventoryCopyId] ?? ""),
                  })
                }
                className="rounded-lg border border-blue-300 bg-blue-50 px-2 py-1 text-[10px] font-semibold text-patriot-blue hover:bg-blue-100 disabled:opacity-50"
              >
                Save
              </button>
              {item.valuation_scope ? (
                <span className="rounded-md border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[9px] uppercase text-blue-800">
                  {item.valuation_scope.replace(/_/g, " ")}
                </span>
              ) : null}
            </div>
            {detail?.current_market_fmv && detail.current_fmv ? (
              <p className="text-slate-600">
                Detail market: {formatCurrencyAmount(detail.current_market_fmv, detail.fmv_currency_code ?? "USD")}
              </p>
            ) : null}
          </div>
        ) : null}

        {panel.id === "acquisition" ? (
          <dl className="grid gap-2 text-xs sm:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Retailer</dt>
              <dd className="mt-0.5 font-medium text-slate-900">{item.retailer}</dd>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Ordered</dt>
              <dd className="mt-0.5 font-medium text-slate-900">{formatDateSafe(item.order_date)}</dd>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Paid</dt>
              <dd className="mt-0.5 font-medium text-slate-900">{formatUsdCurrency(item.acquisition_cost)}</dd>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-2">
              <dt className="text-[10px] uppercase tracking-wide text-slate-500">Received</dt>
              <dd className="mt-0.5 font-medium text-slate-900">{formatDateSafe(item.received_at)}</dd>
            </div>
            {item.expected_ship_date ? (
              <div className="rounded-lg border border-slate-200 bg-white p-2">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Expected ship</dt>
                <dd className="mt-0.5 font-medium text-slate-900">{formatDateSafe(item.expected_ship_date)}</dd>
              </div>
            ) : null}
            {item.release_date ? (
              <div className="rounded-lg border border-slate-200 bg-white p-2">
                <dt className="text-[10px] uppercase tracking-wide text-slate-500">Release date</dt>
                <dd className="mt-0.5 font-medium text-slate-900">{formatDateSafe(item.release_date)}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}

        {panel.id === "copy" ? (
          <div className="space-y-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={gradeDrafts[inventoryCopyId] ?? item.grade_status}
                onChange={(event) =>
                  onGradeDraftChange(inventoryCopyId, event.target.value as InventoryItem["grade_status"])
                }
                onBlur={() =>
                  void onSave(inventoryCopyId, {
                    grade_status: gradeDrafts[inventoryCopyId] ?? item.grade_status,
                  })
                }
                className={selectClass}
                aria-label="Grade status"
              >
                <option value="raw">Raw</option>
                <option value="submitted">Submitted</option>
                <option value="graded">Graded</option>
              </select>
              <select
                value={holdDrafts[inventoryCopyId] ?? item.hold_status}
                onChange={(event) =>
                  onHoldDraftChange(inventoryCopyId, event.target.value as InventoryItem["hold_status"])
                }
                onBlur={() =>
                  void onSave(inventoryCopyId, {
                    hold_status: holdDrafts[inventoryCopyId] ?? item.hold_status,
                  })
                }
                className={selectClass}
                aria-label="Hold status"
              >
                <option value="hold">Hold</option>
                <option value="sell">Sell</option>
                <option value="sold">Sold</option>
              </select>
              <FavoriteStarRating
                size="sm"
                label={`Favorite rating for ${item.title}`}
                disabled={isSaving}
                value={starDrafts[inventoryCopyId] ? Number(starDrafts[inventoryCopyId]) : item.star_rating}
                onChange={(rating) => {
                  onStarDraftChange(inventoryCopyId, rating ? String(rating) : "");
                  void onSave(inventoryCopyId, { star_rating: rating });
                }}
              />
              <button
                type="button"
                onClick={() => onOpenNotes(item)}
                className="rounded-lg border border-slate-300 px-2 py-1 text-[10px] font-semibold text-slate-700 hover:border-blue-400 hover:text-patriot-blue"
              >
                Notes
              </button>
            </div>

            {detail?.inventory_intelligence ? (
              <p className="text-slate-700">
                Health: {detail.inventory_intelligence.inventory_health.replace(/_/g, " ")}
                {detail.inventory_intelligence.has_cover_scan ? "" : " · No cover scan"}
              </p>
            ) : null}

            {detail?.inventory_risks && detail.inventory_risks.length > 0 ? (
              <ul className="text-amber-900">
                {detail.inventory_risks.slice(0, 6).map((risk) => (
                  <li key={risk.risk_key}>
                    {risk.risk_type.replace(/_/g, " ")} ({risk.priority})
                  </li>
                ))}
              </ul>
            ) : null}

            {detail?.condition_notes ? (
              <p className="whitespace-pre-wrap text-slate-700">{detail.condition_notes}</p>
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
    </div>
  );
}
