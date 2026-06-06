import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient, type OrderDetail } from "../api/client";
import { AppShell } from "../components/AppShell";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatCurrency(value: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(value));
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

function variantLabel(item: OrderDetail["items"][number]): string {
  return [item.cover_name, item.printing, item.ratio, item.variant_type]
    .filter(Boolean)
    .join(" / ");
}

export function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const parsedOrderId = Number(orderId);

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function loadOrder() {
      setIsLoading(true);
      setError(null);

      if (!Number.isInteger(parsedOrderId) || parsedOrderId <= 0) {
        setError("Invalid order id.");
        setIsLoading(false);
        return;
      }

      try {
        const response = await apiClient.getOrder(parsedOrderId);
        if (!ignore) {
          setOrder(response);
        }
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load order.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void loadOrder();

    return () => {
      ignore = true;
    };
  }, [parsedOrderId]);

  if (isLoading) {
    return (
      <AppShell>
        <LoadingState
          title="Loading order detail"
          description="Refreshing order totals, allocation breakdowns, and linked inventory copies."
        />
      </AppShell>
    );
  }

  if (error && !order) {
    return (
      <AppShell>
        <div className="max-w-4xl">
          <Link
            to="/orders"
            className="inline-flex rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
          >
            Back to Orders
          </Link>
          <div className="mt-6">
            <StatusBanner tone="error">{error}</StatusBanner>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!order) {
    return null;
  }

  const totalCopies = order.items.reduce((sum, item) => sum + item.quantity, 0);

  const metrics = [
    { label: "Order Total", value: formatCurrency(order.total_amount) },
    { label: "Shipping", value: formatCurrency(order.shipping_amount) },
    { label: "Tax", value: formatCurrency(order.tax_amount) },
    { label: "Copies", value: String(totalCopies) },
  ];

  return (
    <AppShell>
      <PageHeader
        eyebrow="Order Detail"
        title={order.retailer}
        description={`Review item allocations, linked inventory copies, and recorded totals for order #${order.order_id}.`}
        actions={
          <>
            <Link
              to="/orders"
              className="inline-flex rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-cyan-300/40 hover:bg-white/5"
            >
              Back to Orders
            </Link>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              Order <span className="font-medium text-slate-900">#{order.order_id}</span>
            </div>
          </>
        }
      />

        <section className="mt-6 rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-indigo-950/70 p-6 shadow-2xl shadow-cyan-950/20">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-4">
              <span className="inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">
                Order Detail
              </span>
              <div>
                <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  {order.retailer}
                </h1>
                <p className="mt-2 text-sm text-slate-300 sm:text-base">
                  Order date {formatDate(order.order_date)} | Source {order.source_type ?? "Unspecified"}
                </p>
              </div>
              <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Created</p>
                  <p className="mt-2 font-medium text-white">{formatTimestamp(order.created_at)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Line Items</p>
                  <p className="mt-2 font-medium text-white">{order.items.length}</p>
                </div>
              </div>
            </div>

            <div className="grid w-full gap-3 sm:grid-cols-2 lg:max-w-xl">
              {metrics.map((metric) => (
                <article
                  key={metric.label}
                  className="rounded-2xl border border-white/10 bg-slate-900/80 p-4"
                >
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{metric.label}</p>
                  <p className="mt-3 text-2xl font-semibold text-white">{metric.value}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 shadow-xl shadow-black/20">
          <div className="border-b border-white/10 px-5 py-4">
            <h2 className="text-xl font-semibold text-white">Item Breakdown</h2>
            <p className="mt-2 text-sm text-slate-400">
              Review raw prices, allocation math, and linked inventory copies for this purchase.
            </p>
          </div>

          <div className="space-y-5 p-5">
            {order.items.map((item) => (
              <article
                key={item.order_item_id}
                className="rounded-2xl border border-white/10 bg-slate-950/70 p-5"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">
                      {item.title} #{item.issue_number}
                    </h3>
                    <p className="mt-1 text-sm text-slate-400">{item.publisher}</p>
                    <p className="mt-2 text-sm text-slate-300">
                      {variantLabel(item) || "Standard cover"}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {item.cover_artist ? `Cover art by ${item.cover_artist}` : "Cover artist unspecified"}
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[24rem]">
                    <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Quantity</p>
                      <p className="mt-2 text-lg font-semibold text-white">{item.quantity}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Unit Cost</p>
                      <p className="mt-2 text-lg font-semibold text-cyan-200">
                        {formatCurrency(item.all_in_unit_cost)}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-5 grid gap-4 text-sm text-slate-300 md:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <p className="text-slate-500">Raw Item Price</p>
                    <p className="mt-1">{formatCurrency(item.raw_item_price)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Allocated Shipping</p>
                    <p className="mt-1">{formatCurrency(item.allocated_shipping)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Allocated Tax</p>
                    <p className="mt-1">{formatCurrency(item.allocated_tax)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">All-In Unit Cost</p>
                    <p className="mt-1">{formatCurrency(item.all_in_unit_cost)}</p>
                  </div>
                </div>

                <div className="mt-5">
                  <p className="text-sm text-slate-500">Linked Inventory Items</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.inventory_copy_ids.map((inventoryCopyId) => (
                      <Link
                        key={inventoryCopyId}
                        to={`/inventory/${inventoryCopyId}`}
                        className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:border-cyan-300/50 hover:bg-cyan-400/20"
                      >
                        Inventory #{inventoryCopyId}
                      </Link>
                    ))}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
    </AppShell>
  );
}
