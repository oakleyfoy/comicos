import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type GmailImportedDraft } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

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

export function EmailImportsPage() {
  const [imports, setImports] = useState<GmailImportedDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncJobId, setSyncJobId] = useState<string | null>(null);

  const draftCount = useMemo(
    () => imports.filter((entry) => entry.draft_import.status === "draft").length,
    [imports],
  );

  async function loadImports(): Promise<void> {
    const records = await apiClient.getGmailImports();
    setImports(records);
  }

  useEffect(() => {
    let ignore = false;

    void apiClient
      .getGmailImports()
      .then((records) => {
        if (!ignore) {
          setImports(records);
        }
      })
      .catch((loadError) => {
        if (!ignore) {
          if (loadError instanceof ApiError) {
            setError(loadError.message);
          } else {
            setError(
              loadError instanceof Error ? loadError.message : "Unable to load email imports.",
            );
          }
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
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

  return (
    <AppShell>
      <PageHeader
        eyebrow="Email Draft Imports"
        title="Gmail Receipt Drafts"
        description="Sync supported Gmail receipt senders into reviewable draft imports. Email receipts create drafts for review. Inventory is never created automatically."
        actions={
          <div className="flex flex-wrap gap-3">
            <Link
              to="/settings/integrations"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
            >
              Manage Gmail
            </Link>
            <button
              type="button"
              disabled={isSyncing}
              onClick={() => void handleSync()}
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSyncing ? "Syncing Gmail..." : "Sync Gmail"}
            </button>
          </div>
        }
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {success ? (
        <div className="mt-6">
          <StatusBanner tone="success">{success}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
            <p className="text-sm font-medium text-slate-400">Imported Gmail Receipts</p>
            <p className="mt-2 text-3xl font-semibold text-white">{imports.length}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
            <p className="text-sm font-medium text-slate-400">Drafts Awaiting Review</p>
            <p className="mt-2 text-3xl font-semibold text-white">{draftCount}</p>
          </div>
          <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-100">
            Supported senders: eBay, Whatnot, Midtown Comics, DCBS, and Third Eye. Confirm remains the only path that creates inventory.
          </div>
        </div>
      </section>

      {isLoading ? (
        <div className="mt-6">
          <StatusBanner tone="info">Loading imported Gmail drafts...</StatusBanner>
        </div>
      ) : null}

      {!isLoading && imports.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="No Gmail drafts yet"
            description="Connect Gmail, then run a sync to import supported receipt emails into draft imports for review."
            action={
              <Link
                to="/settings/integrations"
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                Connect Gmail
              </Link>
            }
          />
        </div>
      ) : null}

      {!isLoading && imports.length > 0 ? (
        <section className="mt-6 space-y-4">
          {imports.map((entry) => (
            <article
              key={entry.external_message_id}
              className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Gmail message {entry.external_message_id}
                  </p>
                  <h2 className="text-xl font-semibold text-white">
                    {entry.draft_import.parsed_payload_json.retailer ?? "Unknown retailer"}
                  </h2>
                  <p className="text-sm text-slate-400">
                    Imported {formatTimestamp(entry.imported_at)} into draft #{entry.draft_import.id}
                  </p>
                  <p className="text-sm text-slate-300">
                    Status:{" "}
                    <span className="font-medium text-white">{entry.draft_import.status}</span> | Items:{" "}
                    {entry.draft_import.parsed_payload_json.items.length}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link
                    to={`/orders/import?importId=${entry.draft_import.id}`}
                    className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                  >
                    Review Draft
                  </Link>
                  {entry.draft_import.order_id ? (
                    <Link
                      to={`/orders/${entry.draft_import.order_id}`}
                      className="rounded-2xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/15"
                    >
                      View Order
                    </Link>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </AppShell>
  );
}
