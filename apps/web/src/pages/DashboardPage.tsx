import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type InventoryItem,
  type PortfolioPerformance,
  type PortfolioPerformanceItem,
  type InventoryQueryParams,
  type InventorySummary,
  type InventoryUpdatePayload,
  type SortBy,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../auth/AuthContext";

const sortOptions: Array<{ label: string; value: SortBy }> = [
  { label: "Purchase Date", value: "purchase_date" },
  { label: "Title", value: "title" },
  { label: "Acquisition Cost", value: "acquisition_cost" },
  { label: "Current FMV", value: "current_fmv" },
  { label: "Gain / Loss", value: "gain_loss" },
];

function formatCurrency(value: string | null): string {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function variantLabel(item: InventoryItem): string {
  return [item.cover_name, item.printing, item.ratio, item.variant_type]
    .filter(Boolean)
    .join(" / ");
}

function gainLossClass(value: string | null): string {
  if (value === null) {
    return "text-slate-400";
  }

  const amount = Number(value);
  if (amount > 0) {
    return "text-emerald-300";
  }
  if (amount < 0) {
    return "text-rose-300";
  }
  return "text-slate-300";
}

function normalizeDecimalInput(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function performanceLabel(item: PortfolioPerformanceItem): string {
  return `${item.title} #${item.issue_number}`;
}

export function DashboardPage() {
  const { user } = useAuth();

  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [performance, setPerformance] = useState<PortfolioPerformance | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [publisher, setPublisher] = useState("");
  const [holdStatus, setHoldStatus] = useState("");
  const [gradeStatus, setGradeStatus] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("purchase_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkHoldStatus, setBulkHoldStatus] = useState<"hold" | "sell" | "sold">("sell");
  const [fMvDrafts, setFmvDrafts] = useState<Record<number, string>>({});
  const [holdDrafts, setHoldDrafts] = useState<Record<number, InventoryItem["hold_status"]>>({});
  const [gradeDrafts, setGradeDrafts] = useState<Record<number, InventoryItem["grade_status"]>>({});
  const [starDrafts, setStarDrafts] = useState<Record<number, string>>({});
  const [activeNotesItem, setActiveNotesItem] = useState<InventoryItem | null>(null);
  const [notesDraft, setNotesDraft] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  const inventoryQuery = useMemo<InventoryQueryParams>(
    () => ({
      page,
      page_size: pageSize,
      search: search || undefined,
      publisher: publisher || undefined,
      hold_status: holdStatus || undefined,
      grade_status: gradeStatus || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
    }),
    [gradeStatus, holdStatus, page, pageSize, publisher, search, sortBy, sortDir],
  );

  async function loadDashboardData(query: InventoryQueryParams = inventoryQuery): Promise<void> {
    const [summaryResponse, performanceResponse, inventoryResponse] = await Promise.all([
      apiClient.getInventorySummary(),
      apiClient.getPortfolioPerformance(),
      apiClient.getInventory(query),
    ]);
    setSummary(summaryResponse);
    setPerformance(performanceResponse);
    setInventory(inventoryResponse.items);
    setTotal(inventoryResponse.total);
    setSelectedIds((current) =>
      current.filter((id) => inventoryResponse.items.some((item) => item.inventory_copy_id === id)),
    );
  }

  useEffect(() => {
    let ignore = false;

    async function fetchData() {
      setIsLoading(true);
      setError(null);

      try {
        const [summaryResponse, performanceResponse, inventoryResponse] = await Promise.all([
          apiClient.getInventorySummary(),
          apiClient.getPortfolioPerformance(),
          apiClient.getInventory(inventoryQuery),
        ]);

        if (ignore) {
          return;
        }

        setSummary(summaryResponse);
        setPerformance(performanceResponse);
        setInventory(inventoryResponse.items);
        setTotal(inventoryResponse.total);
        setSelectedIds((current) =>
          current.filter((id) => inventoryResponse.items.some((item) => item.inventory_copy_id === id)),
        );
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load dashboard.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void fetchData();

    return () => {
      ignore = true;
    };
  }, [inventoryQuery]);

  useEffect(() => {
    const nextFmvDrafts: Record<number, string> = {};
    const nextHoldDrafts: Record<number, InventoryItem["hold_status"]> = {};
    const nextGradeDrafts: Record<number, InventoryItem["grade_status"]> = {};
    const nextStarDrafts: Record<number, string> = {};

    inventory.forEach((item) => {
      nextFmvDrafts[item.inventory_copy_id] = item.current_fmv ?? "";
      nextHoldDrafts[item.inventory_copy_id] = item.hold_status;
      nextGradeDrafts[item.inventory_copy_id] = item.grade_status;
      nextStarDrafts[item.inventory_copy_id] = item.star_rating ? String(item.star_rating) : "";
    });

    setFmvDrafts(nextFmvDrafts);
    setHoldDrafts(nextHoldDrafts);
    setGradeDrafts(nextGradeDrafts);
    setStarDrafts(nextStarDrafts);
  }, [inventory]);

  function applySearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  function resetPageAndUpdate(callback: () => void) {
    setPage(1);
    callback();
  }

  async function saveInventoryUpdate(
    inventoryCopyId: number,
    updates: InventoryUpdatePayload,
  ): Promise<void> {
    setError(null);
    setIsSaving(true);

    try {
      await apiClient.updateInventoryCopy(inventoryCopyId, updates);
      await loadDashboardData();
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to save inventory changes.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function applyBulkHoldUpdate(): Promise<void> {
    if (!selectedIds.length) {
      return;
    }

    setError(null);
    setIsSaving(true);

    try {
      await apiClient.bulkUpdateInventory({
        inventory_copy_ids: selectedIds,
        updates: { hold_status: bulkHoldStatus },
      });
      setSelectedIds([]);
      await loadDashboardData();
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to apply bulk update.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  function toggleSelection(inventoryCopyId: number): void {
    setSelectedIds((current) =>
      current.includes(inventoryCopyId)
        ? current.filter((id) => id !== inventoryCopyId)
        : [...current, inventoryCopyId],
    );
  }

  function toggleSelectAll(): void {
    if (selectedIds.length === inventory.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(inventory.map((item) => item.inventory_copy_id));
    }
  }

  const cards = [
    { label: "Copies", value: summary?.total_copies ?? 0 },
    { label: "Cost Basis", value: formatCurrency(summary?.total_cost_basis ?? "0") },
    { label: "Current FMV", value: formatCurrency(summary?.total_current_fmv ?? "0") },
    {
      label: "Unrealized P/L",
      value: formatCurrency(summary?.total_unrealized_gain_loss ?? "0"),
    },
  ];

  const analyticsSections = [
    {
      title: "Top Gainers",
      items: performance?.top_gainers ?? [],
      empty: "No positive gainers yet.",
      valueLabel: "Gain",
      valueFor: (item: PortfolioPerformanceItem) => item.gain_loss,
    },
    {
      title: "Top Losers",
      items: performance?.top_losers ?? [],
      empty: "No unrealized losers yet.",
      valueLabel: "Loss",
      valueFor: (item: PortfolioPerformanceItem) => item.gain_loss,
    },
    {
      title: "Highest Value Books",
      items: performance?.highest_value_books ?? [],
      empty: "No valued books yet.",
      valueLabel: "FMV",
      valueFor: (item: PortfolioPerformanceItem) => item.current_fmv,
    },
  ];

  const hasPerformanceData = analyticsSections.some((section) => section.items.length > 0);
  const isInitialLoad = isLoading && !summary && !performance && inventory.length === 0;

  if (isInitialLoad) {
    return (
      <AppShell>
        <PageHeader
          eyebrow="ComicOS Dashboard"
          title="Inventory Portfolio"
          description="Review cost basis, FMV, performance leaders, and book-level metadata from one premium workspace."
          actions={
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              Signed in as <span className="font-medium text-white">{user?.email ?? "Loading..."}</span>
            </div>
          }
        />
        <div className="mt-6">
          <LoadingState
            title="Loading portfolio workspace"
            description="Refreshing summary cards, performance leaders, and inventory rows."
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="ComicOS Dashboard"
        title="Inventory Portfolio"
        description="Review cost basis, monitor held inventory, and manage book-level portfolio metadata from one dark-mode workspace."
        actions={
          <>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              Signed in as <span className="font-medium text-white">{user?.email ?? "Loading..."}</span>
            </div>
            <Link
              to="/orders/import"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
            >
              Import Order
            </Link>
            <Link
              to="/orders/new"
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
            >
              Add Order
            </Link>
          </>
        }
      />

      <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {cards.map((card) => (
            <article
              key={card.label}
              className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 shadow-lg shadow-black/20"
            >
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
                {card.label}
              </p>
              <p className="mt-2 text-2xl font-semibold text-white sm:text-3xl">{card.value}</p>
            </article>
          ))}
      </section>

      {!hasPerformanceData ? (
        <div className="mt-6">
          <EmptyState
            title="No performance data yet"
            description="Performance leaders appear after you create orders and start assigning FMV values to inventory copies."
            action={
              <div className="flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/orders/import"
                  className="rounded-2xl border border-white/10 px-4 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                >
                  Paste Receipt/Text
                </Link>
                <Link
                  to="/orders/new"
                  className="rounded-2xl bg-cyan-400 px-4 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
                >
                  Add Your First Order
                </Link>
              </div>
            }
          />
        </div>
      ) : (
        <section className="mt-6 grid gap-4 xl:grid-cols-3">
          {analyticsSections.map((section) => (
            <article
              key={section.title}
              className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-lg shadow-black/20"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-white">{section.title}</h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Premium portfolio analytics for your strongest signals.
                  </p>
                </div>
              </div>

              <div className="mt-5 space-y-3">
                {section.items.length ? (
                  section.items.map((item) => (
                    <Link
                      key={`${section.title}-${item.inventory_copy_id}`}
                      to={`/inventory/${item.inventory_copy_id}`}
                      className="block rounded-2xl border border-white/10 bg-slate-950/70 p-4 transition hover:border-cyan-300/40 hover:bg-slate-950"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-white">{performanceLabel(item)}</p>
                          <p className="mt-1 text-sm text-slate-400">{item.publisher}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                            {item.cover_name ?? "Standard cover"}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                            {section.valueLabel}
                          </p>
                          <p
                            className={`mt-1 text-sm font-semibold ${
                              section.title === "Highest Value Books"
                                ? "text-cyan-200"
                                : gainLossClass(section.valueFor(item))
                            }`}
                          >
                            {formatCurrency(section.valueFor(item))}
                          </p>
                        </div>
                      </div>
                    </Link>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/50 p-4 text-sm text-slate-500">
                    {section.empty}
                  </div>
                )}
              </div>
            </article>
          ))}
        </section>
      )}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-4">
            <form className="grid gap-3 lg:grid-cols-[2fr_repeat(4,1fr)]" onSubmit={applySearch}>
              <input
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search by title, publisher, issue, or cover"
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
              />
              <input
                type="text"
                value={publisher}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setPublisher(event.target.value);
                  })
                }
                placeholder="Publisher"
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
              />
              <select
                value={holdStatus}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setHoldStatus(event.target.value);
                  })
                }
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
              >
                <option value="">All hold statuses</option>
                <option value="hold">Hold</option>
                <option value="sell">Sell</option>
                <option value="sold">Sold</option>
              </select>
              <select
                value={gradeStatus}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setGradeStatus(event.target.value);
                  })
                }
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
              >
                <option value="">All grade statuses</option>
                <option value="raw">Raw</option>
                <option value="submitted">Submitted</option>
                <option value="graded">Graded</option>
              </select>
              <button
                type="submit"
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                Search
              </button>
            </form>

            <div className="grid gap-3 md:grid-cols-3">
              <select
                value={sortBy}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setSortBy(event.target.value as SortBy);
                  })
                }
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
              >
                {sortOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    Sort by {option.label}
                  </option>
                ))}
              </select>
              <select
                value={sortDir}
                onChange={(event) =>
                  resetPageAndUpdate(() => {
                    setSortDir(event.target.value as "asc" | "desc");
                  })
                }
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setSearchInput("");
                  setPublisher("");
                  setHoldStatus("");
                  setGradeStatus("");
                  setSortBy("purchase_date");
                  setSortDir("asc");
                  setPage(1);
                }}
                className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Reset filters
              </button>
            </div>

            <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-slate-950/50 p-4 md:flex-row md:items-center md:justify-between">
              <p className="text-sm text-slate-400">
                {selectedIds.length} selected for bulk updates
              </p>
              <div className="flex flex-col gap-3 sm:flex-row">
                <select
                  value={bulkHoldStatus}
                  onChange={(event) =>
                    setBulkHoldStatus(event.target.value as "hold" | "sell" | "sold")
                  }
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                >
                  <option value="hold">Mark Hold</option>
                  <option value="sell">Mark Sell</option>
                  <option value="sold">Mark Sold</option>
                </select>
                <button
                  type="button"
                  disabled={!selectedIds.length || isSaving}
                  onClick={() => void applyBulkHoldUpdate()}
                  className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Apply bulk update
                </button>
              </div>
            </div>
          </div>
      </section>

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 shadow-xl shadow-black/20">
          <div className="border-b border-white/10 px-5 py-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-white">Inventory</h2>
                <p className="text-sm text-slate-400">
                  Page {page} of {pageCount} with {total} tracked copies
                </p>
              </div>
              {isLoading ? <p className="text-sm text-slate-400">Refreshing inventory...</p> : null}
            </div>
          </div>

          {!inventory.length ? (
            <div className="p-5">
              <EmptyState
                title="No inventory yet"
                description="Create your first order to populate the dashboard with inventory copies, valuation controls, and detail pages."
                action={
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Link
                      to="/orders/import"
                      className="rounded-2xl border border-white/10 px-4 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                    >
                      Import Order
                    </Link>
                    <Link
                      to="/orders/new"
                      className="rounded-2xl bg-cyan-400 px-4 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
                    >
                      Add Order
                    </Link>
                  </div>
                }
              />
            </div>
          ) : (
            <>
          <div className="hidden overflow-x-auto xl:block">
            <table className="min-w-full text-left text-sm text-slate-300">
              <thead className="border-b border-white/10 text-xs uppercase tracking-[0.16em] text-slate-500">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={Boolean(inventory.length) && selectedIds.length === inventory.length}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Issue</th>
                  <th className="px-4 py-3">Publisher</th>
                  <th className="px-4 py-3">Cover / Variant</th>
                  <th className="px-4 py-3">Retailer</th>
                  <th className="px-4 py-3">Order Date</th>
                  <th className="px-4 py-3">Acquisition</th>
                  <th className="px-4 py-3">Current FMV</th>
                  <th className="px-4 py-3">Gain / Loss</th>
                  <th className="px-4 py-3">Grade</th>
                  <th className="px-4 py-3">Hold</th>
                  <th className="px-4 py-3">Stars</th>
                  <th className="px-4 py-3">Notes</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item) => (
                  <tr key={item.inventory_copy_id} className="border-b border-white/5 align-top">
                    <td className="px-4 py-3.5">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.inventory_copy_id)}
                        onChange={() => toggleSelection(item.inventory_copy_id)}
                      />
                    </td>
                    <td className="px-4 py-3.5 font-medium text-white">{item.title}</td>
                    <td className="px-4 py-3.5">#{item.issue_number}</td>
                    <td className="px-4 py-3.5">{item.publisher}</td>
                    <td className="px-4 py-3.5 text-slate-300">
                      {variantLabel(item) || "Standard cover"}
                    </td>
                    <td className="px-4 py-3.5">{item.retailer}</td>
                    <td className="px-4 py-3.5">{formatDate(item.order_date)}</td>
                    <td className="px-4 py-3.5">{formatCurrency(item.acquisition_cost)}</td>
                    <td className="px-4 py-3.5">
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={fMvDrafts[item.inventory_copy_id] ?? ""}
                          onChange={(event) =>
                            setFmvDrafts((current) => ({
                              ...current,
                              [item.inventory_copy_id]: event.target.value,
                            }))
                          }
                          className="w-24 rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                        />
                        <button
                          type="button"
                          disabled={isSaving}
                          onClick={() =>
                            void saveInventoryUpdate(item.inventory_copy_id, {
                              current_fmv: normalizeDecimalInput(
                                fMvDrafts[item.inventory_copy_id] ?? "",
                              ),
                            })
                          }
                          className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                        >
                          Save
                        </button>
                      </div>
                    </td>
                    <td className={`px-4 py-3.5 ${gainLossClass(item.gain_loss)}`}>
                      {formatCurrency(item.gain_loss)}
                    </td>
                    <td className="px-4 py-3.5">
                      <select
                        value={gradeDrafts[item.inventory_copy_id] ?? item.grade_status}
                        onChange={(event) =>
                          setGradeDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]:
                              event.target.value as InventoryItem["grade_status"],
                          }))
                        }
                        onBlur={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            grade_status: gradeDrafts[item.inventory_copy_id] ?? item.grade_status,
                          })
                        }
                        className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      >
                        <option value="raw">Raw</option>
                        <option value="submitted">Submitted</option>
                        <option value="graded">Graded</option>
                      </select>
                    </td>
                    <td className="px-4 py-3.5">
                      <select
                        value={holdDrafts[item.inventory_copy_id] ?? item.hold_status}
                        onChange={(event) =>
                          setHoldDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]:
                              event.target.value as InventoryItem["hold_status"],
                          }))
                        }
                        onBlur={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            hold_status: holdDrafts[item.inventory_copy_id] ?? item.hold_status,
                          })
                        }
                        className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      >
                        <option value="hold">Hold</option>
                        <option value="sell">Sell</option>
                        <option value="sold">Sold</option>
                      </select>
                    </td>
                    <td className="px-4 py-3.5">
                      <select
                        value={starDrafts[item.inventory_copy_id] ?? ""}
                        onChange={(event) =>
                          setStarDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]: event.target.value,
                          }))
                        }
                        onBlur={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            star_rating: starDrafts[item.inventory_copy_id]
                              ? Number(starDrafts[item.inventory_copy_id])
                              : null,
                          })
                        }
                        className="rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      >
                        <option value="">-</option>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                        <option value="5">5</option>
                      </select>
                    </td>
                    <td className="px-4 py-3.5">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveNotesItem(item);
                          setNotesDraft(item.condition_notes ?? "");
                        }}
                        className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                      >
                        Notes
                      </button>
                    </td>
                    <td className="px-4 py-3.5">
                      <Link
                        to={`/inventory/${item.inventory_copy_id}`}
                        className="inline-flex rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:border-cyan-300/50 hover:bg-cyan-400/20"
                      >
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="space-y-4 p-5 xl:hidden">
            {inventory.map((item) => (
              <article
                key={item.inventory_copy_id}
                className="rounded-3xl border border-white/10 bg-slate-950/70 p-4 shadow-lg shadow-black/10"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                      Inventory Copy #{item.inventory_copy_id}
                    </p>
                    <h3 className="mt-1 text-lg font-semibold text-white">
                      {item.title} #{item.issue_number}
                    </h3>
                    <p className="mt-1 text-sm text-slate-400">
                      {item.publisher} | {variantLabel(item) || "Standard cover"}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.inventory_copy_id)}
                      onChange={() => toggleSelection(item.inventory_copy_id)}
                    />
                    <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                      {item.hold_status}
                    </span>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                  <div>
                    <p className="text-slate-500">Retailer</p>
                    <p>{item.retailer}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Order Date</p>
                    <p>{formatDate(item.order_date)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Acquisition</p>
                    <p>{formatCurrency(item.acquisition_cost)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Gain / Loss</p>
                    <p className={gainLossClass(item.gain_loss)}>{formatCurrency(item.gain_loss)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Current FMV</p>
                    <div className="mt-1 flex gap-2">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={fMvDrafts[item.inventory_copy_id] ?? ""}
                        onChange={(event) =>
                          setFmvDrafts((current) => ({
                            ...current,
                            [item.inventory_copy_id]: event.target.value,
                          }))
                        }
                        className="w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none transition focus:border-cyan-300/40"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          void saveInventoryUpdate(item.inventory_copy_id, {
                            current_fmv: normalizeDecimalInput(
                              fMvDrafts[item.inventory_copy_id] ?? "",
                            ),
                          })
                        }
                        className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                  <div>
                    <p className="text-slate-500">Grade Status</p>
                    <select
                      value={gradeDrafts[item.inventory_copy_id] ?? item.grade_status}
                      onChange={(event) =>
                        setGradeDrafts((current) => ({
                          ...current,
                          [item.inventory_copy_id]:
                            event.target.value as InventoryItem["grade_status"],
                        }))
                      }
                      onBlur={() =>
                        void saveInventoryUpdate(item.inventory_copy_id, {
                          grade_status: gradeDrafts[item.inventory_copy_id] ?? item.grade_status,
                        })
                      }
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none"
                    >
                      <option value="raw">Raw</option>
                      <option value="submitted">Submitted</option>
                      <option value="graded">Graded</option>
                    </select>
                  </div>
                  <div>
                    <p className="text-slate-500">Hold Status</p>
                    <select
                      value={holdDrafts[item.inventory_copy_id] ?? item.hold_status}
                      onChange={(event) =>
                        setHoldDrafts((current) => ({
                          ...current,
                          [item.inventory_copy_id]:
                            event.target.value as InventoryItem["hold_status"],
                        }))
                      }
                      onBlur={() =>
                        void saveInventoryUpdate(item.inventory_copy_id, {
                          hold_status: holdDrafts[item.inventory_copy_id] ?? item.hold_status,
                        })
                      }
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none"
                    >
                      <option value="hold">Hold</option>
                      <option value="sell">Sell</option>
                      <option value="sold">Sold</option>
                    </select>
                  </div>
                  <div>
                    <p className="text-slate-500">Star Rating</p>
                    <select
                      value={starDrafts[item.inventory_copy_id] ?? ""}
                      onChange={(event) =>
                        setStarDrafts((current) => ({
                          ...current,
                          [item.inventory_copy_id]: event.target.value,
                        }))
                      }
                      onBlur={() =>
                        void saveInventoryUpdate(item.inventory_copy_id, {
                          star_rating: starDrafts[item.inventory_copy_id]
                            ? Number(starDrafts[item.inventory_copy_id])
                            : null,
                        })
                      }
                      className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900/80 px-3 py-2 text-sm text-white outline-none"
                    >
                      <option value="">-</option>
                      <option value="1">1</option>
                      <option value="2">2</option>
                      <option value="3">3</option>
                      <option value="4">4</option>
                      <option value="5">5</option>
                    </select>
                  </div>
                  <div className="sm:col-span-2">
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveNotesItem(item);
                          setNotesDraft(item.condition_notes ?? "");
                        }}
                        className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100"
                      >
                        Edit notes
                      </button>
                      <Link
                        to={`/inventory/${item.inventory_copy_id}`}
                        className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:border-cyan-300/50 hover:bg-cyan-400/20"
                      >
                        View Details
                      </Link>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
            </>
          )}

          <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
            <button
              type="button"
              disabled={page === 1}
              onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-slate-400">
              Showing page {page} of {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((currentPage) => Math.min(pageCount, currentPage + 1))}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
      </section>

      {activeNotesItem ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4">
          <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-slate-900 p-6 shadow-2xl shadow-black/30">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-white">Condition Notes</h3>
                <p className="mt-2 text-sm text-slate-400">
                  {activeNotesItem.title} #{activeNotesItem.issue_number}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActiveNotesItem(null)}
                className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100"
              >
                Close
              </button>
            </div>

            <textarea
              value={notesDraft}
              onChange={(event) => setNotesDraft(event.target.value)}
              maxLength={2000}
              rows={8}
              className="mt-6 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
              placeholder="Add condition notes, grading observations, or sale prep notes."
            />

            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-slate-500">{notesDraft.length}/2000 characters</p>
              <button
                type="button"
                disabled={isSaving}
                onClick={async () => {
                  await saveInventoryUpdate(activeNotesItem.inventory_copy_id, {
                    condition_notes: notesDraft.trim() ? notesDraft : null,
                  });
                  setActiveNotesItem(null);
                }}
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Save notes
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
