import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type RetailerAccountRead,
  type RetailerAccountSyncResponse,
  type RetailerLocalSyncCompleteRequest,
  type RetailerOrderSnapshotRead,
  type RetailerSyncRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  getMidtownExtensionInstallUrl,
  isMidtownExtensionCaptureError,
  isMidtownExtensionCaptureResult,
  isMidtownExtensionStatusMessage,
  type MidtownExtensionCaptureResult,
  MIDTOWN_EXTENSION_CAPTURE_ERROR_EVENT,
  MIDTOWN_EXTENSION_CAPTURE_REQUEST_EVENT,
  MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT,
  MIDTOWN_EXTENSION_PING_EVENT,
  MIDTOWN_EXTENSION_READY_EVENT,
  MIDTOWN_EXTENSION_STATUS_EVENT,
} from "../lib/midtownExtensionBridge";


function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Never";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}


function formatMoney(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(parsed);
}


function statusBadgeClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "connected" || normalized === "succeeded") {
    return "border-emerald-400/20 bg-emerald-400/10 text-emerald-200";
  }
  if (normalized === "needs_attention" || normalized === "failed" || normalized === "error") {
    return "border-rose-400/20 bg-rose-400/10 text-rose-200";
  }
  return "border-amber-400/20 bg-amber-400/10 text-amber-100";
}

type NeedsAttentionState = {
  actionRequired: string | null;
  suggestedNextStep: string | null;
  retryAllowedAt: string | null;
  challengeDetected: boolean;
  errorCode: string | null;
};

type LocalSyncSession = {
  accountId: number;
  syncRunId: number;
  captureToken: string;
  captureTokenExpiresAt: string;
};

type ExtensionCaptureStatus = {
  connected: boolean;
  midtownPageDetected: boolean;
  domReadSuccess: boolean;
  lastMessage: string | null;
};

function readSummaryString(summary: Record<string, unknown>, key: string): string | null {
  const value = summary[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function readSummaryNumber(summary: Record<string, unknown>, key: string): number {
  const value = summary[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function deriveNeedsAttentionState(run: RetailerSyncRunRead | null): NeedsAttentionState {
  const summary = (run?.summary_json ?? {}) as Record<string, unknown>;
  return {
    actionRequired: readSummaryString(summary, "action_required"),
    suggestedNextStep: readSummaryString(summary, "suggested_next_step"),
    retryAllowedAt: readSummaryString(summary, "retry_allowed_at"),
    challengeDetected: summary["challenge_detected"] === true,
    errorCode: readSummaryString(summary, "error_code"),
  };
}

function isRetryBlocked(retryAllowedAt: string | null): boolean {
  if (!retryAllowedAt) {
    return false;
  }
  const retryAt = new Date(retryAllowedAt);
  return Number.isFinite(retryAt.getTime()) && retryAt.getTime() > Date.now();
}

export function ConnectedRetailersPage() {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState<RetailerAccountRead[]>([]);
  const [orders, setOrders] = useState<RetailerOrderSnapshotRead[]>([]);
  const [runs, setRuns] = useState<RetailerSyncRunRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [expandedOrderIds, setExpandedOrderIds] = useState<Record<number, boolean>>({});
  const [pendingMidtownCapture, setPendingMidtownCapture] = useState<MidtownExtensionCaptureResult | null>(null);
  const [latestCompletedRetailerOrders, setLatestCompletedRetailerOrders] = useState<
    RetailerOrderSnapshotRead[]
  >([]);
  const [latestCompletedRun, setLatestCompletedRun] = useState<RetailerSyncRunRead | null>(null);
  const [extensionCaptureStatus, setExtensionCaptureStatus] = useState<ExtensionCaptureStatus>({
    connected: false,
    midtownPageDetected: false,
    domReadSuccess: false,
    lastMessage: null,
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showAnotherMidtownPrompt, setShowAnotherMidtownPrompt] = useState(false);
  const [midtownExtensionReady, setMidtownExtensionReady] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("Midtown Comics");
  const [syncEnabled, setSyncEnabled] = useState(false);
  const [localSyncSession, setLocalSyncSession] = useState<LocalSyncSession | null>(null);

  const account = accounts[0] ?? null;
  const latestRun = runs[0] ?? null;
  const needsAttention = useMemo(() => deriveNeedsAttentionState(latestRun), [latestRun]);
  const retryBlocked = useMemo(
    () => isRetryBlocked(needsAttention.retryAllowedAt),
    [needsAttention.retryAllowedAt],
  );
  const latestCompletedRetailerOrder = latestCompletedRetailerOrders[0] ?? orders[0] ?? null;
  const latestCompletedRetailerOrderCount = latestCompletedRetailerOrders.length || (latestCompletedRetailerOrder ? 1 : 0);
  const midtownExtensionInstallUrl = useMemo(() => getMidtownExtensionInstallUrl(), []);

  async function loadPage(): Promise<void> {
    const [accountResponse, orderResponse] = await Promise.all([
      apiClient.getRetailerAccounts(),
      apiClient.getRetailerOrders(),
    ]);
    setAccounts(accountResponse.items);
    setOrders(orderResponse.items);
    if (accountResponse.items[0]) {
      const runResponse = await apiClient.getRetailerAccountSyncRuns(accountResponse.items[0].id);
      setRuns(runResponse.items);
      setDisplayName(accountResponse.items[0].display_name ?? "Midtown Comics");
      setSyncEnabled(accountResponse.items[0].sync_enabled);
    } else {
      setRuns([]);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void loadPage()
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load connected retailers.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function handleExtensionReady(): void {
      setMidtownExtensionReady(true);
      setExtensionCaptureStatus((current) => ({
        ...current,
        connected: true,
        lastMessage: "Extension Connected",
      }));
    }

    function handleExtensionStatus(event: Event): void {
      const customEvent = event as CustomEvent<unknown>;
      if (!isMidtownExtensionStatusMessage(customEvent.detail)) {
        return;
      }
      const status = customEvent.detail;
      setExtensionCaptureStatus((current) => {
        if (status.stage === "midtown_page_detected") {
          return {
            ...current,
            midtownPageDetected: true,
            lastMessage: status.message,
          };
        }
        if (status.stage === "dom_read_success") {
          return {
            ...current,
            domReadSuccess: true,
            lastMessage: status.message,
          };
        }
        return {
          ...current,
          lastMessage: status.message,
        };
      });
    }

    function handleCaptureResult(event: Event): void {
      const customEvent = event as CustomEvent<unknown>;
      if (!isMidtownExtensionCaptureResult(customEvent.detail)) {
        return;
      }
      const captureDiagnostics = customEvent.detail.detailPages[0]?.capture_diagnostics ?? null;
      const htmlLength = captureDiagnostics?.html_length ?? 0;
      const currentUrl = captureDiagnostics?.current_url ?? "unknown";
      if (!customEvent.detail.captureToken || !customEvent.detail.historyHtml) {
        setError("Midtown extension returned incomplete data. Open the Midtown order detail page and try again.");
        setIsWorking(false);
        return;
      }
      if (!currentUrl || currentUrl === "unknown" || htmlLength === 0) {
        setPendingMidtownCapture(null);
        setError("ComicOS could not read the Midtown page. Make sure the Midtown order tab is open and try again.");
        setIsWorking(false);
        return;
      }
      setPendingMidtownCapture(customEvent.detail);
      setSuccess(null);
      setError(null);
      setIsWorking(false);
    }

    function handleCaptureError(event: Event): void {
      const customEvent = event as CustomEvent<unknown>;
      if (!isMidtownExtensionCaptureError(customEvent.detail)) {
        return;
      }
      setLocalSyncSession(null);
      setError(customEvent.detail.message);
      setIsWorking(false);
    }

    window.addEventListener(MIDTOWN_EXTENSION_READY_EVENT, handleExtensionReady);
    window.addEventListener(MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT, handleCaptureResult);
    window.addEventListener(MIDTOWN_EXTENSION_CAPTURE_ERROR_EVENT, handleCaptureError);
    window.addEventListener(MIDTOWN_EXTENSION_STATUS_EVENT, handleExtensionStatus);
    window.dispatchEvent(new CustomEvent(MIDTOWN_EXTENSION_PING_EVENT));
    return () => {
      window.removeEventListener(MIDTOWN_EXTENSION_READY_EVENT, handleExtensionReady);
      window.removeEventListener(MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT, handleCaptureResult);
      window.removeEventListener(MIDTOWN_EXTENSION_CAPTURE_ERROR_EVENT, handleCaptureError);
      window.removeEventListener(MIDTOWN_EXTENSION_STATUS_EVENT, handleExtensionStatus);
    };
  }, []);

  const visibleOrders = useMemo(
    () => orders.filter((row) => !account || row.retailer_account_id === account.id).slice(0, 8),
    [account, orders],
  );
  const pendingCaptureDiagnostics = pendingMidtownCapture?.detailPages[0]?.capture_diagnostics ?? null;
  const pendingItemsDetected = pendingCaptureDiagnostics?.items_detected_client_side ?? 0;
  const pendingCaptureWarning = pendingItemsDetected < 2;

  async function refreshWithMessage(message?: string): Promise<void> {
    await loadPage();
    setPassword("");
    if (message) {
      setSuccess(message);
    }
  }

  async function sendPendingMidtownCapture(): Promise<void> {
    if (!pendingMidtownCapture) {
      return;
    }
    const payload: RetailerLocalSyncCompleteRequest = {
      helper_token: pendingMidtownCapture.captureToken,
      history_html: pendingMidtownCapture.historyHtml,
      detail_pages: pendingMidtownCapture.detailPages,
    };
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    setShowAnotherMidtownPrompt(false);
    try {
      const response = await apiClient.completeRetailerLocalSync(
        pendingMidtownCapture.accountId,
        pendingMidtownCapture.syncRunId,
        payload,
      );
      setLatestCompletedRetailerOrders(response.orders);
      setLatestCompletedRun(response.run);
      setPendingMidtownCapture(null);
      setLocalSyncSession(null);
      setShowAnotherMidtownPrompt(true);
      await refreshWithMessage(
        response.run.status === "succeeded"
          ? "Midtown order captured. Review the retailer order below or continue with another capture."
          : "Midtown browser capture finished but needs attention.",
      );
    } catch (completeError) {
      if (completeError instanceof ApiError || completeError instanceof Error) {
        setError(completeError.message);
      } else {
        setError("Unable to finish Midtown capture.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  function discardPendingMidtownCapture(): void {
    setPendingMidtownCapture(null);
    setIsWorking(false);
  }

  function openRetailerOrderReview(order: RetailerOrderSnapshotRead): void {
    navigate(`/retailer-orders/${order.id}`);
  }

  function toggleOrderDetails(orderId: number): void {
    setExpandedOrderIds((current) => ({
      ...current,
      [orderId]: !current[orderId],
    }));
  }

  async function handleSaveAccount(): Promise<void> {
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      if (!account && (!username.trim() || !password.trim())) {
        throw new Error("Username and password are required to connect Midtown.");
      }
      if (!account) {
        await apiClient.saveRetailerAccount({
          retailer: "midtown",
          username: username.trim(),
          password,
          display_name: displayName.trim() || "Midtown Comics",
          sync_enabled: syncEnabled,
        });
        setUsername("");
        await refreshWithMessage("Midtown account connected.");
        return;
      }
      await apiClient.updateRetailerAccount(account.id, {
        username: username.trim() || undefined,
        password: password.trim() || undefined,
        display_name: displayName.trim() || undefined,
        sync_enabled: syncEnabled,
      });
      setUsername("");
      await refreshWithMessage("Midtown account updated.");
    } catch (saveError) {
      if (saveError instanceof ApiError || saveError instanceof Error) {
        setError(saveError.message);
      } else {
        setError("Unable to save retailer account.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  async function handleTestConnection(): Promise<void> {
    if (!account) {
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await apiClient.testRetailerAccount(account.id);
      await refreshWithMessage(
        response.run.status === "succeeded"
          ? "Midtown connection test succeeded."
          : "Midtown test completed but needs attention.",
      );
    } catch (testError) {
      if (testError instanceof ApiError || testError instanceof Error) {
        setError(testError.message);
      } else {
        setError("Unable to test Midtown connection.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  async function handleSyncNow(): Promise<void> {
    if (!account) {
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await apiClient.syncRetailerAccount(account.id, { limit_orders: 25 });
      await refreshWithMessage(
        response.run.status === "succeeded"
          ? `Midtown sync complete. Imported ${response.run.orders_seen} orders.`
          : "Midtown sync finished but needs attention.",
      );
    } catch (syncError) {
      if (syncError instanceof ApiError || syncError instanceof Error) {
        setError(syncError.message);
      } else {
        setError("Unable to sync Midtown account.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  async function handleCaptureMidtownOrder(): Promise<void> {
    if (!account) {
      return;
    }
    if (!midtownExtensionReady) {
      setError(
        midtownExtensionInstallUrl
          ? "Install the Midtown extension, then refresh Comicos so the capture button can connect."
          : "Set the Midtown extension install URL, then reload Comicos after installing the extension.",
      );
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    setShowAnotherMidtownPrompt(false);
    setLatestCompletedRetailerOrders([]);
    setLatestCompletedRun(null);
    setExtensionCaptureStatus((current) => ({
      ...current,
      midtownPageDetected: false,
      domReadSuccess: false,
      lastMessage: "Waiting for Midtown tab",
    }));
    try {
      const response = await apiClient.startRetailerLocalSync(account.id, { limit_orders: 1 });
      const session: LocalSyncSession = {
        accountId: account.id,
        syncRunId: response.run.id,
        captureToken: response.helper_token,
        captureTokenExpiresAt: response.helper_token_expires_at,
      };
      setLocalSyncSession(session);
      window.dispatchEvent(
        new CustomEvent(MIDTOWN_EXTENSION_CAPTURE_REQUEST_EVENT, {
          detail: {
            accountId: session.accountId,
            syncRunId: session.syncRunId,
            captureToken: session.captureToken,
            appOrigin: window.location.origin,
          },
        }),
      );
      await refreshWithMessage("Midtown capture started. The extension is reading the open Midtown order detail page.");
    } catch (startError) {
      setIsWorking(false);
      if (startError instanceof ApiError || startError instanceof Error) {
        setError(startError.message);
      } else {
        setError("Unable to start Midtown capture.");
      }
    }
  }

  async function handleImportAnotherMidtownOrder(): Promise<void> {
    setShowAnotherMidtownPrompt(false);
    await handleCaptureMidtownOrder();
  }

  async function handleDisconnect(): Promise<void> {
    if (!account) {
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.deleteRetailerAccount(account.id);
      setUsername("");
      setPassword("");
      setSyncEnabled(false);
      await refreshWithMessage("Midtown account removed. Add it again whenever you're ready.");
    } catch (disconnectError) {
      if (disconnectError instanceof ApiError || disconnectError instanceof Error) {
        setError(disconnectError.message);
      } else {
        setError("Unable to remove Midtown account.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  async function handleSyncToggle(nextEnabled: boolean): Promise<void> {
    setSyncEnabled(nextEnabled);
    if (!account) {
      return;
    }
    setIsWorking(true);
    setError(null);
    setSuccess(null);
    try {
      await apiClient.updateRetailerAccount(account.id, { sync_enabled: nextEnabled });
      await refreshWithMessage(nextEnabled ? "Retailer sync enabled." : "Retailer sync disabled.");
    } catch (toggleError) {
      setSyncEnabled(!nextEnabled);
      if (toggleError instanceof ApiError || toggleError instanceof Error) {
        setError(toggleError.message);
      } else {
        setError("Unable to update retailer sync setting.");
      }
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Settings"
        title="Connected Retailers"
        description="Connect a user-owned Midtown Comics account and open Midtown inside ComicOS to choose an order."
      />

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Midtown Comics</p>
            <h2 className="text-2xl font-semibold text-white">Open Midtown inside ComicOS</h2>
            <p className="max-w-2xl text-sm text-slate-300">
              ComicOS keeps your Midtown session, loads order history in-app, and lets you pick an
              order without leaving this workspace.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => navigate("/connected-retailers/midtown")}
              className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
            >
              Open Midtown Browser
            </button>
            <button
              type="button"
              onClick={() => navigate("/connected-retailers/midtown/orders")}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5"
            >
              View Midtown Orders
            </button>
          </div>
        </div>
      </section>

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
      {pendingMidtownCapture ? (
        <div className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <StatusBanner tone={pendingCaptureWarning ? "warning" : "info"} emphasis="prominent">
            {pendingCaptureWarning
              ? `This looks like a partial capture. ComicOS found ${pendingItemsDetected} possible items on this page. Scroll the Midtown order page fully, wait for all items to load, then try again.`
              : `ComicOS found ${pendingItemsDetected} possible items on this page. Review the capture details below before sending it to ComicOS.`}
          </StatusBanner>

          <div className="mt-5 grid gap-3 text-sm text-slate-200 sm:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Capture Debug</p>
              <dl className="mt-3 space-y-2 text-slate-300">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">current_url</dt>
                  <dd className="font-medium text-white break-all text-right">{pendingCaptureDiagnostics?.current_url ?? "unknown"}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">items_detected_client_side</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.items_detected_client_side ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">html_length</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.html_length ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">text_length</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.text_length ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">scroll_height</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.scroll_height ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">product_link_count</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.product_link_count ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">image_count</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.image_count ?? 0}</dd>
                </div>
              </dl>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Page Signals</p>
              <dl className="mt-3 space-y-2 text-slate-300">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">ready_state</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.ready_state ?? "unknown"}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">each_match_count</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.each_match_count ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">qty_match_count</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.qty_match_count ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">status_match_count</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.status_match_count ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">visible_order_item_block_count</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.visible_order_item_block_count ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">scroll_position</dt>
                  <dd className="font-medium text-white">{pendingCaptureDiagnostics?.scroll_position ?? 0}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void sendPendingMidtownCapture()}
              disabled={isWorking}
              className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Send Capture to ComicOS
            </button>
            <button
              type="button"
              onClick={discardPendingMidtownCapture}
              disabled={isWorking}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Discard Capture
            </button>
          </div>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <div className="flex flex-col gap-6 lg:flex-row lg:justify-between">
          <div className="space-y-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Midtown Comics</p>
              <h2 className="mt-1 text-2xl font-semibold text-white">Account Connection</h2>
            </div>
            {isLoading ? (
              <p className="text-sm text-slate-400">Loading retailer account status...</p>
            ) : (
              <div className="space-y-3 text-sm text-slate-300">
                <div className="flex flex-wrap gap-3">
                  <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(account?.status ?? "pending")}`}>
                    {account?.status ?? "Not connected"}
                  </span>
                  <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(runs[0]?.status ?? "pending")}`}>
                    {runs[0]?.status ?? "No sync run yet"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-3 text-xs font-semibold uppercase tracking-[0.16em]">
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 ${
                      extensionCaptureStatus.connected
                        ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
                        : "border-slate-600 bg-slate-900 text-slate-400"
                    }`}
                  >
                    Extension Connected
                  </span>
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 ${
                      extensionCaptureStatus.midtownPageDetected
                        ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-200"
                        : "border-slate-600 bg-slate-900 text-slate-400"
                    }`}
                  >
                    Midtown Page Detected
                  </span>
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 ${
                      extensionCaptureStatus.domReadSuccess
                        ? "border-violet-400/20 bg-violet-400/10 text-violet-200"
                        : "border-slate-600 bg-slate-900 text-slate-400"
                    }`}
                  >
                    DOM Read Success
                  </span>
                </div>
                {extensionCaptureStatus.lastMessage ? (
                  <p className="text-xs text-slate-400">{extensionCaptureStatus.lastMessage}</p>
                ) : null}
                <p>
                  Stored username: <span className="font-medium text-white">{account?.masked_username ?? "None"}</span>
                </p>
                <p>
                  Last sync: <span className="font-medium text-white">{formatDateTime(account?.last_sync_at)}</span>
                </p>
                <p>
                  Last success: <span className="font-medium text-white">{formatDateTime(account?.last_success_at)}</span>
                </p>
                {account?.last_error ? (
                  <div className="rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4 text-rose-100">
                    <p className="font-semibold">Last sync error</p>
                    <p className="mt-2 text-sm">{account.last_error}</p>
                    {needsAttention.actionRequired ? (
                      <p className="mt-3 text-sm text-rose-50">{needsAttention.actionRequired}</p>
                    ) : null}
                    {needsAttention.retryAllowedAt ? (
                      <p className="mt-2 text-sm text-rose-50">
                        Retry after: {formatDateTime(needsAttention.retryAllowedAt)}
                      </p>
                    ) : null}
                    {needsAttention.suggestedNextStep ? (
                      <p className="mt-2 text-sm text-rose-50">{needsAttention.suggestedNextStep}</p>
                    ) : null}
                  </div>
                ) : null}
                {needsAttention.challengeDetected ? (
                  <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-amber-100">
                    <p className="font-semibold">Midtown challenge handling</p>
                    <p className="mt-2 text-sm">
                      The app now keeps the account in <code>needs_attention</code> and uses a
                      safer retry path. Avoid repeated retries until the cooldown passes.
                    </p>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          <div className="w-full max-w-xl space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm text-slate-200">
                <span className="font-medium">Display name</span>
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none focus:border-cyan-400/60"
                />
              </label>
              <label className="space-y-2 text-sm text-slate-200">
                <span className="font-medium">Username or email</span>
                <input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder={account ? "Leave blank to keep current username" : "midtown username"}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none focus:border-cyan-400/60"
                />
              </label>
            </div>
            <label className="space-y-2 text-sm text-slate-200">
              <span className="font-medium">{account ? "Replace password" : "Password"}</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={account ? "Leave blank to keep current password" : "Midtown password"}
                className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none focus:border-cyan-400/60"
              />
            </label>
            <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-200">
              <input
                type="checkbox"
                checked={syncEnabled}
                disabled={isLoading || isWorking}
                onChange={(event) => void handleSyncToggle(event.target.checked)}
              />
              <span className="font-medium">Enable sync for this account</span>
            </label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                disabled={isLoading || isWorking}
                onClick={() => void handleSaveAccount()}
                className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isWorking ? "Working..." : account ? "Update Midtown Account" : "Connect Midtown"}
              </button>
              <button
                type="button"
                disabled={isLoading || isWorking || !account || retryBlocked}
                onClick={() => void handleTestConnection()}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {retryBlocked ? "Retry Later" : "Test Connection"}
              </button>
              <button
                type="button"
                disabled={isLoading || isWorking || !account || retryBlocked}
                onClick={() => void handleSyncNow()}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {retryBlocked ? "Sync Paused" : "Sync Now"}
              </button>
              <button
                type="button"
                disabled={isLoading || isWorking || !account || !midtownExtensionReady}
                onClick={() => void handleCaptureMidtownOrder()}
                className="rounded-2xl border border-cyan-400/30 px-5 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Capture Midtown Order
              </button>
              <button
                type="button"
                disabled={isLoading || isWorking || !account}
                onClick={() => void handleDisconnect()}
                className="rounded-2xl border border-rose-400/30 px-5 py-3 text-sm font-semibold text-rose-100 transition hover:bg-rose-400/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Remove Midtown and start over
              </button>
            </div>
            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-4 text-sm text-slate-200">
              <p className="font-semibold text-white">New here? Follow these 3 steps.</p>
              <p className="mt-2">
                Comicos uses a small Chrome extension to read the Midtown order detail page you
                already have open, then sends it back here for import.
              </p>
              <div className="mt-4 space-y-3">
                <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Step 1</p>
                  <p className="mt-1 font-semibold text-white">Install the Midtown extension</p>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    {midtownExtensionInstallUrl ? (
                      <a
                        href={midtownExtensionInstallUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex rounded-xl border border-cyan-300/40 px-4 py-2 font-semibold text-cyan-100 hover:bg-cyan-400/10"
                      >
                        Install Midtown Extension
                      </a>
                    ) : (
                      <button
                        type="button"
                        disabled
                        className="inline-flex cursor-not-allowed rounded-xl border border-slate-500/40 px-4 py-2 font-semibold text-slate-400 opacity-70"
                      >
                        Install Midtown Extension
                      </button>
                    )}
                    <p className="text-slate-300">
                      Install it once, then come back here and refresh Comicos.
                    </p>
                  </div>
                  {!midtownExtensionInstallUrl ? (
                    <p className="mt-3 rounded-xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-amber-100">
                      The store link is not configured yet. When Chrome review is approved, set{" "}
                      <code className="mx-1 rounded bg-black/20 px-1.5 py-0.5 text-xs">
                        VITE_MIDTOWN_EXTENSION_INSTALL_URL
                      </code>{" "}
                      in the frontend environment and redeploy so this button opens the Chrome Web Store page.
                    </p>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Step 2</p>
                  <p className="mt-1 font-semibold text-white">
                    Refresh Comicos until the extension is detected
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <span
                      className={`inline-flex rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${
                        midtownExtensionReady
                          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-100"
                          : "border-amber-400/30 bg-amber-400/10 text-amber-100"
                      }`}
                    >
                      {midtownExtensionReady ? "Extension connected" : "Extension not detected"}
                    </span>
                    <p className="text-slate-300">
                      {midtownExtensionReady
                        ? "You are ready to capture an order."
                        : "If this still says not detected, the extension is not installed in this browser yet."}
                    </p>
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Step 3</p>
                  <p className="mt-1 font-semibold text-white">
                    Open the Midtown order detail page and capture it
                  </p>
                  <p className="mt-2 text-slate-300">
                    Open the order you want to review, then click{" "}
                    <span className="font-medium text-white">Capture Midtown Order</span>. After
                    capture, review the retailer order directly in ComicOS.
                  </p>
                </div>
              </div>
              {localSyncSession ? (
                <p className="mt-3 text-cyan-100">
                  Waiting for Midtown capture. Capture token expires{" "}
                  {formatDateTime(localSyncSession.captureTokenExpiresAt)}.
                </p>
              ) : null}
              {showAnotherMidtownPrompt ? (
                <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                  <p className="text-sm text-slate-200">Capture another Midtown order?</p>
                  <div className="mt-3 flex flex-wrap gap-3">
                    <button
                      type="button"
                      disabled={isLoading || isWorking || !account}
                      onClick={() => void handleImportAnotherMidtownOrder()}
                      className="rounded-2xl bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Yes, capture another
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowAnotherMidtownPrompt(false)}
                      className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-white/5"
                    >
                      No, I&apos;m done
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      {latestCompletedRetailerOrder ? (
        <section className="mt-6 rounded-3xl border border-emerald-400/20 bg-emerald-400/10 p-6 text-slate-100 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-emerald-100/80">
                Retailer Order Captured
              </p>
              <p className="mt-1 text-lg font-semibold text-white">
                Order #{latestCompletedRetailerOrder.retailer_order_number}
              </p>
              <p className="mt-2 text-sm text-emerald-50/90">
                {latestCompletedRetailerOrder.item_count} item
                {latestCompletedRetailerOrder.item_count === 1 ? "" : "s"} ·{" "}
                {formatMoney(latestCompletedRetailerOrder.order_total)} ·{" "}
                {latestCompletedRetailerOrder.review_status}
              </p>
              {latestCompletedRun ? (
                <p className="mt-2 text-xs text-emerald-50/80">
                  Sync run #{latestCompletedRun.id} · Capture quality:{" "}
                  {readSummaryNumber(latestCompletedRetailerOrder.capture_quality_summary_json, "items_detected_client_side")} detected ·{" "}
                  {readSummaryNumber(latestCompletedRetailerOrder.capture_quality_summary_json, "parser_items_parsed")} parsed
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() =>
                  navigate(
                    latestCompletedRetailerOrderCount === 1
                      ? `/retailer-orders/${latestCompletedRetailerOrder.id}`
                      : `/retailer-orders${latestCompletedRun ? `?syncRunId=${latestCompletedRun.id}` : ""}`,
                  )
                }
                className="rounded-xl bg-white px-4 py-2 font-semibold text-slate-950 transition hover:bg-slate-100"
              >
                {latestCompletedRetailerOrderCount === 1
                  ? "Review Retailer Order"
                  : "Review Retailer Orders"}
              </button>
              <button
                type="button"
                onClick={() => void handleImportAnotherMidtownOrder()}
                disabled={isLoading || isWorking || !account}
                className="rounded-xl border border-emerald-200/30 px-4 py-2 font-semibold text-emerald-50 transition hover:bg-emerald-200/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Capture Another Midtown Order
              </button>
              <button
                type="button"
                onClick={() => navigate("/retailer-orders")}
                className="rounded-xl border border-white/10 px-4 py-2 font-semibold text-white transition hover:bg-white/5"
              >
                View All Retailer Orders
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <section className="mt-6 grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Recent Orders</p>
          <h2 className="mt-1 text-2xl font-semibold text-white">Synced Snapshot Orders</h2>
          <div className="mt-4 space-y-3">
            {visibleOrders.length === 0 ? (
              <p className="text-sm text-slate-400">No synced retailer orders yet.</p>
            ) : (
              visibleOrders.map((order) => (
                <article
                  key={order.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => openRetailerOrderReview(order)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openRetailerOrderReview(order);
                    }
                  }}
                  className="cursor-pointer rounded-2xl border border-white/10 bg-slate-950/50 p-4 transition hover:border-cyan-300/40 hover:bg-slate-950/70 focus:outline-none focus:ring-2 focus:ring-cyan-300/50"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">Order #{order.retailer_order_number}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {formatDateTime(order.order_date)} · {order.items.length} item{order.items.length === 1 ? "" : "s"}
                      </p>
                    </div>
                    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(order.order_status ?? "pending")}`}>
                      {order.order_status ?? "Unknown"}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    Total: <span className="font-medium text-white">{formatMoney(order.order_total)}</span>
                  </p>
                  <p className="mt-2 text-xs uppercase tracking-[0.16em] text-slate-500">
                    Review status: <span className="text-slate-200">{order.review_status}</span>
                  </p>
                  <p className="mt-2 text-sm text-slate-300">
                    {order.item_count} items · {order.cover_image_count} covers · {order.product_url_count} product links
                  </p>
                  <div className="mt-3 space-y-2 text-sm text-slate-300">
                    {(expandedOrderIds[order.id] ? order.items : order.items.slice(0, 3)).map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-4">
                        <span className="truncate">
                          {item.quantity} x {item.title}
                        </span>
                        <span className="shrink-0 text-slate-400">{formatMoney(item.unit_price)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        openRetailerOrderReview(order);
                      }}
                      className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 font-semibold text-cyan-100 transition hover:bg-cyan-400/20"
                    >
                      Review Order
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleOrderDetails(order.id);
                      }}
                      className="rounded-xl border border-white/10 px-4 py-2 font-semibold text-white transition hover:bg-white/5"
                    >
                      {expandedOrderIds[order.id] ? "Hide Details" : "View Details"}
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Sync History</p>
          <h2 className="mt-1 text-2xl font-semibold text-white">Recent Runs</h2>
          <div className="mt-4 space-y-3">
            {runs.length === 0 ? (
              <p className="text-sm text-slate-400">No sync runs yet.</p>
            ) : (
              runs.slice(0, 8).map((run) => (
                <article key={run.id} className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{formatDateTime(run.started_at)}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {run.orders_seen} orders · {run.items_seen} items
                      </p>
                    </div>
                    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(run.status)}`}>
                      {run.status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    Imported {run.orders_imported} orders, created {run.items_imported} items, updated {run.items_updated} items.
                  </p>
                  {run.error_message ? <p className="mt-2 text-sm text-rose-200">{run.error_message}</p> : null}
                  {run.summary_json["action_required"] ? (
                    <p className="mt-2 text-sm text-amber-100">
                      {String(run.summary_json["action_required"])}
                    </p>
                  ) : null}
                  {run.summary_json["retry_allowed_at"] ? (
                    <p className="mt-2 text-sm text-slate-300">
                      Retry after: {formatDateTime(String(run.summary_json["retry_allowed_at"]))}
                    </p>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
