import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiClient, type OrderListItem, type OrderQueryParams, type OrderSortBy } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const sortOptions: Array<{ label: string; value: OrderSortBy }> = [
  { label: "Order Date", value: "order_date" },
  { label: "Retailer", value: "retailer" },
  { label: "Order Total", value: "total_amount" },
  { label: "Created At", value: "created_at" },
];

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

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [retailer, setRetailer] = useState("");
  const [sortBy, setSortBy] = useState<OrderSortBy>("order_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const orderQuery = useMemo<OrderQueryParams>(
    () => ({
      page,
      page_size: pageSize,
      retailer: retailer || undefined,
      search: search || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
    }),
    [page, pageSize, retailer, search, sortBy, sortDir],
  );

  useEffect(() => {
    let ignore = false;

    async function loadOrders() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.getOrders(orderQuery);
        if (ignore) {
          return;
        }

        setOrders(response.items);
        setTotal(response.total);
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load orders.");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void loadOrders();

    return () => {
      ignore = true;
    };
  }, [orderQuery]);

  const isInitialLoad = isLoading && orders.length === 0 && total === 0;

  function applySearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  function resetPageAndRun(callback: () => void) {
    setPage(1);
    callback();
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Order History"
        title="Purchase Ledger"
        description="Review past acquisitions, allocation totals, and the purchase records backing your inventory."
        actions={
          <>
            <Link
              to="/orders/import"
              className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
            >
              Import Order
            </Link>
            <Link
              to="/orders/new"
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
            >
              Add Order
            </Link>
          </>
        }
      />

      {isInitialLoad ? (
        <div className="mt-6">
          <LoadingState
            title="Loading order history"
            description="Refreshing purchase rows, totals, and sorting controls."
          />
        </div>
      ) : (
        <>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-4">
            <form className="grid gap-3 lg:grid-cols-[2fr_1fr_1fr_1fr]" onSubmit={applySearch}>
              <input
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search by retailer, publisher, title, issue, or cover"
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
              />
              <input
                type="text"
                value={retailer}
                onChange={(event) =>
                  resetPageAndRun(() => {
                    setRetailer(event.target.value);
                  })
                }
                placeholder="Retailer"
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
              />
              <select
                value={sortBy}
                onChange={(event) =>
                  resetPageAndRun(() => {
                    setSortBy(event.target.value as OrderSortBy);
                  })
                }
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
              >
                {sortOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    Sort by {option.label}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                Search
              </button>
            </form>

            <div className="grid gap-3 md:grid-cols-2">
              <select
                value={sortDir}
                onChange={(event) =>
                  resetPageAndRun(() => {
                    setSortDir(event.target.value as "asc" | "desc");
                  })
                }
                className="w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
              >
                <option value="desc">Newest first</option>
                <option value="asc">Oldest first</option>
              </select>
              <button
                type="button"
                onClick={() => {
                  setPage(1);
                  setSearch("");
                  setSearchInput("");
                  setRetailer("");
                  setSortBy("order_date");
                  setSortDir("desc");
                }}
                className="rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
              >
                Reset filters
              </button>
            </div>
          </div>
      </section>

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 shadow-xl shadow-black/20">
          <div className="border-b border-white/10 px-5 py-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-white">Orders</h2>
                <p className="text-sm text-slate-600">
                  Page {page} of {pageCount} with {total} orders tracked
                </p>
              </div>
              {isLoading ? <p className="text-sm text-slate-600">Refreshing orders...</p> : null}
            </div>
          </div>

          {!orders.length ? (
            <div className="p-5">
              <EmptyState
                title="No orders yet"
                description="Your purchase ledger will appear here once you create the first manual order."
                action={
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Link
                      to="/orders/import"
                      className="rounded-2xl border border-white/10 px-4 py-3 text-center text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
                    >
                      Paste Receipt/Text
                    </Link>
                    <Link
                      to="/orders/new"
                      className="rounded-2xl bg-cyan-400 px-4 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
                    >
                      Add Order
                    </Link>
                  </div>
                }
              />
            </div>
          ) : (
            <>
          <div className="hidden overflow-x-auto xl:block">
            <table className="min-w-full text-left text-sm text-slate-300">
              <thead className="border-b border-white/10 text-xs uppercase tracking-[0.16em] text-slate-500">
                <tr>
                  <th className="px-4 py-3">Retailer</th>
                  <th className="px-4 py-3">Order Date</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Shipping</th>
                  <th className="px-4 py-3">Tax</th>
                  <th className="px-4 py-3">Total</th>
                  <th className="px-4 py-3">Items</th>
                  <th className="px-4 py-3">Copies</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.order_id} className="border-b border-slate-100">
                    <td className="px-4 py-3.5 font-medium text-white">{order.retailer}</td>
                    <td className="px-4 py-3.5">{formatDate(order.order_date)}</td>
                    <td className="px-4 py-3.5">{order.source_type ?? "Unspecified"}</td>
                    <td className="px-4 py-3.5">{formatCurrency(order.shipping_amount)}</td>
                    <td className="px-4 py-3.5">{formatCurrency(order.tax_amount)}</td>
                    <td className="px-4 py-3.5 font-medium text-cyan-200">
                      {formatCurrency(order.total_amount)}
                    </td>
                    <td className="px-4 py-3.5">{order.total_items}</td>
                    <td className="px-4 py-3.5">{order.total_copies}</td>
                    <td className="px-4 py-3.5">{formatTimestamp(order.created_at)}</td>
                    <td className="px-4 py-3.5">
                      <Link
                        to={`/orders/${order.order_id}`}
                        className="inline-flex rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200 transition hover:border-cyan-300/50 hover:bg-cyan-400/20"
                      >
                        View Order
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="space-y-4 p-5 xl:hidden">
            {orders.map((order) => (
              <Link
                key={order.order_id}
                to={`/orders/${order.order_id}`}
                className="block rounded-2xl border border-white/10 bg-slate-950/70 p-4 transition hover:border-cyan-300/40 hover:bg-slate-950"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-base font-semibold text-white">{order.retailer}</h3>
                    <p className="mt-1 text-sm text-slate-400">{formatDate(order.order_date)}</p>
                  </div>
                  <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-200">
                    {formatCurrency(order.total_amount)}
                  </span>
                </div>

                <div className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                  <div>
                    <p className="text-slate-500">Source</p>
                    <p>{order.source_type ?? "Unspecified"}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Items / Copies</p>
                    <p>
                      {order.total_items} items / {order.total_copies} copies
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Shipping</p>
                    <p>{formatCurrency(order.shipping_amount)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Tax</p>
                    <p>{formatCurrency(order.tax_amount)}</p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
            </>
          )}

          <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
            <button
              type="button"
              disabled={page === 1}
              onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-slate-600">
              Showing page {page} of {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount}
              onClick={() => setPage((currentPage) => Math.min(pageCount, currentPage + 1))}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
      </section>
        </>
      )}
    </AppShell>
  );
}
