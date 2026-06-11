import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiClient, type MidtownBrowserSessionResponse } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value: string | null | undefined): string {
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

export function MidtownBrowserSessionPage() {
  const navigate = useNavigate();
  const [session, setSession] = useState<MidtownBrowserSessionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshSession(): Promise<void> {
    const response = await apiClient.getMidtownBrowserSessionStatus();
    setSession(response);
  }

  useEffect(() => {
    let cancelled = false;
    void refreshSession()
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load Midtown session.");
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

  async function handleStartSession(): Promise<void> {
    setIsWorking(true);
    setError(null);
    try {
      const response = await apiClient.startMidtownBrowserSession();
      setSession(response);
      navigate("/connected-retailers/midtown/orders");
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Unable to start Midtown session.");
    } finally {
      setIsWorking(false);
    }
  }

  const browserSession = session?.session ?? null;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Connected Retailers"
        title="Midtown Browser Session"
        description="ComicOS keeps a Midtown session for this connected account and loads your orders inside the app."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Midtown Comics</p>
            <h2 className="text-2xl font-semibold text-white">Login and load your orders in ComicOS</h2>
            <p className="max-w-2xl text-sm text-slate-300">
              ComicOS maintains your Midtown session for this account. Start the session, then open
              the order history page to choose an order to add to your inventory.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void handleStartSession()}
              disabled={isLoading || isWorking}
              className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isWorking ? "Starting..." : "Start Midtown Session"}
            </button>
            <button
              type="button"
              onClick={() => void refreshSession()}
              disabled={isLoading || isWorking}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Refresh Status
            </button>
            <button
              type="button"
              onClick={() => navigate("/connected-retailers")}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5"
            >
              Back to Connected Retailers
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Session Status</p>
            <p className="mt-2 text-lg font-semibold text-white">{browserSession?.status ?? "idle"}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Authenticated</p>
            <p className="mt-2 text-lg font-semibold text-white">
              {browserSession?.authenticated ? "Yes" : "No"}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Orders Loaded</p>
            <p className="mt-2 text-lg font-semibold text-white">
              {browserSession?.order_count ?? 0}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Last Updated</p>
            <p className="mt-2 text-sm font-semibold text-white">
              {formatDateTime(browserSession?.last_updated_at)}
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3 text-sm text-slate-300">
          <span className="inline-flex rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-emerald-100">
            Retailer website is the source of truth
          </span>
          <span className="inline-flex rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-cyan-100">
            Session persists across refreshes
          </span>
        </div>

        <div className="mt-6">
          <button
            type="button"
            onClick={() => navigate("/connected-retailers/midtown/orders")}
            disabled={isLoading || isWorking}
            className="rounded-2xl border border-cyan-400/30 px-5 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Open Order History
          </button>
        </div>
      </section>
    </AppShell>
  );
}
