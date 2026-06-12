import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type GmailImportedDraft } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { LegacyFeatureBanner } from "../components/LegacyFeatureBanner";
import { StatusBanner } from "../components/StatusBanner";
import { consumeGmailConnectedSearchParam, GMAIL_IMPORTS_PATH, startGmailOAuth } from "../lib/gmailConnect";

const POLL_INTERVAL_MS = 1500;

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function isPendingGmailImport(entry: GmailImportedDraft): boolean {
  return entry.draft_import.status === "draft";
}

function GmailImportCard({
  entry,
  deletingDraftId,
  isSyncing,
  onDelete,
}: {
  entry: GmailImportedDraft;
  deletingDraftId: number | null;
  isSyncing: boolean;
  onDelete: (entry: GmailImportedDraft) => void;
}) {
  const pending = isPendingGmailImport(entry);

  return (
    <article
      className={`flex min-w-0 flex-col rounded-2xl border p-4 shadow-lg shadow-black/20 ${
        pending
          ? "border-cyan-400/25 bg-slate-950/95"
          : "border-white/10 bg-slate-900/80 opacity-95"
      }`}
    >
      <h2 className="truncate text-base font-semibold text-white">
        {entry.draft_import.parsed_payload_json.retailer ?? "Unknown retailer"}
      </h2>
      <p className="mt-2 rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-slate-100">
        Imported {formatTimestamp(entry.imported_at)}
      </p>
      <p className="mt-2 text-xs text-slate-200">
        <span className="font-medium capitalize text-slate-100">{entry.draft_import.status}</span>
        {", "}
        {entry.draft_import.parsed_payload_json.items.length} item
        {entry.draft_import.parsed_payload_json.items.length === 1 ? "" : "s"}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {pending ? (
          <Link
            to={`/orders/import?importId=${entry.draft_import.id}`}
            className="rounded-xl border border-rose-400/50 bg-rose-950/90 px-4 py-2.5 text-sm font-semibold text-rose-50 transition hover:border-rose-300/70 hover:bg-rose-900"
          >
            Review
          </Link>
        ) : entry.draft_import.order_id ? (
          <Link
            to={`/orders/${entry.draft_import.order_id}`}
            className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/15"
          >
            View Order
          </Link>
        ) : (
          <Link
            to={`/orders/import?importId=${entry.draft_import.id}`}
            className="rounded-xl border border-white/15 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
          >
            View Import
          </Link>
        )}
        {pending && entry.draft_import.order_id ? (
          <Link
            to={`/orders/${entry.draft_import.order_id}`}
            className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/15"
          >
            View Order
          </Link>
        ) : null}
        {pending ? (
          <button
            type="button"
            disabled={deletingDraftId === entry.draft_import.id || isSyncing}
            onClick={() => onDelete(entry)}
            className="rounded-lg border border-white/15 bg-slate-900/80 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-slate-400 hover:bg-slate-800 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deletingDraftId === entry.draft_import.id ? "Deleting…" : "Delete"}
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function EmailImportsPage() {
  const [imports, setImports] = useState<GmailImportedDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [gmailConnected, setGmailConnected] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncJobId, setSyncJobId] = useState<string | null>(null);
  const [deletingDraftId, setDeletingDraftId] = useState<number | null>(null);
  const [isConnectingGmail, setIsConnectingGmail] = useState(false);

  useEffect(() => {
    if (consumeGmailConnectedSearchParam()) {
      setSuccess("Gmail connected. You can sync receipt emails into drafts.");
      void refreshPage();
    }
  }, []);

  const draftCount = useMemo(
    () => imports.filter((entry) => isPendingGmailImport(entry)).length,
    [imports],
  );
  const completedImports = useMemo(
    () => imports.filter((entry) => !isPendingGmailImport(entry)),
    [imports],
  );
  const pendingImports = useMemo(
    () => imports.filter((entry) => isPendingGmailImport(entry)),
    [imports],
  );

  async function loadImports(): Promise<void> {
    const records = await apiClient.getGmailImports();
    setImports(records);
  }

  async function refreshPage(): Promise<void> {
    setError(null);
    setIsLoading(true);
    try {
      const status = await apiClient.getGmailStatus();
      setGmailConnected(status.connected);
      if (!status.connected) {
        setImports([]);
        return;
      }
      await loadImports();
    } catch (loadError) {
      if (loadError instanceof ApiError) {
        setError(loadError.message);
      } else {
        setError(loadError instanceof Error ? loadError.message : "Unable to load email imports.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshPage();
  }, []);

  useEffect(() => {
    if (!syncJobId) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const poll = async () => {
      try {
        const job = await apiClient.getGmailSyncStatus(syncJobId);
        if (cancelled) {
          return;
        }

        if (job.status === "finished") {
          await loadImports();
          setSuccess("Gmail sync finished. Review imported drafts before confirming any inventory.");
          setIsSyncing(false);
          return;
        }

        if (job.status === "failed") {
          setError(job.error ?? "Gmail sync failed.");
          setIsSyncing(false);
          return;
        }

        timeoutId = window.setTimeout(() => {
          void poll();
        }, POLL_INTERVAL_MS);
      } catch (pollError) {
        if (cancelled) {
          return;
        }

        setError(pollError instanceof Error ? pollError.message : "Unable to refresh Gmail sync.");
        setIsSyncing(false);
      }
    };

    timeoutId = window.setTimeout(() => {
      void poll();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [syncJobId]);

  async function handleSync(): Promise<void> {
    setError(null);
    setSuccess(null);
    setIsSyncing(true);
    try {
      const response = await apiClient.syncGmail();
      setSyncJobId(response.job_id);
      setSuccess("Gmail sync queued. Imported emails will create drafts only.");
    } catch (syncError) {
      if (syncError instanceof ApiError) {
        setError(syncError.message);
      } else {
        setError("Unable to start Gmail sync.");
      }
      setIsSyncing(false);
    }
  }

  async function handleConnectGmail(): Promise<void> {
    setError(null);
    setSuccess(null);
    setIsConnectingGmail(true);
    try {
      await startGmailOAuth(GMAIL_IMPORTS_PATH);
    } catch (connectError) {
      if (connectError instanceof ApiError) {
        setError(connectError.message);
      } else {
        setError("Unable to start Gmail connection.");
      }
      setIsConnectingGmail(false);
    }
  }

  async function handleDeleteGmailImport(entry: GmailImportedDraft): Promise<void> {
    const draftId = entry.draft_import.id;
    const retailer = entry.draft_import.parsed_payload_json.retailer ?? "this receipt";
    const confirmed = window.confirm(
      `Delete the draft for ${retailer}? The Gmail receipt will be removed from this list and can be imported again on the next sync.`,
    );
    if (!confirmed) {
      return;
    }

    setError(null);
    setSuccess(null);
    setDeletingDraftId(draftId);
    try {
      await apiClient.deleteGmailImport(draftId);
      setImports((current) => current.filter((row) => row.draft_import.id !== draftId));
      setSuccess("Gmail receipt removed and draft discarded.");
    } catch (deleteError) {
      if (deleteError instanceof ApiError) {
        setError(deleteError.message);
      } else {
        setError("Unable to delete this Gmail import.");
      }
    } finally {
      setDeletingDraftId(null);
    }
  }

  return (
    <AppShell>
      <LegacyFeatureBanner feature="Gmail receipt import" />
      <PageHeader
        eyebrow="Email Draft Imports"
        title="Gmail Receipt Drafts"
        description="Sync supported Gmail receipt senders into reviewable draft imports. Email receipts create drafts for review. Inventory is never created automatically."
        actions={
          <div className="flex flex-wrap gap-3">
            <Link
              to="/settings/integrations"
              className="rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-900 transition hover:border-cyan-500/50 hover:bg-slate-50"
            >
              Gmail settings
            </Link>
            <button
              type="button"
              disabled={isSyncing || isConnectingGmail}
              onClick={() => void handleSync()}
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSyncing ? "Syncing Gmail..." : "Sync Gmail"}
            </button>
          </div>
        }
      />

      {error ? (
        <div className="mt-6 space-y-3">
          <StatusBanner tone="error">{error}</StatusBanner>
          {/reconnect gmail|authorization expired|invalid_grant/i.test(error) ? (
            <button
              type="button"
              disabled={isConnectingGmail}
              onClick={() => void handleConnectGmail()}
              className="inline-flex rounded-2xl bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isConnectingGmail ? "Connecting…" : "Connect Gmail"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => void refreshPage()}
            className="rounded-2xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40"
          >
            Try again
          </button>
        </div>
      ) : null}

      {success ? (
        <div className="mt-6">
          <StatusBanner tone="success">{success}</StatusBanner>
        </div>
      ) : null}

      {gmailConnected === false && !isLoading ? (
        <div className="mt-6">
          <EmptyState
            title="Connect Gmail first"
            description="Link your Gmail account before syncing receipt emails into draft imports."
            action={
              <button
                type="button"
                disabled={isConnectingGmail}
                onClick={() => void handleConnectGmail()}
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isConnectingGmail ? "Connecting…" : "Connect Gmail"}
              </button>
            }
          />
        </div>
      ) : null}

      {gmailConnected && !isLoading ? (
      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
            <p className="text-base font-semibold text-slate-200">Imported Gmail Receipts</p>
            <p className="mt-2 text-3xl font-semibold text-white">{imports.length}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
            <p className="text-base font-semibold text-slate-200">Drafts Awaiting Review</p>
            <p className="mt-2 text-3xl font-semibold text-white">{draftCount}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
            <p className="text-base font-semibold text-slate-200">Completed</p>
            <p className="mt-2 text-3xl font-semibold text-white">{completedImports.length}</p>
          </div>
        </div>
      </section>
      ) : null}

      {isLoading ? (
        <div className="mt-6">
          <StatusBanner tone="info">Loading Gmail import status...</StatusBanner>
        </div>
      ) : null}

      {gmailConnected && !isLoading && imports.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="No Gmail drafts yet"
            description="Run a sync to import supported receipt emails into draft imports for review."
            action={
              <button
                type="button"
                disabled={isSyncing}
                onClick={() => void handleSync()}
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSyncing ? "Syncing…" : "Sync Gmail"}
              </button>
            }
          />
        </div>
      ) : null}

      {gmailConnected && !isLoading && imports.length > 0 ? (
        <div className="mt-6 space-y-8">
          <section>
            <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
              <div>
                <p className="text-sm font-bold uppercase tracking-[0.12em] text-cyan-900">Needs review</p>
                <h2 className="mt-1.5 text-2xl font-bold text-slate-900">Drafts to finish</h2>
              </div>
              <p className="text-base font-semibold text-slate-800">{pendingImports.length} waiting</p>
            </div>
            {pendingImports.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-base font-medium text-slate-700">
                No drafts waiting. Sync Gmail or confirm imports from the list below.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {pendingImports.map((entry) => (
                  <GmailImportCard
                    key={entry.external_message_id}
                    entry={entry}
                    deletingDraftId={deletingDraftId}
                    isSyncing={isSyncing}
                    onDelete={(row) => void handleDeleteGmailImport(row)}
                  />
                ))}
              </div>
            )}
          </section>

          <section>
            <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
              <div>
                <p className="text-sm font-bold uppercase tracking-[0.12em] text-slate-700">Done</p>
                <h2 className="mt-1.5 text-2xl font-bold text-slate-900">Confirmed imports</h2>
              </div>
              <p className="text-base font-semibold text-slate-800">{completedImports.length} completed</p>
            </div>
            {completedImports.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-base font-medium text-slate-700">
                Confirmed Gmail imports will appear here after you create an order.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {completedImports.map((entry) => (
                  <GmailImportCard
                    key={entry.external_message_id}
                    entry={entry}
                    deletingDraftId={deletingDraftId}
                    isSyncing={isSyncing}
                    onDelete={(row) => void handleDeleteGmailImport(row)}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
