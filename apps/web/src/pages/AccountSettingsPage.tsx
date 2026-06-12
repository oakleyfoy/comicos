import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type CollectionResetExecuteResponse,
  type CollectionResetPreviewResponse,
  type CollectionResetSummary,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { patriotInputClass } from "../components/patriotTheme";

const CONFIRMATION_PHRASE = "DELETE MY COLLECTION";

function formatSummaryLine(summary: CollectionResetSummary): string {
  const parts: string[] = [];
  if (summary.inventory_copies) {
    parts.push(`${summary.inventory_copies} inventory ${summary.inventory_copies === 1 ? "copy" : "copies"}`);
  }
  if (summary.orders) {
    parts.push(`${summary.orders} ${summary.orders === 1 ? "order" : "orders"}`);
  }
  if (summary.draft_imports) {
    parts.push(`${summary.draft_imports} draft ${summary.draft_imports === 1 ? "import" : "imports"}`);
  }
  if (summary.gmail_import_records) {
    parts.push(`${summary.gmail_import_records} Gmail import ${summary.gmail_import_records === 1 ? "record" : "records"}`);
  }
  if (summary.retailer_order_snapshots) {
    parts.push(
      `${summary.retailer_order_snapshots} retailer order ${summary.retailer_order_snapshots === 1 ? "snapshot" : "snapshots"}`,
    );
  }
  if (summary.portfolio_items) {
    parts.push(`${summary.portfolio_items} portfolio ${summary.portfolio_items === 1 ? "item" : "items"}`);
  }
  if (parts.length === 0) {
    return "No collection or import data found for your account.";
  }
  return `This will delete ${parts.join(", ")}.`;
}

function SummaryGrid({ title, summary }: { title: string; summary: CollectionResetSummary }): JSX.Element {
  const rows = [
    ["Inventory copies", summary.inventory_copies],
    ["Orders", summary.orders],
    ["Order line items", summary.order_items],
    ["Draft imports", summary.draft_imports],
    ["Gmail import records", summary.gmail_import_records],
    ["Retailer order snapshots", summary.retailer_order_snapshots],
    ["Portfolio items", summary.portfolio_items],
    ["Cover / scan images", summary.cover_images],
    ["Receiving sessions", summary.receiving_sessions],
  ].filter(([, count]) => (count as number) > 0);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">Nothing to delete.</p>
      ) : (
        <ul className="mt-3 space-y-1 text-sm text-slate-700">
          {rows.map(([label, count]) => (
            <li key={label} className="flex justify-between gap-4">
              <span>{label}</span>
              <span className="font-semibold tabular-nums text-slate-900">{count}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-slate-500">Total rows across affected tables: {summary.total_rows}</p>
    </section>
  );
}

export function AccountSettingsPage(): JSX.Element {
  const navigate = useNavigate();
  const [preview, setPreview] = useState<CollectionResetPreviewResponse | null>(null);
  const [result, setResult] = useState<CollectionResetExecuteResponse | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(true);
  const [resetOpen, setResetOpen] = useState(false);
  const [phrase, setPhrase] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPreview = useCallback(async () => {
    setLoadingPreview(true);
    setError(null);
    try {
      const body = await apiClient.previewResetCollectionData();
      setPreview(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load reset preview.");
    } finally {
      setLoadingPreview(false);
    }
  }, []);

  useEffect(() => {
    void loadPreview();
  }, [loadPreview]);

  const canExecute = useMemo(
    () => phrase.trim() === CONFIRMATION_PHRASE && acknowledged && !executing,
    [phrase, acknowledged, executing],
  );

  async function runReset(): Promise<void> {
    if (!canExecute) return;
    setExecuting(true);
    setError(null);
    try {
      const body = await apiClient.executeResetCollectionData({
        confirmation_phrase: phrase.trim(),
        acknowledge_permanent_delete: true,
      });
      setResult(body);
      setResetOpen(false);
      setPhrase("");
      setAcknowledged(false);
      await loadPreview();
      if (body.status === "success") {
        navigate("/dashboard");
      }
    } catch (err) {
      if (err instanceof ApiError && err.data && typeof err.data === "object") {
        const payload = err.data as CollectionResetExecuteResponse;
        if (payload.failed_table || payload.error) {
          setResult(payload);
          setError(
            payload.error
              ? `Reset failed at ${payload.failed_table ?? "unknown"}: ${payload.error}`
              : err.message,
          );
          await loadPreview();
          return;
        }
      }
      setError(err instanceof ApiError ? err.message : "Reset failed.");
    } finally {
      setExecuting(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Settings"
        title="Account & data"
        description="Manage destructive actions for your ComicOS collection. Your login, retailer connections, and Gmail link stay intact."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {result ? (
        <StatusBanner tone={result.status === "success" ? "success" : "warning"}>
          {result.status === "success"
            ? "Collection data was reset. Your portfolio is empty."
            : "Reset finished with remaining rows — contact support if this was unexpected."}
        </StatusBanner>
      ) : null}

      <section className="mt-6 rounded-3xl border border-rose-200 bg-rose-50/80 p-6 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-800">Danger zone</p>
        <h2 className="mt-1 text-lg font-semibold text-slate-900">Reset collection data</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-700">
          Permanently remove inventory, orders, imports, retailer order snapshots, scans, and portfolio holdings for your
          account only. Does not delete your user account, connected retailers, Gmail connection, catalog, market data,
          or watchlists.
        </p>

        {loadingPreview ? (
          <p className="mt-4 text-sm text-slate-600">Loading preview counts…</p>
        ) : preview ? (
          <p className="mt-4 text-sm font-medium text-slate-800">{formatSummaryLine(preview.summary)}</p>
        ) : null}

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="rounded-2xl border border-rose-300 bg-white px-4 py-2.5 text-sm font-semibold text-rose-800 transition hover:border-rose-400 hover:bg-rose-50"
            onClick={() => {
              setResetOpen(true);
              void loadPreview();
            }}
          >
            Reset collection data
          </button>
          <Link
            to="/dashboard"
            className="rounded-2xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-white"
          >
            Back to portfolio
          </Link>
        </div>
      </section>

      {resetOpen && preview ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-collection-title"
        >
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 shadow-xl">
            <h2 id="reset-collection-title" className="text-lg font-semibold text-slate-900">
              Confirm collection reset
            </h2>
            <p className="mt-2 text-sm text-slate-600">{formatSummaryLine(preview.summary)}</p>
            <div className="mt-4">
              <SummaryGrid title="Dry-run counts" summary={preview.summary} />
            </div>

            <label className="mt-4 block text-sm text-slate-700">
              Type <span className="font-mono font-semibold">{CONFIRMATION_PHRASE}</span> to confirm
              <input
                type="text"
                className={`mt-2 w-full ${patriotInputClass}`}
                value={phrase}
                onChange={(e) => setPhrase(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
            </label>

            <label className="mt-4 flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="mt-1"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
              />
              <span>I understand this cannot be undone.</span>
            </label>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                type="button"
                className="rounded-2xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700"
                onClick={() => {
                  setResetOpen(false);
                  setPhrase("");
                  setAcknowledged(false);
                }}
                disabled={executing}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-2xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!canExecute}
                onClick={() => void runReset()}
              >
                {executing ? "Resetting…" : "Permanently reset collection data"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <SummaryGrid title="Deleted" summary={result.deleted} />
          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-900">Remaining</h3>
            <ul className="mt-3 space-y-1 text-sm text-slate-700">
              <li className="flex justify-between">
                <span>Inventory copies</span>
                <span className="font-semibold tabular-nums">{result.remaining.inventory_copies}</span>
              </li>
              <li className="flex justify-between">
                <span>Orders</span>
                <span className="font-semibold tabular-nums">{result.remaining.orders}</span>
              </li>
              <li className="flex justify-between">
                <span>Draft imports</span>
                <span className="font-semibold tabular-nums">{result.remaining.draft_imports}</span>
              </li>
            </ul>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
