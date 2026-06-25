import { Link } from "react-router-dom";

import {
  type InventoryActionCenterCategory,
  type InventoryItem,
  type InventoryRiskType,
  type InventoryUpdatePayload,
  type OrderArrivalClassification,
} from "../api/client";
import { formatCurrencyAmount, formatUsdCurrency } from "../lib/currencyFormat";
import { canQuickReceiveInventoryCopy } from "../lib/inventoryReceiving";
import { FavoriteStarRating } from "./FavoriteStarRating";

type Chip = { key: string; label: string; className: string; title?: string };

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function variantLabel(item: InventoryItem): string {
  return [item.cover_name, item.printing, item.ratio, item.variant_type].filter(Boolean).join(" / ");
}

function assetStateShort(state: InventoryItem["asset_state"]): string {
  switch (state) {
    case "in_hand":
      return "In hand";
    case "ordered_not_received":
      return "Not received";
    case "preorder_not_released_yet":
      return "Preorder";
    case "cancelled":
      return "Cancelled";
    default:
      return String(state);
  }
}

function assetStateTone(state: InventoryItem["asset_state"]): string {
  switch (state) {
    case "in_hand":
      return "border-emerald-300 bg-emerald-50 text-emerald-900";
    case "ordered_not_received":
      return "border-amber-300 bg-amber-50 text-amber-900";
    case "preorder_not_released_yet":
      return "border-blue-300 bg-blue-50 text-blue-900";
    case "cancelled":
      return "border-red-300 bg-red-50 text-red-900";
    default:
      return "border-slate-200 bg-slate-50 text-slate-700";
  }
}

function gainLossClass(value: string): string {
  const n = Number.parseFloat(value);
  if (Number.isNaN(n) || n === 0) return "text-slate-500";
  return n > 0 ? "text-emerald-700" : "text-red-700";
}

function inventoryRiskLabel(value: InventoryRiskType): string {
  switch (value) {
    case "needs_scan":
      return "Needs scan";
    case "needs_canonical_review":
      return "Canon review";
    case "needs_conflict_review":
      return "Conflict";
    case "released_not_received":
      return "Not received";
    default:
      return value.replace(/_/g, " ");
  }
}

function actionShort(cat: InventoryActionCenterCategory): string {
  switch (cat) {
    case "scan_missing_cover":
      return "No scan";
    case "review_run_gap":
      return "Run gap";
    default:
      return cat.replace(/_/g, " ");
  }
}

function orderArrivalShort(value: OrderArrivalClassification): string {
  switch (value) {
    case "released_not_received":
      return "Released, not recv";
    case "expected_to_ship_soon":
      return "Ships soon";
    case "overdue_expected_ship":
      return "Ship overdue";
    default:
      return value.replace(/_/g, " ");
  }
}

function buildSignalChips(item: InventoryItem): Chip[] {
  const chips: Chip[] = [];
  const intel = item.inventory_intelligence;

  if (intel) {
    if (intel.inventory_health !== "healthy") {
      chips.push({
        key: "health",
        label: intel.inventory_health.replace(/_/g, " "),
        className: "border-sky-300 bg-sky-50 text-sky-900",
      });
    }
    if (!intel.has_cover_scan) {
      chips.push({
        key: "unscanned",
        label: "Unscanned",
        className: "border-slate-300 bg-slate-100 text-slate-700",
      });
    }
    if (intel.preorder_missing_release_calendar) {
      chips.push({
        key: "preorder-cal",
        label: "Preorder date gap",
        className: "border-amber-300 bg-amber-50 text-amber-900",
      });
    }
  }

  if (item.duplicate_ownership) {
    chips.push({
      key: "dup",
      label: "Multi-copy",
      className: "border-slate-300 bg-slate-100 text-slate-800",
      title: item.duplicate_ownership.classification,
    });
  }

  if (item.run_detection) {
    chips.push({
      key: "run",
      label: item.run_detection.series_status.replace(/_/g, " "),
      className: "border-slate-300 bg-slate-100 text-slate-800",
    });
  }

  for (const risk of item.inventory_risks ?? []) {
    chips.push({
      key: `risk-${risk.risk_key}`,
      label: inventoryRiskLabel(risk.risk_type),
      className:
        risk.priority === "critical" || risk.priority === "high"
          ? "border-rose-300 bg-rose-50 text-rose-900"
          : "border-amber-300 bg-amber-50 text-amber-900",
    });
  }

  for (const cat of item.inventory_action_center?.action_categories ?? []) {
    chips.push({
      key: `act-${cat}`,
      label: actionShort(cat),
      className: "border-teal-300 bg-teal-50 text-teal-900",
    });
  }

  for (const c of item.order_arrival_classifications ?? []) {
    chips.push({
      key: `arr-${c}`,
      label: orderArrivalShort(c),
      className: "border-violet-300 bg-violet-50 text-violet-900",
    });
  }

  return chips;
}

function SignalChips({ item }: { item: InventoryItem }): JSX.Element | null {
  const chips = buildSignalChips(item);
  if (!chips.length) return null;

  const visible = chips.slice(0, 4);
  const overflow = chips.length - visible.length;
  const overflowTitle = chips.slice(4).map((c) => c.label).join(" · ");

  return (
    <div className="mt-1.5 flex max-w-full flex-wrap gap-1">
      {visible.map((chip) => (
        <span
          key={chip.key}
          title={chip.title ?? chip.label}
          className={`inline-flex max-w-[9rem] truncate rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${chip.className}`}
        >
          {chip.label}
        </span>
      ))}
      {overflow > 0 ? (
        <span
          title={overflowTitle}
          className="inline-flex rounded-md border border-slate-300 bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
        >
          +{overflow}
        </span>
      ) : null}
    </div>
  );
}

function releaseMetaLine(item: InventoryItem): string {
  const parts: string[] = [];
  if (item.release_year != null) parts.push(String(item.release_year));
  if (item.received_at) parts.push(`Received ${formatDate(item.received_at)}`);
  else if (item.expected_ship_date) parts.push(`Expected ship ${formatDate(item.expected_ship_date)}`);
  else if (item.release_date) parts.push(formatDate(item.release_date));
  return parts.join(" · ");
}

const selectClass =
  "rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 outline-none focus:border-blue-500";

export function PortfolioInventoryList(props: {
  inventory: InventoryItem[];
  selectedIds: number[];
  isSaving: boolean;
  fMvDrafts: Record<number, string>;
  gradeDrafts: Record<number, InventoryItem["grade_status"]>;
  holdDrafts: Record<number, InventoryItem["hold_status"]>;
  starDrafts: Record<number, string>;
  normalizeDecimalInput: (value: string) => string | null;
  onToggleSelection: (id: number) => void;
  onFmvDraftChange: (id: number, value: string) => void;
  onGradeDraftChange: (id: number, value: InventoryItem["grade_status"]) => void;
  onHoldDraftChange: (id: number, value: InventoryItem["hold_status"]) => void;
  onStarDraftChange: (id: number, value: string) => void;
  onSave: (id: number, payload: InventoryUpdatePayload) => Promise<void>;
  onOpenNotes: (item: InventoryItem) => void;
  onOpenDetail?: (item: InventoryItem) => void;
  receivingCopyIds: ReadonlySet<number>;
  onMarkReceived: (id: number) => void;
}): JSX.Element {
  const {
    inventory,
    selectedIds,
    isSaving,
    fMvDrafts,
    gradeDrafts,
    holdDrafts,
    starDrafts,
    normalizeDecimalInput,
    onToggleSelection,
    onFmvDraftChange,
    onGradeDraftChange,
    onHoldDraftChange,
    onStarDraftChange,
    onSave,
    onOpenNotes,
    onOpenDetail,
    receivingCopyIds,
    onMarkReceived,
  } = props;

  return (
    <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
      {inventory.map((item) => {
        const id = item.inventory_copy_id;
        const variant = variantLabel(item) || "Standard cover";
        const meta = releaseMetaLine(item);
        const marketFmv = item.current_market_fmv
          ? formatCurrencyAmount(item.current_market_fmv, item.fmv_currency_code ?? "USD")
          : null;
        const canReceive = canQuickReceiveInventoryCopy(item);
        const isReceiving = receivingCopyIds.has(id);
        const openDetail = () => {
          if (onOpenDetail) {
            onOpenDetail(item);
          }
        };
        const coverClass =
          "relative block h-20 w-14 shrink-0 overflow-hidden rounded-md border border-slate-200 bg-slate-100 text-left";
        const titleClass =
          "line-clamp-2 text-sm font-semibold leading-snug text-patriot-navy hover:text-patriot-blue";

        return (
          <article
            key={id}
            className="flex flex-col rounded-2xl border border-slate-200 bg-white p-3 shadow-sm transition hover:border-blue-200 hover:shadow-md"
          >
            <div className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-1 shrink-0"
                checked={selectedIds.includes(id)}
                onChange={() => onToggleSelection(id)}
                aria-label={`Select ${item.title}`}
              />

              {onOpenDetail ? (
                <button
                  type="button"
                  onClick={openDetail}
                  className={coverClass}
                  aria-label={`${item.title} cover`}
                  data-testid="inventory-card-cover"
                >
                  {item.cover_image_url ? (
                    <img
                      src={item.cover_image_url}
                      alt=""
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={(event) => {
                        event.currentTarget.style.display = "none";
                        const fallback = event.currentTarget.nextElementSibling;
                        if (fallback instanceof HTMLElement) {
                          fallback.style.display = "flex";
                        }
                      }}
                    />
                  ) : null}
                  <span
                    className="absolute inset-0 flex items-center justify-center text-base text-slate-400"
                    style={{ display: item.cover_image_url ? "none" : "flex" }}
                    aria-hidden="true"
                  >
                    📚
                  </span>
                </button>
              ) : (
                <Link
                  to={`/inventory/${id}`}
                  className={coverClass}
                  aria-label={`${item.title} cover`}
                  data-testid="inventory-card-cover"
                >
                  {item.cover_image_url ? (
                    <img
                      src={item.cover_image_url}
                      alt=""
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={(event) => {
                        event.currentTarget.style.display = "none";
                        const fallback = event.currentTarget.nextElementSibling;
                        if (fallback instanceof HTMLElement) {
                          fallback.style.display = "flex";
                        }
                      }}
                    />
                  ) : null}
                  <span
                    className="absolute inset-0 flex items-center justify-center text-base text-slate-400"
                    style={{ display: item.cover_image_url ? "none" : "flex" }}
                    aria-hidden="true"
                  >
                    📚
                  </span>
                </Link>
              )}

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  {onOpenDetail ? (
                    <button type="button" onClick={openDetail} className={titleClass}>
                      {item.title} #{item.issue_number}
                    </button>
                  ) : (
                    <Link to={`/inventory/${id}`} className={titleClass}>
                      {item.title} #{item.issue_number}
                    </Link>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1">
                  <span
                    className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${assetStateTone(
                      item.asset_state,
                    )}`}
                  >
                    {canReceive ? (
                      <button
                        type="button"
                        disabled={isSaving || isReceiving}
                        title="Mark this copy in hand"
                        onClick={() => onMarkReceived(id)}
                        className="uppercase tracking-wide hover:underline disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isReceiving ? "Receiving…" : assetStateShort(item.asset_state)}
                      </button>
                    ) : (
                      assetStateShort(item.asset_state)
                    )}
                  </span>
                  {canReceive ? (
                    <button
                      type="button"
                      disabled={isSaving || isReceiving}
                      onClick={() => onMarkReceived(id)}
                      className="shrink-0 rounded-md border border-emerald-400 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-900 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isReceiving ? "Marking…" : "Mark received"}
                    </button>
                  ) : null}
                </div>
              </div>
            </div>

            <p className="mt-2 line-clamp-3 text-xs leading-snug text-slate-600">
              {item.publisher}
              <span className="text-slate-600"> · </span>
              {variant}
              <span className="text-slate-600"> · </span>
              {item.retailer}
              <span className="text-slate-600"> · </span>
              {formatDate(item.order_date)}
              <span className="text-slate-600"> · </span>
              Paid {formatUsdCurrency(item.acquisition_cost)}
              {meta ? (
                <>
                  <span className="text-slate-600"> · </span>
                  {meta}
                </>
              ) : null}
            </p>
            <SignalChips item={item} />

            <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                <span className="text-slate-500">Market</span>
                <span className="font-medium text-slate-900">{marketFmv ?? "—"}</span>
                <span className={`${gainLossClass(item.gain_loss ?? "0")} font-medium`}>
                  {formatUsdCurrency(item.gain_loss ?? "0")}
                </span>
                {item.valuation_scope === "no_market_data" ? (
                  <span className="rounded-md border border-slate-500/40 px-1 py-0.5 text-[9px] uppercase text-slate-500">
                    No FMV
                  </span>
                ) : item.valuation_scope ? (
                  <span className="rounded-md border border-blue-200 bg-blue-50 px-1 py-0.5 text-[9px] uppercase text-blue-800">
                    {item.valuation_scope.replace(/_/g, " ")}
                  </span>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                <span className="text-slate-500">Your FMV</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={fMvDrafts[id] ?? ""}
                  onChange={(event) => onFmvDraftChange(id, event.target.value)}
                  className="w-[4.25rem] rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 outline-none focus:border-blue-500"
                />
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() =>
                    void onSave(id, {
                      current_fmv: normalizeDecimalInput(fMvDrafts[id] ?? ""),
                    })
                  }
                  className="rounded-lg border border-blue-300 bg-blue-50 px-2 py-1 text-[10px] font-semibold text-patriot-blue hover:bg-blue-100 disabled:opacity-50"
                >
                  Save
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                <select
                  value={gradeDrafts[id] ?? item.grade_status}
                  onChange={(event) =>
                    onGradeDraftChange(id, event.target.value as InventoryItem["grade_status"])
                  }
                  onBlur={() =>
                    void onSave(id, {
                      grade_status: gradeDrafts[id] ?? item.grade_status,
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
                  value={holdDrafts[id] ?? item.hold_status}
                  onChange={(event) =>
                    onHoldDraftChange(id, event.target.value as InventoryItem["hold_status"])
                  }
                  onBlur={() =>
                    void onSave(id, {
                      hold_status: holdDrafts[id] ?? item.hold_status,
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
                  value={
                    starDrafts[id]
                      ? Number(starDrafts[id])
                      : item.star_rating
                  }
                  onChange={(rating) => {
                    onStarDraftChange(id, rating ? String(rating) : "");
                    void onSave(id, { star_rating: rating });
                  }}
                />
                <button
                  type="button"
                  onClick={() => onOpenNotes(item)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-[10px] font-semibold text-slate-700 hover:border-blue-400 hover:text-patriot-blue"
                >
                  Notes
                </button>
                {onOpenDetail ? (
                  <button
                    type="button"
                    onClick={openDetail}
                    className="rounded-lg border border-patriot-blue bg-patriot-blue px-2 py-1 text-[10px] font-semibold text-white hover:bg-blue-900"
                  >
                    Details
                  </button>
                ) : (
                  <Link
                    to={`/inventory/${id}`}
                    className="rounded-lg border border-patriot-blue bg-patriot-blue px-2 py-1 text-[10px] font-semibold text-white hover:bg-blue-900"
                  >
                    Open
                  </Link>
                )}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
