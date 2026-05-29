import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceAccountListResponse,
  type MarketplaceOrderDetailResponse,
  type MarketplaceOrderResponse,
  type MarketplaceTransactionReconciliationReportResponse,
  type MarketplaceTransactionResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { MarketplaceOrderDetailPanel } from "../components/marketplaces/orders/MarketplaceOrderDetailPanel";
import { MarketplaceOrderImportSummaryPanel } from "../components/marketplaces/orders/MarketplaceOrderImportSummaryPanel";
import { MarketplaceOrderTable } from "../components/marketplaces/orders/MarketplaceOrderTable";
import { MarketplaceReconciliationReportViewer } from "../components/marketplaces/orders/MarketplaceReconciliationReportViewer";
import { MarketplaceTransactionTable } from "../components/marketplaces/orders/MarketplaceTransactionTable";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MarketplaceOrdersPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [accounts, setAccounts] = useState<MarketplaceAccountListResponse | null>(null);
  const [orders, setOrders] = useState<MarketplaceOrderResponse[]>([]);
  const [transactions, setTransactions] = useState<MarketplaceTransactionResponse[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [detail, setDetail] = useState<MarketplaceOrderDetailResponse | null>(null);
  const [report, setReport] = useState<MarketplaceTransactionReconciliationReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (selectedOrderId != null && Number.isFinite(parsedOrganizationId)) {
      void loadDetail(selectedOrderId);
    } else {
      setDetail(null);
    }
  }, [selectedOrderId, parsedOrganizationId]);

  async function refresh(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const org = await apiClient.getOrganization(parsedOrganizationId);
      setOrganization(org);
      if (!hasOrganizationPermission(org, "organization:view")) {
        setAccounts(null);
        setOrders([]);
        setTransactions([]);
        return;
      }
      const [accountRows, orderRows, transactionRows] = await Promise.all([
        apiClient.listMarketplaceAccounts(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplaceOrders(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplaceTransactions(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setAccounts(accountRows);
      setOrders(orderRows.items);
      setTransactions(transactionRows.items);
      if (orderRows.items.length === 0) {
        setSelectedOrderId(null);
      } else if (selectedOrderId == null || !orderRows.items.some((item) => item.id === selectedOrderId)) {
        setSelectedOrderId(orderRows.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace orders.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(orderId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    try {
      const body = await apiClient.getMarketplaceOrder(parsedOrganizationId, orderId);
      setDetail(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace order detail.");
    }
  }

  async function handleImport(payload: {
    marketplace_account_id: number;
    marketplace_order_identifier: string;
    buyer_identifier?: string | null;
    order_total: string;
    order_currency: string;
    ordered_at?: string | null;
    marketplace_listing_identifier: string;
    transaction_reference: string;
    fee_amount: string;
  }): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const grossAmount = Number(payload.order_total);
      const feeAmount = Number(payload.fee_amount);
      const netAmount = Math.max(grossAmount - feeAmount, 0).toFixed(2);
      const created = await apiClient.importMarketplaceOrder(parsedOrganizationId, {
        marketplace_account_id: payload.marketplace_account_id,
        marketplace_order_identifier: payload.marketplace_order_identifier,
        order_status: "imported",
        buyer_identifier: payload.buyer_identifier,
        order_total: payload.order_total,
        order_currency: payload.order_currency,
        ordered_at: payload.ordered_at ? new Date(payload.ordered_at).toISOString() : null,
        line_items: [
          {
            marketplace_listing_identifier: payload.marketplace_listing_identifier,
            quantity: 1,
            unit_price: payload.order_total,
            line_total: payload.order_total,
          },
        ],
        transactions: [
          {
            transaction_type: "sale",
            transaction_status: "completed",
            gross_amount: payload.order_total,
            fee_amount: payload.fee_amount,
            net_amount: netAmount,
            transaction_currency: payload.order_currency,
            transaction_reference: payload.transaction_reference,
          },
        ],
      });
      setDetail(created);
      setSelectedOrderId(created.order.id);
      setReport(null);
      setMessage(created.import_summary.duplicate_detected ? "Duplicate order replay processed idempotently." : "Marketplace order imported.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to import marketplace order.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReconcile(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.reconcileMarketplaceOrders(parsedOrganizationId, {});
      setReport(body);
      setMessage("Marketplace transaction reconciliation report generated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to reconcile marketplace transactions.");
    } finally {
      setBusy(false);
    }
  }

  const canView = organization ? hasOrganizationPermission(organization, "organization:view") : false;
  const canManage = organization ? hasOrganizationPermission(organization, "organization:update") : false;

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <p className="text-sm text-slate-400">Invalid organization id.</p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P43-04"
        title={organization ? `${organization.display_name} marketplace orders` : "Marketplace orders"}
        description="Deterministic order ingestion, transaction visibility, and replay-safe order lineage for organization-scoped marketplace sales foundations."
        actions={
          <div className="flex gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplaces`}
              className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100"
            >
              Accounts
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-listings`}
              className="rounded-2xl border border-fuchsia-400/30 px-4 py-2 text-sm font-semibold text-fuchsia-100"
            >
              Listings
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-sync`}
              className="rounded-2xl border border-amber-400/30 px-4 py-2 text-sm font-semibold text-amber-100"
            >
              Sync
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-pricing`}
              className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100"
            >
              Pricing
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-events`}
              className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100"
            >
              Events
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/live-sales`}
              className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100"
            >
              Live sales
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-ops`}
              className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100"
            >
              Ops dashboard
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-analytics`}
              className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100"
            >
              Analytics
            </Link>
          </div>
        }
      />
      {error ? <div className="mt-4"><StatusBanner tone="error">{error}</StatusBanner></div> : null}
      {message ? <div className="mt-4"><StatusBanner tone="success">{message}</StatusBanner></div> : null}
      {loading ? <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">Loading marketplace orders workspace...</section> : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Marketplace orders access denied"
            description="Marketplace order visibility is permission-aware and fail-closed."
          />
        </div>
      ) : null}
      {!loading && organization && canView ? (
        <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
          <section className="space-y-6">
            <MarketplaceOrderTable
              items={orders}
              selectedOrderId={selectedOrderId}
              loading={false}
              onSelect={setSelectedOrderId}
            />
            <MarketplaceTransactionTable items={detail?.transactions ?? transactions} />
          </section>
          <section className="space-y-6">
            <MarketplaceOrderImportSummaryPanel
              accounts={accounts?.items ?? []}
              canManage={canManage}
              submitting={submitting}
              detail={detail}
              onSubmit={handleImport}
            />
            <div className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
              <button
                type="button"
                disabled={busy || !canManage}
                onClick={() => void handleReconcile()}
                className="rounded-2xl border border-amber-400/30 px-4 py-2 text-sm font-semibold text-amber-100 disabled:opacity-50"
              >
                Generate reconciliation report
              </button>
            </div>
            <MarketplaceReconciliationReportViewer report={report} />
            <MarketplaceOrderDetailPanel detail={detail} />
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
