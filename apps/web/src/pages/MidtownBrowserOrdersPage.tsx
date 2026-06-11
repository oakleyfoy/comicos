import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  apiClient,
  type MidtownBrowserOrdersResponse,
  type MidtownBrowserOrderRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

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

  async function loadOrders(): Promise<void> {
    const response = await apiClient.goToMidtownBrowserOrders();
    setSession(response);
  }

  useEffect(() => {
    let cancelled = false;
    void loadOrders()
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load Midtown orders.");
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

  return (
    <AppShell>
      <PageHeader
        eyebrow="Connected Retailers"
        title="Choose an order to add to your inventory"
        description="Pick the Midtown order you want ComicOS to capture and review."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <p className="text-sm text-slate-300">
              {browserSession?.authenticated ? "Signed in and ready." : "Preparing the Midtown session..."}
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
            <button
              type="button"
              onClick={() => navigate("/connected-retailers/midtown")}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5"
            >
              Back to Session
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-4">
          {isLoading ? (
            <p className="text-sm text-slate-400">Loading Midtown orders...</p>
          ) : orders.length > 0 ? (
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
              No Midtown orders were found for this session.
            </div>
          )}
        </div>
      </section>
    </AppShell>
  );
}
