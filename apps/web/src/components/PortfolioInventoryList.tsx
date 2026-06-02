import { Link } from "react-router-dom";

import {
  type InventoryActionCenterCategory,
  type InventoryItem,
  type InventoryRiskType,
  type InventoryUpdatePayload,
  type OrderArrivalClassification,
} from "../api/client";
import { formatCurrencyAmount, formatUsdCurrency } from "../lib/currencyFormat";

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
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
    case "ordered_not_received":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "preorder_not_released_yet":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    case "cancelled":
      return "border-rose-400/30 bg-rose-400/10 text-rose-200";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

function gainLossClass(value: string): string {
  const n = Number.parseFloat(value);
  if (Number.isNaN(n) || n === 0) return "text-slate-400";
  return n > 0 ? "text-emerald-300" : "text-rose-300";
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
        className: "border-cyan-400/30 bg-cyan-400/10 text-cyan-100",
      });
    }
    if (!intel.has_cover_scan) {
      chips.push({
        key: "unscanned",
        label: "Unscanned",
        className: "border-white/15 bg-white/5 text-slate-300",
      });
    }
    if (intel.preorder_missing_release_calendar) {
      chips.push({
        key: "preorder-cal",
        label: "Preorder date gap",
        className: "border-amber-400/30 bg-amber-400/10 text-amber-100",
      });
    }
  }

  if (item.duplicate_ownership) {
    chips.push({
      key: "dup",
      label: "Multi-copy",
      className: "border-white/15 bg-white/5 text-slate-200",
      title: item.duplicate_ownership.classification,
    });
  }

  if (item.run_detection) {
    chips.push({
      key: "run",
      label: item.run_detection.series_status.replace(/_/g, " "),
      className: "border-white/15 bg-white/5 text-slate-200",
    });
  }

  for (const risk of item.inventory_risks ?? []) {
    chips.push({
      key: `risk-${risk.risk_key}`,
      label: inventoryRiskLabel(risk.risk_type),
      className:
        risk.priority === "critical" || risk.priority === "high"
          ? "border-rose-400/35 bg-rose-400/10 text-rose-100"
          : "border-amber-400/30 bg-amber-400/10 text-amber-100",
    });
  }

  for (const cat of item.inventory_action_center?.action_categories ?? []) {
    chips.push({
      key: `act-${cat}`,
      label: actionShort(cat),
      className: "border-teal-400/30 bg-teal-400/10 text-teal-100",
    });
  }

  for (const c of item.order_arrival_classifications ?? []) {
    chips.push({
      key: `arr-${c}`,
      label: orderArrivalShort(c),
      className: "border-violet-400/30 bg-violet-400/10 text-violet-100",
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
          className="inline-flex rounded-md border border-white/15 bg-white/5 px-1.5 py-0.5 text-[10px] font-medium text-slate-400"
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
  "rounded-lg border border-white/10 bg-slate-950/80 px-2 py-1 text-xs text-white outline-none focus:border-cyan-300/40";

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
  } = props;

  return (
    <div className="divide-y divide-white/5">
      {inventory.map((item) => {
        const id = item.inventory_copy_id;
        const variant = variantLabel(item) || "Standard cover";
        const meta = releaseMetaLine(item);
        const marketFmv = item.current_market_fmv
          ? formatCurrencyAmount(item.current_market_fmv, item.fmv_currency_code ?? "USD")
          : null;

        return (
          <article key={id} className="px-4 py-3 transition hover:bg-white/[0.02]">
            <div className="flex gap-3">
              <input
                type="checkbox"
                className="mt-1 shrink-0"
                checked={selectedIds.includes(id)}
                onChange={() => onToggleSelection(id)}
                aria-label={`Select ${item.title}`}
              />

              <div className="min-w-0 flex-1 space-y-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <Link
                      to={`/inventory/${id}`}
                      className="truncate text-sm font-semibold text-white hover:text-cyan-200"
                    >
                      {item.title} #{item.issue_number}
                    </Link>
                    <span
                      className={`shrink-0 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${assetStateTone(
                        item.asset_state,
                      )}`}
                    >
                      {assetStateShort(item.asset_state)}
                    </span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-xs leading-snug text-slate-400">
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
                </div>

                <div className="flex flex-wrap items-end justify-between gap-3 gap-y-2 border-t border-white/5 pt-2">
                  <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                    <span className="text-slate-500">Market</span>
                    <span className="font-medium text-slate-100">{marketFmv ?? "—"}</span>
                    <span className={`${gainLossClass(item.gain_loss ?? "0")} font-medium`}>
                      {formatUsdCurrency(item.gain_loss ?? "0")}
                    </span>
                    {item.valuation_scope === "no_market_data" ? (
                      <span className="rounded-md border border-slate-500/40 px-1 py-0.5 text-[9px] uppercase text-slate-500">
                        No FMV
                      </span>
                    ) : item.valuation_scope ? (
                      <span className="rounded-md border border-cyan-400/25 px-1 py-0.5 text-[9px] uppercase text-cyan-200/80">
                        {item.valuation_scope.replace(/_/g, " ")}
                      </span>
                    ) : null}
                    <span className="text-slate-600">|</span>
                    <span className="text-slate-500">Your FMV</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={fMvDrafts[id] ?? ""}
                      onChange={(event) => onFmvDraftChange(id, event.target.value)}
                      className="w-[4.25rem] rounded-lg border border-white/10 bg-slate-950/80 px-2 py-1 text-xs text-white outline-none focus:border-cyan-300/40"
                    />
                    <button
                      type="button"
                      disabled={isSaving}
                      onClick={() =>
                        void onSave(id, {
                          current_fmv: normalizeDecimalInput(fMvDrafts[id] ?? ""),
                        })
                      }
                      className="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-semibold text-slate-200 hover:border-cyan-300/40 disabled:opacity-50"
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
                    <select
                      value={starDrafts[id] ?? ""}
                      onChange={(event) => onStarDraftChange(id, event.target.value)}
                      onBlur={() =>
                        void onSave(id, {
                          star_rating: starDrafts[id] ? Number(starDrafts[id]) : null,
                        })
                      }
                      className={`${selectClass} max-w-[3rem]`}
                      aria-label="Star rating"
                    >
                      <option value="">★</option>
                      <option value="1">1</option>
                      <option value="2">2</option>
                      <option value="3">3</option>
                      <option value="4">4</option>
                      <option value="5">5</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => onOpenNotes(item)}
                      className="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-semibold text-slate-200 hover:border-cyan-300/40"
                    >
                      Notes
                    </button>
                    <Link
                      to={`/inventory/${id}`}
                      className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-[10px] font-semibold text-cyan-100 hover:border-cyan-300/50"
                    >
                      Open
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
