import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type DraftImport,
  type DraftImportConfirmResponse,
  type DraftImportStatus,
  type ImportQueryParams,
  type ImportSortBy,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDate(value: string | null): string {
  if (!value) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusBadgeClass(status: DraftImport["status"]): string {
  if (status === "confirmed") {
    return "border-emerald-400/20 bg-emerald-400/10 text-emerald-200";
  }
  if (status === "discarded") {
    return "border-rose-400/20 bg-rose-400/10 text-rose-200";
  }
  return "border-cyan-400/20 bg-cyan-400/10 text-cyan-100";
}

function importMetrics(draftImport: DraftImport) {
  return {
    itemCount: draftImport.parsed_payload_json.items.length,
    warningCount: draftImport.parsed_payload_json.warnings.length,
    metadataReviewItemCount: draftImport.metadata_review_item_count,
    releaseDateReviewItemCount: draftImport.release_date_review_item_count,
    retailer: draftImport.parsed_payload_json.retailer ?? "Unknown retailer",
    orderDate: draftImport.parsed_payload_json.order_date,
  };
}

const statusOptions: Array<{ label: string; value: DraftImportStatus | "" }> = [
  { label: "All", value: "" },
  { label: "Draft", value: "draft" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Discarded", value: "discarded" },
];

const sortOptions: Array<{ label: string; value: ImportSortBy }> = [
  { label: "Updated At", value: "updated_at" },
  { label: "Created At", value: "created_at" },
  { label: "Confidence", value: "confidence_score" },
  { label: "Status", value: "status" },
];

export function ImportsPage() {
  const [imports, setImports] = useState<DraftImport[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [statusFilter, setStatusFilter] = useState<DraftImportStatus | "">("");
  const [needsMetadataReviewFilter, setNeedsMetadataReviewFilter] = useState(false);
  const [needsReleaseDateReviewFilter, setNeedsReleaseDateReviewFilter] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<ImportSortBy>("updated_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeImportId, setActiveImportId] = useState<number | null>(null);
  const [lastConfirmed, setLastConfirmed] = useState<DraftImportConfirmResponse | null>(null);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const importQuery = useMemo<ImportQueryParams>(
    () => ({
      page,
      page_size: pageSize,
      status: statusFilter || undefined,
      search: search || undefined,
      needs_metadata_review: needsMetadataReviewFilter || undefined,
      needs_release_date_review: needsReleaseDateReviewFilter || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
    }),
    [
      page,
      pageSize,
      search,
      sortBy,
      sortDir,
      statusFilter,
      needsMetadataReviewFilter,
      needsReleaseDateReviewFilter,
    ],
  );

  async function loadImports(query: ImportQueryParams = importQuery): Promise<void> {
    setError(null);
    const response = await apiClient.getImports(query);
    setImports(response.items);
    setTotal(response.total);
  }

  useEffect(() => {
    let ignore = false;

    async function fetchImports() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.getImports(importQuery);
        if (!ignore) {
          setImports(response.items);
          setTotal(response.total);
        }
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load imports.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void fetchImports();

    return () => {
      ignore = true;
    };
  }, [importQuery]);

  useEffect(() => {
    if (page > pageCount) {
      setPage(pageCount);
    }
  }, [page, pageCount]);

  const isInitialLoad = isLoading && imports.length === 0 && total === 0;

  function applySearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  function updateFilter(callback: () => void): void {
    setPage(1);
    callback();
  }

  async function handleConfirm(importId: number): Promise<void> {
    setActiveImportId(importId);
    setError(null);
    try {
      const response = await apiClient.confirmImport(importId);
      setLastConfirmed(response);
      await loadImports();
    } catch (actionError) {
      if (actionError instanceof ApiError) {
        setError(actionError.message);
      } else {
        setError("Unable to confirm import draft.");
      }
    } finally {
      setActiveImportId(null);
    }
  }

  async function handleDiscard(importId: number): Promise<void> {
    setActiveImportId(importId);
    setError(null);
    try {
      await apiClient.discardImport(importId);
      await loadImports();
    } catch (actionError) {
      if (actionError instanceof ApiError) {
        setError(actionError.message);
      } else {
        setError("Unable to discard import draft.");
      }
    } finally {
      setActiveImportId(null);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="AI Import History"
        title="Saved Import Drafts"
        description="Reopen, review, confirm, or discard saved AI import drafts. Inventory is created only when an import is confirmed."
        actions={
          <Link
            to="/orders/import"
            className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
          >
            Import Order
          </Link>
        }
      />

      {isInitialLoad ? (
        <div className="mt-6">
          <LoadingState
            title="Loading saved imports"
            description="Refreshing saved AI drafts, statuses, and review actions."
          />
        </div>
      ) : null}

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {lastConfirmed ? (
        <div className="mt-6">
          <StatusBanner tone="success">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <span>
                Import #{lastConfirmed.import_id} confirmed and converted into order #
                {lastConfirmed.order_id}.
              </span>
              <Link
                to={`/orders/${lastConfirmed.order_id}`}
                className="rounded-2xl border border-emerald-300/30 px-4 py-2 text-center text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/10"
              >
                View Order
              </Link>
            </div>
          </StatusBanner>
        </div>
      ) : null}

      {!isInitialLoad && imports.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title={search || statusFilter ? "No imports match the current filters" : "No saved imports yet"}
            description={
              search || statusFilter || needsMetadataReviewFilter
                ? "Try a different search term or filter, or start a new import."
                : "Pasted AI drafts appear here after you start a new import. Save one to reopen it later or confirm it into inventory."
            }
            action={
              <Link
                to="/orders/import"
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                Start New Import
              </Link>
            }
          />
        </div>
      ) : null}

      {!isInitialLoad && imports.length > 0 ? (
        <>
          <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-3">
                {statusOptions.map((option) => {
                  const isActive = statusFilter === option.value;
                  return (
                    <button
                      key={option.label}
                      type="button"
                      onClick={() =>
                        updateFilter(() => {
                          setStatusFilter(option.value);
                        })
                      }
                      className={`rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                        isActive
                          ? "bg-cyan-400 text-slate-950"
                          : "border border-white/10 text-slate-100 hover:border-cyan-300/40 hover:bg-white/5"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>

              <form className="grid gap-3 lg:grid-cols-[2fr_1fr_1fr]" onSubmit={applySearch}>
                <input
                  type="search"
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="Search raw text, retailer, titles, or warnings"
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
                />
                <select
                  value={sortBy}
                  onChange={(event) =>
                    updateFilter(() => {
                      setSortBy(event.target.value as ImportSortBy);
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
                <button
                  type="submit"
                  className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
                >
                  Search
                </button>
              </form>

              <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                    <input
                      type="checkbox"
                      checked={needsMetadataReviewFilter}
                      onChange={(event) =>
                        updateFilter(() => {
                          setNeedsMetadataReviewFilter(event.target.checked);
                        })
                      }
                      className="h-4 w-4 rounded border-white/20 bg-slate-950 text-cyan-400 focus:ring-cyan-300/40"
                    />
                    Metadata review flags only
                  </label>
                  <label className="flex items-center gap-3 rounded-2xl border border-rose-400/15 bg-rose-950/20 px-4 py-3 text-sm text-slate-200">
                    <input
                      type="checkbox"
                      checked={needsReleaseDateReviewFilter}
                      onChange={(event) =>
                        updateFilter(() => {
                          setNeedsReleaseDateReviewFilter(event.target.checked);
                        })
                      }
                      className="h-4 w-4 rounded border-white/20 bg-slate-950 text-rose-800 focus:ring-rose-300/40"
                    />
                    Release date warnings only
                  </label>
                </div>
                <select
                  value={sortDir}
                  onChange={(event) =>
                    updateFilter(() => {
                      setSortDir(event.target.value as "asc" | "desc");
                    })
                  }
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 lg:col-span-1"
                >
                  <option value="desc">Descending</option>
                  <option value="asc">Ascending</option>
                </select>
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-400">
                  Showing {imports.length} of {total} imports
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setPage(1);
                    setStatusFilter("");
                    setNeedsMetadataReviewFilter(false);
                    setNeedsReleaseDateReviewFilter(false);
                    setSearch("");
                    setSearchInput("");
                    setSortBy("updated_at");
                    setSortDir("desc");
                  }}
                  className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                >
                  Reset filters
                </button>
              </div>
            </div>
          </section>

          <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 shadow-xl shadow-black/20">
            <div className="border-b border-white/10 px-5 py-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">Imports</h2>
                  <p className="text-sm text-slate-600">
                    Page {page} of {pageCount} with {total} saved AI import drafts
                  </p>
                </div>
                {isLoading ? <p className="text-sm text-slate-600">Refreshing imports...</p> : null}
              </div>
            </div>

            <div className="hidden overflow-x-auto xl:block">
              <table className="min-w-full text-left text-sm text-slate-300">
                <thead className="border-b border-white/10 text-xs uppercase tracking-[0.16em] text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Import</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Retailer</th>
                    <th className="px-4 py-3">Order Date</th>
                    <th className="px-4 py-3">Confidence</th>
                    <th className="px-4 py-3">Items</th>
                    <th className="px-4 py-3">Warnings</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-4 py-3">Updated</th>
                    <th className="px-4 py-3">Order</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {imports.map((draftImport) => {
                    const metrics = importMetrics(draftImport);
                    const isWorking = activeImportId === draftImport.id;

                    return (
                      <tr key={draftImport.id} className="border-b border-white/5 align-top">
                        <td className="px-4 py-3.5 font-medium text-white">
                          <div className="flex flex-col gap-2">
                            <span>#{draftImport.id}</span>
                            {draftImport.cover_image_count > 0 ? (
                              <span
                                className="inline-flex items-center gap-1 self-start rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-100"
                                title={`${draftImport.cover_image_count} cover scan${draftImport.cover_image_count === 1 ? "" : "s"}`}
                              >
                                <span aria-hidden>📷</span>
                                <span>{draftImport.cover_image_count}</span>
                                <span className="sr-only">cover uploads</span>
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <span
                            className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(draftImport.status)}`}
                          >
                            {draftImport.status}
                          </span>
                        </td>
                        <td className="px-4 py-3.5">{metrics.retailer}</td>
                        <td className="px-4 py-3.5">{formatDate(metrics.orderDate)}</td>
                        <td className="px-4 py-3.5">
                          {Math.round(Number(draftImport.confidence_score) * 100)}%
                        </td>
                        <td className="px-4 py-3.5">{metrics.itemCount}</td>
                        <td className="px-4 py-3.5">
                          <div className="space-y-2">
                            <p>{metrics.warningCount}</p>
                            {draftImport.needs_metadata_review ? (
                              <span className="inline-flex rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-amber-800">
                                {metrics.metadataReviewItemCount} metadata
                                {metrics.metadataReviewItemCount === 1 ? " item" : " items"}
                              </span>
                            ) : null}
                            {draftImport.needs_release_date_review ? (
                              <span className="inline-flex rounded-full border border-rose-400/25 bg-rose-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-rose-100">
                                {metrics.releaseDateReviewItemCount} release date
                                {metrics.releaseDateReviewItemCount === 1 ? "" : "s"}
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-4 py-3.5">{formatTimestamp(draftImport.created_at)}</td>
                        <td className="px-4 py-3.5">{formatTimestamp(draftImport.updated_at)}</td>
                        <td className="px-4 py-3.5">
                          {draftImport.order_id ? (
                            <Link
                              to={`/orders/${draftImport.order_id}`}
                              className="inline-flex rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/15"
                            >
                              View Order
                            </Link>
                          ) : (
                            <span className="text-slate-500">Not created</span>
                          )}
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex flex-wrap gap-2">
                            <Link
                              to={`/orders/import?importId=${draftImport.id}`}
                              className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                            >
                              Open Draft
                            </Link>
                            {draftImport.status === "draft" ? (
                              <>
                                <button
                                  type="button"
                                  disabled={isWorking}
                                  onClick={() => void handleConfirm(draftImport.id)}
                                  className="rounded-xl bg-cyan-400 px-3 py-2 text-xs font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {isWorking ? "Working..." : "Confirm"}
                                </button>
                                <button
                                  type="button"
                                  disabled={isWorking}
                                  onClick={() => void handleDiscard(draftImport.id)}
                                  className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  Discard
                                </button>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="space-y-4 p-5 xl:hidden">
              {imports.map((draftImport) => {
                const metrics = importMetrics(draftImport);
                const isWorking = activeImportId === draftImport.id;

                return (
                  <article
                    key={draftImport.id}
                    className="rounded-3xl border border-white/10 bg-slate-950/70 p-4 shadow-lg shadow-black/10"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                          Import #{draftImport.id}
                        </p>
                        <h3 className="mt-1 text-lg font-semibold text-white">{metrics.retailer}</h3>
                        <p className="mt-1 text-sm text-slate-400">
                          Order date {formatDate(metrics.orderDate)}
                        </p>
                        {draftImport.cover_image_count > 0 ? (
                          <p
                            className="mt-2 inline-flex items-center gap-1 rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-violet-100"
                            title={`${draftImport.cover_image_count} cover scan${draftImport.cover_image_count === 1 ? "" : "s"}`}
                          >
                            <span aria-hidden>📷</span>
                            {draftImport.cover_image_count} scans
                          </p>
                        ) : null}
                      </div>
                      <span
                        className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(draftImport.status)}`}
                      >
                        {draftImport.status}
                      </span>
                    </div>

                    <div className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                      <div>
                        <p className="text-slate-500">Confidence</p>
                        <p>{Math.round(Number(draftImport.confidence_score) * 100)}%</p>
                      </div>
                      <div>
                        <p className="text-slate-500">Items / Warnings</p>
                        <p>
                          {metrics.itemCount} items / {metrics.warningCount} warnings
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Metadata review</p>
                        <p>
                          {draftImport.needs_metadata_review
                            ? `${metrics.metadataReviewItemCount} item${
                                metrics.metadataReviewItemCount === 1 ? "" : "s"
                              } flagged`
                            : "No metadata flags"}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Release date notes</p>
                        <p>
                          {draftImport.needs_release_date_review
                            ? `${metrics.releaseDateReviewItemCount} item${
                                metrics.releaseDateReviewItemCount === 1 ? "" : "s"
                              } with warnings`
                            : "No release date warnings"}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Created</p>
                        <p>{formatTimestamp(draftImport.created_at)}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">Updated</p>
                        <p>{formatTimestamp(draftImport.updated_at)}</p>
                      </div>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-3">
                      <Link
                        to={`/orders/import?importId=${draftImport.id}`}
                        className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                      >
                        Open Draft
                      </Link>
                      {draftImport.order_id ? (
                        <Link
                          to={`/orders/${draftImport.order_id}`}
                          className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/15"
                        >
                          View Order
                        </Link>
                      ) : null}
                      {draftImport.status === "draft" ? (
                        <>
                          <button
                            type="button"
                            disabled={isWorking}
                            onClick={() => void handleConfirm(draftImport.id)}
                            className="rounded-xl bg-cyan-400 px-3 py-2 text-xs font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isWorking ? "Working..." : "Confirm"}
                          </button>
                          <button
                            type="button"
                            disabled={isWorking}
                            onClick={() => void handleDiscard(draftImport.id)}
                            className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            Discard
                          </button>
                        </>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
              <button
                type="button"
                disabled={page === 1}
                onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
                className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-slate-600">
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
        </>
      ) : null}
    </AppShell>
  );
}
