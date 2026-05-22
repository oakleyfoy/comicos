import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type InventoryDetail,
  type InventoryFmvSnapshot,
  type InventoryUpdatePayload,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

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

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
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

function variantLabel(item: InventoryDetail): string {
  return [item.cover_name, item.printing, item.ratio, item.variant_type]
    .filter(Boolean)
    .join(" / ");
}

export function InventoryDetailPage() {
  const { inventoryCopyId } = useParams<{ inventoryCopyId: string }>();
  const parsedInventoryCopyId = Number(inventoryCopyId);

  const [detail, setDetail] = useState<InventoryDetail | null>(null);
  const [history, setHistory] = useState<InventoryFmvSnapshot[]>([]);
  const [fMvDraft, setFmvDraft] = useState("");
  const [holdDraft, setHoldDraft] = useState<InventoryDetail["hold_status"]>("hold");
  const [gradeDraft, setGradeDraft] = useState<InventoryDetail["grade_status"]>("raw");
  const [starDraft, setStarDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function loadDetail(): Promise<void> {
    if (!Number.isInteger(parsedInventoryCopyId) || parsedInventoryCopyId <= 0) {
      setError("Invalid inventory copy id.");
      setIsLoading(false);
      return;
    }

    const [detailResponse, historyResponse] = await Promise.all([
      apiClient.getInventoryCopy(parsedInventoryCopyId),
      apiClient.getInventoryFmvHistory(parsedInventoryCopyId),
    ]);
    setDetail(detailResponse);
    setHistory(historyResponse);
    setFmvDraft(detailResponse.current_fmv ?? "");
    setHoldDraft(detailResponse.hold_status);
    setGradeDraft(detailResponse.grade_status);
    setStarDraft(detailResponse.star_rating ? String(detailResponse.star_rating) : "");
    setNotesDraft(detailResponse.condition_notes ?? "");
  }

  useEffect(() => {
    let ignore = false;

    async function fetchDetail() {
      setIsLoading(true);
      setError(null);

      if (!Number.isInteger(parsedInventoryCopyId) || parsedInventoryCopyId <= 0) {
        setError("Invalid inventory copy id.");
        setIsLoading(false);
        return;
      }

      try {
        const [detailResponse, historyResponse] = await Promise.all([
          apiClient.getInventoryCopy(parsedInventoryCopyId),
          apiClient.getInventoryFmvHistory(parsedInventoryCopyId),
        ]);
        if (ignore) {
          return;
        }

        setDetail(detailResponse);
        setHistory(historyResponse);
        setFmvDraft(detailResponse.current_fmv ?? "");
        setHoldDraft(detailResponse.hold_status);
        setGradeDraft(detailResponse.grade_status);
        setStarDraft(detailResponse.star_rating ? String(detailResponse.star_rating) : "");
        setNotesDraft(detailResponse.condition_notes ?? "");
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load inventory copy.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void fetchDetail();

    return () => {
      ignore = true;
    };
  }, [parsedInventoryCopyId]);

  async function saveDetail(): Promise<void> {
    if (!detail) {
      return;
    }

    const payload: InventoryUpdatePayload = {
      current_fmv: fMvDraft.trim() ? fMvDraft.trim() : null,
      hold_status: holdDraft,
      grade_status: gradeDraft,
      star_rating: starDraft ? Number(starDraft) : null,
      condition_notes: notesDraft.trim() ? notesDraft : null,
    };

    setError(null);
    setSuccessMessage(null);
    setIsSaving(true);

    try {
      await apiClient.updateInventoryCopy(detail.inventory_copy_id, payload);
      await loadDetail();
      setSuccessMessage("Asset profile updated.");
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
      } else {
        setError("Unable to save inventory copy changes.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <AppShell>
        <LoadingState
          title="Loading asset profile"
          description="Refreshing valuation details, order metadata, and FMV history."
        />
      </AppShell>
    );
  }

  if (error && !detail) {
    return (
      <AppShell>
        <div className="max-w-4xl">
          <Link
            to="/dashboard"
            className="inline-flex rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
          >
            Back to Dashboard
          </Link>
          <div className="mt-6">
            <StatusBanner tone="error">{error}</StatusBanner>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!detail) {
    return null;
  }

  const metrics = [
    { label: "Cost Basis", value: formatCurrency(detail.acquisition_cost) },
    { label: "Current FMV", value: formatCurrency(detail.current_fmv) },
    {
      label: "Gain / Loss",
      value: formatCurrency(detail.gain_loss),
      className: gainLossClass(detail.gain_loss),
    },
    { label: "Copy Number", value: `#${detail.copy_number}` },
  ];

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <PageHeader
          eyebrow="Asset Profile"
          title={`${detail.title} #${detail.issue_number}`}
          description={`Review valuation history, acquisition context, and copy-level metadata for ${detail.publisher}.`}
          actions={
            <>
              <Link
                to="/dashboard"
                className="inline-flex rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Back to Dashboard
              </Link>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                Inventory Copy <span className="font-medium text-white">#{detail.inventory_copy_id}</span>
              </div>
            </>
          }
        />

        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <Link
            to="/dashboard"
            className="inline-flex rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
          >
            Back to Dashboard
          </Link>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Inventory Copy #{detail.inventory_copy_id}
          </p>
        </div>

        <section className="mt-4 rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-indigo-950/70 p-6 shadow-2xl shadow-cyan-950/20">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-4">
              <span className="inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">
                Asset Profile
              </span>
              <div>
                <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  {detail.title} #{detail.issue_number}
                </h1>
                <p className="mt-2 text-sm text-slate-300 sm:text-base">
                  {detail.publisher}
                  {variantLabel(detail) ? ` | ${variantLabel(detail)}` : " | Standard cover"}
                </p>
              </div>
              <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Retailer</p>
                  <p className="mt-2 font-medium text-white">{detail.retailer}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Order Date</p>
                  <p className="mt-2 font-medium text-white">{formatDate(detail.order_date)}</p>
                </div>
              </div>
            </div>

            <div className="grid w-full gap-3 sm:grid-cols-2 lg:max-w-xl">
              {metrics.map((metric) => (
                <article
                  key={metric.label}
                  className="rounded-2xl border border-white/10 bg-slate-900/80 p-4"
                >
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    {metric.label}
                  </p>
                  <p className={`mt-3 text-2xl font-semibold text-white ${metric.className ?? ""}`}>
                    {metric.value}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {error ? <div className="mt-6"><StatusBanner tone="error">{error}</StatusBanner></div> : null}

        {successMessage ? (
          <div className="mt-6">
            <StatusBanner tone="success">{successMessage}</StatusBanner>
          </div>
        ) : null}

        <section className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <article className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">Investment Snapshot</h2>
                <p className="mt-2 text-sm text-slate-400">
                  Review asset identity, copy-level valuation, and acquisition metadata in one view.
                </p>
              </div>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                  detail.hold_status === "hold"
                    ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-200"
                    : detail.hold_status === "sell"
                      ? "border-amber-400/30 bg-amber-400/10 text-amber-200"
                      : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                }`}
              >
                {detail.hold_status}
              </span>
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Cover Profile</p>
                <div className="mt-3 space-y-2 text-sm text-slate-300">
                  <p>Cover: {detail.cover_name ?? "Standard"}</p>
                  <p>Printing: {detail.printing ?? "Standard"}</p>
                  <p>Ratio: {detail.ratio ?? "Open order"}</p>
                  <p>Variant Type: {detail.variant_type ?? "Primary"}</p>
                  <p>Cover Artist: {detail.cover_artist ?? "Unknown"}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  Acquisition Metadata
                </p>
                <div className="mt-3 space-y-2 text-sm text-slate-300">
                  <p>Source Type: {detail.source_type ?? "Unspecified"}</p>
                  <p>Order ID: #{detail.order_id}</p>
                  <p>Order Item ID: #{detail.order_item_id}</p>
                  <p>Variant ID: #{detail.variant_id}</p>
                  <p>Created: {formatTimestamp(detail.created_at)}</p>
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Condition Notes</p>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">
                {detail.condition_notes || "No condition notes added yet."}
              </p>
            </div>
          </article>

          <article className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
            <h2 className="text-xl font-semibold text-white">Manage Copy</h2>
            <p className="mt-2 text-sm text-slate-400">
              Adjust live FMV, portfolio intent, rating, grading status, and notes for this single
              asset.
            </p>

            <div className="mt-6 space-y-5">
              <label className="block">
                <span className="text-sm font-medium text-slate-300">Current FMV</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={fMvDraft}
                  onChange={(event) => setFmvDraft(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  placeholder="Enter current fair market value"
                />
              </label>

              <div className="grid gap-5 sm:grid-cols-2">
                <label className="block">
                  <span className="text-sm font-medium text-slate-300">Hold Status</span>
                  <select
                    value={holdDraft}
                    onChange={(event) =>
                      setHoldDraft(event.target.value as InventoryDetail["hold_status"])
                    }
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  >
                    <option value="hold">Hold</option>
                    <option value="sell">Sell</option>
                    <option value="sold">Sold</option>
                  </select>
                </label>

                <label className="block">
                  <span className="text-sm font-medium text-slate-300">Grade Status</span>
                  <select
                    value={gradeDraft}
                    onChange={(event) =>
                      setGradeDraft(event.target.value as InventoryDetail["grade_status"])
                    }
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  >
                    <option value="raw">Raw</option>
                    <option value="submitted">Submitted</option>
                    <option value="graded">Graded</option>
                  </select>
                </label>
              </div>

              <label className="block">
                <span className="text-sm font-medium text-slate-300">Star Rating</span>
                <select
                  value={starDraft}
                  onChange={(event) => setStarDraft(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                >
                  <option value="">No rating</option>
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                  <option value="4">4</option>
                  <option value="5">5</option>
                </select>
              </label>

              <label className="block">
                <span className="text-sm font-medium text-slate-300">Condition Notes</span>
                <textarea
                  rows={8}
                  maxLength={2000}
                  value={notesDraft}
                  onChange={(event) => setNotesDraft(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  placeholder="Add grading observations, defects, press notes, or exit-strategy context."
                />
              </label>

              <div className="flex items-center justify-between gap-4">
                <p className="text-sm text-slate-500">{notesDraft.length}/2000 characters</p>
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() => void saveDetail()}
                  className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? "Saving..." : "Save Asset Profile"}
                </button>
              </div>
            </div>
          </article>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">FMV History</h2>
              <p className="mt-2 text-sm text-slate-400">
                Every manual FMV change is preserved as a dated valuation snapshot.
              </p>
            </div>
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">
              {history.length} snapshots
            </span>
          </div>

          {history.length ? (
            <div className="mt-6 overflow-x-auto">
              <table className="min-w-full text-left text-sm text-slate-300">
                <thead className="border-b border-white/10 text-xs uppercase tracking-[0.16em] text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Changed</th>
                    <th className="px-4 py-3">Previous FMV</th>
                    <th className="px-4 py-3">New FMV</th>
                    <th className="px-4 py-3">Delta</th>
                    <th className="px-4 py-3">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((snapshot) => {
                    const delta =
                      snapshot.previous_fmv === null
                        ? null
                        : (Number(snapshot.new_fmv) - Number(snapshot.previous_fmv)).toFixed(2);

                    return (
                      <tr key={snapshot.id} className="border-b border-white/5">
                        <td className="px-4 py-4 text-slate-300">
                          {formatTimestamp(snapshot.changed_at)}
                        </td>
                        <td className="px-4 py-4 text-slate-400">
                          {formatCurrency(snapshot.previous_fmv)}
                        </td>
                        <td className="px-4 py-4 font-medium text-white">
                          {formatCurrency(snapshot.new_fmv)}
                        </td>
                        <td className={`px-4 py-4 ${gainLossClass(delta)}`}>
                          {delta === null ? "Initial mark" : formatCurrency(delta)}
                        </td>
                        <td className="px-4 py-4">
                          <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs uppercase tracking-[0.14em] text-cyan-200">
                            {snapshot.source}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-6">
              <EmptyState
                title="No FMV history yet"
                description="The first manual FMV change will create the opening snapshot for this inventory copy."
              />
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
