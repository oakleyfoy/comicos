import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type GmailStatusResponse,
  type GmailSyncStatusResponse,
} from "../api/client";
import {
  consumeGmailConnectedSearchParam,
  startGmailOAuth,
} from "../lib/gmailConnect";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { LegacyFeatureBanner } from "../components/LegacyFeatureBanner";

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusBadgeClass(isPositive: boolean): string {
  return isPositive
    ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
    : "border-amber-400/20 bg-amber-400/10 text-amber-800";
}

export function IntegrationsPage() {
  const [gmailStatus, setGmailStatus] = useState<GmailStatusResponse | null>(null);
  const [gmailSyncStatus, setGmailSyncStatus] = useState<GmailSyncStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [ebayStatus, setEbayStatus] = useState<Awaited<ReturnType<typeof apiClient.getEbayMarketplaceIntegrationStatus>> | null>(
    null,
  );

  async function loadStatus(): Promise<void> {
    const [status, syncStatus, ebay] = await Promise.all([
      apiClient.getGmailStatus(),
      apiClient.getGmailSyncSummary(),
      apiClient.getEbayMarketplaceIntegrationStatus().catch(() => null),
    ]);
    setGmailStatus(status);
    setGmailSyncStatus(syncStatus);
    setEbayStatus(ebay);
  }

  useEffect(() => {
    let ignore = false;

    void Promise.all([
      apiClient.getGmailStatus(),
      apiClient.getGmailSyncSummary(),
      apiClient.getEbayMarketplaceIntegrationStatus().catch(() => null),
    ])
      .then(([status, syncStatus, ebay]) => {
        if (!ignore) {
          setGmailStatus(status);
          setGmailSyncStatus(syncStatus);
          setEbayStatus(ebay);
        }
      })
      .catch((loadError) => {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load Gmail status.");
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
    if (consumeGmailConnectedSearchParam()) {
      setSuccess("Gmail connected. Email receipts will still create drafts only for review.");
      void loadStatus();
    }
  }, []);

  async function handleConnect(): Promise<void> {
    setIsWorking(true);
    setError(null);
    try {
      await startGmailOAuth("/settings/integrations");
    } catch (connectError) {
      if (connectError instanceof ApiError) {
        setError(connectError.message);
      } else {
        setError("Unable to start Gmail connection.");
      }
      setIsWorking(false);
    }
  }

  async function handleDisconnect(): Promise<void> {
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.disconnectGmail();
      await loadStatus();
      setSuccess("Gmail disconnected. Tokens were removed and no future sync can run until reconnect.");
    } catch (disconnectError) {
      if (disconnectError instanceof ApiError) {
        setError(disconnectError.message);
      } else {
        setError("Unable to disconnect Gmail.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  async function handleAutoSyncToggle(nextEnabled: boolean): Promise<void> {
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      const syncStatus = await apiClient.updateGmailSyncSettings({
        auto_sync_enabled: nextEnabled,
      });
      setGmailSyncStatus(syncStatus);
      await loadStatus();
      setSuccess(
        nextEnabled
          ? "Gmail auto sync enabled. Scheduled runs still create drafts only for review."
          : "Gmail auto sync disabled.",
      );
    } catch (syncError) {
      if (syncError instanceof ApiError) {
        setError(syncError.message);
      } else {
        setError("Unable to update Gmail auto sync settings.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <AppShell>
      <LegacyFeatureBanner feature="Gmail receipt integration" />
      <PageHeader
        eyebrow="Integrations"
        title="Email Receipt Integrations"
        description="Connect Gmail to import supported receipt emails into draft imports. Email receipts create drafts for review only. Inventory is never created automatically."
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
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Gmail</p>
              <h2 className="mt-1 text-2xl font-semibold text-slate-900">Receipt Sync Foundation</h2>
            </div>
            {isLoading ? (
              <p className="text-sm text-slate-600">Loading Gmail connection status...</p>
            ) : (
              <div className="space-y-3 text-sm text-slate-300">
                <div className="flex flex-wrap gap-3">
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(Boolean(gmailStatus?.configured))}`}
                  >
                    {gmailStatus?.configured ? "Configured" : "Not configured"}
                  </span>
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(Boolean(gmailStatus?.connected))}`}
                  >
                    {gmailStatus?.connected ? "Connected" : "Not connected"}
                  </span>
                </div>
                <p>
                  Configuration:{" "}
                  <span className="font-medium text-slate-900">
                    {gmailStatus?.configured ? "Configured" : "Missing Google OAuth settings"}
                  </span>
                </p>
                <p>
                  Connection:{" "}
                  <span className="font-medium text-slate-900">
                    {gmailStatus?.connected ? "Connected" : "Not connected"}
                  </span>
                </p>
                <p>
                  Gmail account:{" "}
                  <span className="font-medium text-slate-900">
                    {gmailStatus?.connected ? gmailStatus.gmail_email ?? "Unknown" : "None"}
                  </span>
                </p>
                <p>
                  Token expires:{" "}
                  <span className="font-medium text-slate-900">
                    {formatDateTime(gmailStatus?.token_expires_at ?? null)}
                  </span>
                </p>
                <p>
                  Auto Sync:{" "}
                  <span className="font-medium text-slate-900">
                    {gmailSyncStatus?.auto_sync_enabled ? "Enabled" : "Disabled"}
                  </span>
                </p>
                <p>
                  Last sync started:{" "}
                  <span className="font-medium text-slate-900">
                    {formatDateTime(gmailSyncStatus?.last_sync_started_at ?? null)}
                  </span>
                </p>
                <p>
                  Last sync completed:{" "}
                  <span className="font-medium text-slate-900">
                    {formatDateTime(gmailSyncStatus?.last_sync_completed_at ?? null)}
                  </span>
                </p>
                <p>
                  Last sync status:{" "}
                  <span className="font-medium text-slate-900">
                    {gmailSyncStatus?.last_sync_status ?? "Never run"}
                  </span>
                </p>
                {gmailSyncStatus?.last_sync_error ? (
                  <div className="rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200">
                    <p className="font-semibold">Last sync error</p>
                    <p className="mt-2">{gmailSyncStatus.last_sync_error}</p>
                  </div>
                ) : null}
                {!gmailStatus?.configured ? (
                  <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-100">
                    <p className="font-semibold">Gmail is not configured locally.</p>
                    <p className="mt-2">
                      Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`
                      in your local backend env, then follow `docs/GMAIL_OAUTH_SETUP.md`.
                    </p>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-4">
            <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-200">
              <input
                type="checkbox"
                checked={Boolean(gmailSyncStatus?.auto_sync_enabled)}
                disabled={isLoading || isWorking || !gmailStatus?.connected}
                onChange={(event) => void handleAutoSyncToggle(event.target.checked)}
              />
              <span className="font-medium">Auto Sync Gmail receipts</span>
            </label>
            <div className="flex flex-col gap-3 sm:flex-row">
              {!gmailStatus?.connected ? (
                <button
                  type="button"
                  disabled={isLoading || isWorking || !gmailStatus?.configured}
                  onClick={() => void handleConnect()}
                  className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isWorking ? "Working..." : "Connect Gmail"}
                </button>
              ) : null}
              <button
                type="button"
                disabled={isLoading || isWorking || !gmailStatus?.connected}
                onClick={() => void handleDisconnect()}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Disconnect Gmail
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Marketplace Integration</p>
        <h2 className="mt-1 text-2xl font-semibold text-slate-900">eBay Integration</h2>
        <div className="mt-4 space-y-2 text-sm text-slate-300">
          <span
            className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(ebayStatus?.status === "Configured")}`}
          >
            {ebayStatus?.status ?? (isLoading ? "Loading…" : "Not Configured")}
          </span>
          <p>
            Environment:{" "}
            <span className="font-medium text-slate-900">{ebayStatus?.environment ?? "—"}</span>
          </p>
          <p>
            Client ID:{" "}
            <span className="font-medium text-slate-900">
              {ebayStatus?.client_id_present ? "Present" : "Missing"}
            </span>
          </p>
          <p>
            Client secret:{" "}
            <span className="font-medium text-slate-900">
              {ebayStatus?.client_secret_present ? "Present" : "Missing"}
            </span>
          </p>
          {ebayStatus?.detail ? <p className="text-slate-400">{ebayStatus.detail}</p> : null}
          <p className="text-xs text-slate-500">
            Status reflects server environment variables only. Remote connectivity is not tested from this page.
          </p>
          <Link
            to="/ops/marketplace-search"
            className="inline-block text-sm font-medium text-red-400 hover:text-red-300 hover:underline"
          >
            Marketplace Search Dashboard (ops)
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
