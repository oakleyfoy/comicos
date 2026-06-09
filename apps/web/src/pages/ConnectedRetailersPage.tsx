import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type RetailerAccountRead,
  type RetailerOrderSnapshotRead,
  type RetailerSyncRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";


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


export function ConnectedRetailersPage() {
  const [accounts, setAccounts] = useState<RetailerAccountRead[]>([]);
  const [orders, setOrders] = useState<RetailerOrderSnapshotRead[]>([]);
  const [runs, setRuns] = useState<RetailerSyncRunRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("Midtown Comics");
  const [syncEnabled, setSyncEnabled] = useState(false);

  const account = accounts[0] ?? null;

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

  const visibleOrders = useMemo(
    () => orders.filter((row) => !account || row.retailer_account_id === account.id).slice(0, 8),
    [account, orders],
  );

  async function refreshWithMessage(message?: string): Promise<void> {
    await loadPage();
    setPassword("");
    if (message) {
      setSuccess(message);
    }
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
      await refreshWithMessage("Midtown account disconnected.");
    } catch (disconnectError) {
      if (disconnectError instanceof ApiError || disconnectError instanceof Error) {
        setError(disconnectError.message);
      } else {
        setError("Unable to disconnect Midtown account.");
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
        description="Connect a user-owned Midtown Comics account, test credentials, and run bounded inline syncs that enrich draft imports with exact retailer order data."
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
                disabled={isLoading || isWorking || !account}
                onClick={() => void handleTestConnection()}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Test Connection
              </button>
              <button
                type="button"
                disabled={isLoading || isWorking || !account}
                onClick={() => void handleSyncNow()}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Sync Now
              </button>
              <button
                type="button"
                disabled={isLoading || isWorking || !account}
                onClick={() => void handleDisconnect()}
                className="rounded-2xl border border-rose-400/30 px-5 py-3 text-sm font-semibold text-rose-100 transition hover:bg-rose-400/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Disconnect
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Recent Orders</p>
          <h2 className="mt-1 text-2xl font-semibold text-white">Synced Snapshot Orders</h2>
          <div className="mt-4 space-y-3">
            {visibleOrders.length === 0 ? (
              <p className="text-sm text-slate-400">No synced retailer orders yet.</p>
            ) : (
              visibleOrders.map((order) => (
                <article key={order.id} className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
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
                  <p className="mt-3 text-sm text-slate-300">Total: <span className="font-medium text-white">{formatMoney(order.order_total)}</span></p>
                  <div className="mt-3 space-y-2 text-sm text-slate-300">
                    {order.items.slice(0, 3).map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-4">
                        <span className="truncate">{item.quantity} x {item.title}</span>
                        <span className="shrink-0 text-slate-400">{formatMoney(item.unit_price)}</span>
                      </div>
                    ))}
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
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
