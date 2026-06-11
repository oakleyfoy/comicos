import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MidtownBrowserOrdersResponse,
  type MidtownBrowserOrderRead,
  type MidtownBrowserSessionStatusRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const SECURITY_VERIFICATION_PATH = "/connected-retailers/midtown";

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
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

type LoadPhase = "security" | "signin" | "ready";

function classifyStatus(session: MidtownBrowserSessionStatusRead | null): LoadPhase {
  const status = (session?.status ?? "").toLowerCase();
  if (status === "security_verification_required") {
    return "security";
  }
  if (["login_required", "needs_attention", "failed", "error"].includes(status)) {
    return "signin";
  }
  return "ready";
}

function OrderCard({
  order,
  onSelect,
  isWorking,
}: {
  order: MidtownBrowserOrderRead;
  onSelect: (orderNumber: string) => void;
  isWorking: boolean;
}) {
  return (
    <article className="rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/10">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Midtown Order</p>
          <h3 className="mt-1 text-xl font-semibold text-white">Order #{order.retailer_order_number}</h3>
          <p className="mt-2 text-sm text-slate-300">
            {formatDate(order.order_date)} · {order.order_status ?? "Unknown status"}
          </p>
          <p className="mt-2 text-sm text-slate-300">
            {formatMoney(order.order_total)} · {order.item_count ?? 0} item
            {(order.item_count ?? 0) === 1 ? "" : "s"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onSelect(order.retailer_order_number)}
          disabled={isWorking}
          className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Select Order
        </button>
      </div>
    </article>
  );
}

export function MidtownBrowserOrdersPage() {
  const navigate = useNavigate();
  const [session, setSession] = useState<MidtownBrowserOrdersResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.goToMidtownBrowserOrders();
      setSession(response);
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 429) {
        setError("Midtown is busy completing a previous request. Wait a moment, then retry.");
      } else {
        setError(loadError instanceof Error ? loadError.message : "Unable to load Midtown orders.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  async function handleSelectOrder(orderNumber: string): Promise<void> {
    setIsWorking(true);
    setError(null);
    try {
      const response = await apiClient.captureMidtownBrowserOrder(orderNumber);
      navigate(`/retailer-orders/${response.order_id}`);
    } catch (selectError) {
      setError(selectError instanceof Error ? selectError.message : "Unable to capture the selected order.");
    } finally {
      setIsWorking(false);
    }
  }

  const browserSession = session?.session ?? null;
  const orders = session?.orders ?? [];
  const phase = classifyStatus(browserSession);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Connected Retailers"
        title="Choose an order to add to your inventory"
        description="ComicOS signs in to Midtown for you and lists your orders here. Pick one to capture and review."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {isLoading ? (
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <p className="text-sm text-slate-300">Signing in to Midtown and loading your order history...</p>
        </section>
      ) : phase === "security" ? (
        <section className="mt-6 rounded-3xl border border-amber-400/20 bg-amber-400/10 p-6 shadow-xl shadow-black/20">
          <p className="text-xs uppercase tracking-[0.16em] text-amber-200/80">Action needed</p>
          <h2 className="mt-1 text-2xl font-semibold text-white">Security verification required</h2>
          <p className="mt-3 max-w-2xl text-sm text-amber-50/90">
            Midtown asked for a one-time security check before ComicOS could load your orders. Complete the
            verification in the live browser, then come back and reload your orders.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => navigate(SECURITY_VERIFICATION_PATH)}
              className="rounded-2xl bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200"
            >
              Complete Security Verification
            </button>
            <button
              type="button"
              onClick={() => void loadOrders()}
              disabled={isWorking}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Retry Loading Orders
            </button>
          </div>
        </section>
      ) : phase === "signin" ? (
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <h2 className="text-2xl font-semibold text-white">ComicOS couldn't sign in to Midtown</h2>
          <p className="mt-3 max-w-2xl text-sm text-slate-300">
            {browserSession?.message ??
              "Check your stored Midtown username and password on the Connected Retailers page, then try again."}
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void loadOrders()}
              disabled={isWorking}
              className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Try Again
            </button>
            <button
              type="button"
              onClick={() => navigate("/connected-retailers")}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5"
            >
              Update Midtown Login
            </button>
            <button
              type="button"
              onClick={() => navigate(SECURITY_VERIFICATION_PATH)}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:bg-white/5"
            >
              Open Live Browser (Fallback)
            </button>
          </div>
        </section>
      ) : (
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <p className="text-sm text-slate-300">
                {browserSession?.authenticated ? "Signed in to Midtown." : "Midtown session ready."}
              </p>
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                {orders.length} order{orders.length === 1 ? "" : "s"} found
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void loadOrders()}
                disabled={isLoading || isWorking}
                className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Refresh Order History
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-4">
            {orders.length > 0 ? (
              orders.map((order) => (
                <OrderCard
                  key={order.retailer_order_number}
                  order={order}
                  onSelect={(orderNumber) => void handleSelectOrder(orderNumber)}
                  isWorking={isWorking}
                />
              ))
            ) : (
              <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/40 p-6 text-sm text-slate-300">
                No Midtown orders were found for this account.
              </div>
            )}
          </div>
        </section>
      )}
    </AppShell>
  );
}
