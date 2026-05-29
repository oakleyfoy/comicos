import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ConventionSessionListResponse,
  type MobileDeviceListResponse,
  type OrganizationResponse,
  type QuickSaleDetailResponse,
  type QuickSaleListResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { QuickSaleCreateForm } from "../components/mobile/quick-sales/QuickSaleCreateForm";
import { QuickSaleDetailPanel } from "../components/mobile/quick-sales/QuickSaleDetailPanel";
import { QuickSaleEventTimeline } from "../components/mobile/quick-sales/QuickSaleEventTimeline";
import { QuickSaleListPanel } from "../components/mobile/quick-sales/QuickSaleListPanel";
import { QuickSaleSummaryCards } from "../components/mobile/quick-sales/QuickSaleSummaryCards";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function QuickSalesPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [sales, setSales] = useState<QuickSaleListResponse | null>(null);
  const [devices, setDevices] = useState<MobileDeviceListResponse | null>(null);
  const [sessions, setSessions] = useState<ConventionSessionListResponse | null>(null);
  const [selectedSaleId, setSelectedSaleId] = useState<number | null>(null);
  const [selectedSale, setSelectedSale] = useState<QuickSaleDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [saleIdentifier, setSaleIdentifier] = useState("qs-001");
  const [buyerLabel, setBuyerLabel] = useState("");
  const [saleSource, setSaleSource] = useState("convention");
  const [deviceId, setDeviceId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [inventoryItemId, setInventoryItemId] = useState("");
  const [unitPrice, setUnitPrice] = useState("0.00");
  const [discountAmount, setDiscountAmount] = useState("0.00");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [paymentAmount, setPaymentAmount] = useState("0.00");

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (selectedSaleId && Number.isFinite(parsedOrganizationId)) {
      void refreshSelectedSale(selectedSaleId);
    }
  }, [selectedSaleId]);

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
        setSales(null);
        setSelectedSale(null);
        return;
      }
      const [saleList, deviceList, sessionList] = await Promise.all([
        apiClient.listQuickSales(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMobileDevices(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listConventionSessions(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setSales(saleList);
      setDevices(deviceList);
      setSessions(sessionList);
      if (saleList.items.length > 0) {
        setSelectedSaleId((current) => current ?? saleList.items[0].id);
      } else {
        setSelectedSaleId(null);
        setSelectedSale(null);
      }
      if (deviceList.items.length > 0 && deviceId === null) {
        setDeviceId(deviceList.items[0].id);
      }
      if (sessionList.items.length > 0 && sessionId === null) {
        setSessionId(sessionList.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load quick sales.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshSelectedSale(saleId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    try {
      const detail = await apiClient.getQuickSale(parsedOrganizationId, saleId);
      setSelectedSale(detail);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load quick sale detail.");
    }
  }

  const canView =
    sales?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage =
    sales?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

  async function handleCreateSale(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !saleIdentifier.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const detail = await apiClient.createQuickSale(parsedOrganizationId, {
        sale_identifier: saleIdentifier.trim(),
        buyer_label: buyerLabel.trim() || null,
        sale_source: saleSource,
        currency: "USD",
        convention_session_id: saleSource === "convention" ? sessionId : null,
        mobile_device_id: saleSource === "mobile" || saleSource === "offline" ? deviceId : null,
      });
      setSelectedSaleId(detail.sale.id);
      setSelectedSale(detail);
      setMessage("Quick sale created.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create quick sale.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAddLineItem(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !selectedSale || !inventoryItemId.trim() || !unitPrice.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      const detail = await apiClient.addQuickSaleLineItem(parsedOrganizationId, selectedSale.sale.id, {
        inventory_item_id: Number(inventoryItemId),
        quantity: 1,
        unit_price: unitPrice,
        discount_amount: discountAmount || "0.00",
      });
      setSelectedSale(detail);
      setMessage("Line item added.");
      setInventoryItemId("");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to add line item.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemoveLineItem(lineItemId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !selectedSale) {
      return;
    }
    setSubmitting(true);
    try {
      const detail = await apiClient.updateQuickSaleLineItem(parsedOrganizationId, selectedSale.sale.id, lineItemId, {
        line_status: "removed",
      });
      setSelectedSale(detail);
      setMessage("Line item removed.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to remove line item.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRecordPayment(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !selectedSale || !paymentAmount.trim()) {
      return;
    }
    setSubmitting(true);
    try {
      const detail = await apiClient.recordQuickSalePayment(parsedOrganizationId, selectedSale.sale.id, {
        payment_method: paymentMethod,
        amount: paymentAmount,
        currency: "USD",
      });
      setSelectedSale(detail);
      setMessage("Payment recorded.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to record payment.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCompleteSale(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !selectedSale) {
      return;
    }
    setSubmitting(true);
    try {
      const detail = await apiClient.completeQuickSale(parsedOrganizationId, selectedSale.sale.id);
      setSelectedSale(detail);
      setMessage("Quick sale completed.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to complete sale.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVoidSale(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || !selectedSale) {
      return;
    }
    setSubmitting(true);
    try {
      const detail = await apiClient.voidQuickSale(parsedOrganizationId, selectedSale.sale.id);
      setSelectedSale(detail);
      setMessage("Quick sale voided.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to void sale.");
    } finally {
      setSubmitting(false);
    }
  }

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
        eyebrow="P44-05"
        title={organization ? `${organization.display_name} quick sales` : "Quick sales"}
        description="Internal dealer sale capture, line items, payment recording, totals, and offline-ready sale lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}/mobile-ops`} className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100">
              Mobile ops
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/convention-mode`} className="rounded-2xl border border-orange-400/30 px-4 py-2 text-sm font-semibold text-orange-100">
              Convention mode
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-scanning`} className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100">
              Mobile scanning
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/mobile-analytics`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Mobile analytics
            </Link>
          </div>
        }
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {message ? (
        <div className="mt-6">
          <StatusBanner tone="success">{message}</StatusBanner>
        </div>
      ) : null}

      {loading ? <p className="mt-8 text-sm text-slate-400">Loading quick sales…</p> : null}

      {!loading && organization && !canView ? (
        <OrganizationAccessDeniedState
          title="Quick sales access denied"
          description="You need organization view permission to inspect dealer transactions."
        />
      ) : null}

      {!loading && canView ? (
        <div className="mt-8 space-y-10">
          <QuickSaleSummaryCards sales={sales?.items ?? []} />

          {canManage ? (
            <section>
              <h2 className="text-lg font-semibold text-white">Create quick sale</h2>
              <div className="mt-4">
                <QuickSaleCreateForm
                  saleIdentifier={saleIdentifier}
                  buyerLabel={buyerLabel}
                  saleSource={saleSource}
                  deviceId={deviceId}
                  sessionId={sessionId}
                  devices={devices?.items ?? []}
                  sessions={sessions?.items ?? []}
                  submitting={submitting}
                  onSaleIdentifierChange={setSaleIdentifier}
                  onBuyerLabelChange={setBuyerLabel}
                  onSaleSourceChange={setSaleSource}
                  onDeviceIdChange={setDeviceId}
                  onSessionIdChange={setSessionId}
                  onSubmit={() => void handleCreateSale()}
                />
              </div>
            </section>
          ) : null}

          <section className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
            <div>
              <h2 className="text-lg font-semibold text-white">Sale list</h2>
              <div className="mt-4">
                <QuickSaleListPanel
                  items={sales?.items ?? []}
                  selectedSaleId={selectedSaleId}
                  onSelect={setSelectedSaleId}
                />
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Sale detail</h2>
              <div className="mt-4">
                <QuickSaleDetailPanel
                  detail={selectedSale}
                  canManage={canManage}
                  submitting={submitting}
                  inventoryItemId={inventoryItemId}
                  unitPrice={unitPrice}
                  discountAmount={discountAmount}
                  paymentMethod={paymentMethod}
                  paymentAmount={paymentAmount}
                  onInventoryItemIdChange={setInventoryItemId}
                  onUnitPriceChange={setUnitPrice}
                  onDiscountAmountChange={setDiscountAmount}
                  onPaymentMethodChange={setPaymentMethod}
                  onPaymentAmountChange={setPaymentAmount}
                  onAddLineItem={() => void handleAddLineItem()}
                  onRemoveLineItem={(lineItemId) => void handleRemoveLineItem(lineItemId)}
                  onRecordPayment={() => void handleRecordPayment()}
                  onComplete={() => void handleCompleteSale()}
                  onVoid={() => void handleVoidSale()}
                />
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white">Quick sale event timeline</h2>
            <div className="mt-4">
              <QuickSaleEventTimeline events={selectedSale?.events ?? []} />
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
