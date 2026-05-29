import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceAccountListResponse,
  type OrganizationResponse,
  type ShopifyProductMappingCreateRequest,
  type ShopifyProductMappingResponse,
  type ShopifyProductMappingUpdateRequest,
  type ShopifyStorefrontCreateRequest,
  type ShopifySyncOverviewResponse,
  type ShopifySyncSnapshotResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { ShopifyMappingEditorShell } from "../components/marketplaces/shopify/ShopifyMappingEditorShell";
import { ShopifyProductMappingTable } from "../components/marketplaces/shopify/ShopifyProductMappingTable";
import { ShopifyPublicationStatusBadge } from "../components/marketplaces/shopify/ShopifyPublicationStatusBadge";
import { ShopifyStorefrontForm } from "../components/marketplaces/shopify/ShopifyStorefrontForm";
import { ShopifyStorefrontProjectionViewer } from "../components/marketplaces/shopify/ShopifyStorefrontProjectionViewer";
import { ShopifyStorefrontTable } from "../components/marketplaces/shopify/ShopifyStorefrontTable";
import { ShopifySyncStateViewer } from "../components/marketplaces/shopify/ShopifySyncStateViewer";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ShopifySyncPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [accounts, setAccounts] = useState<MarketplaceAccountListResponse | null>(null);
  const [overview, setOverview] = useState<ShopifySyncOverviewResponse | null>(null);
  const [currentSnapshot, setCurrentSnapshot] = useState<ShopifySyncSnapshotResponse | null>(null);
  const [selectedStorefrontId, setSelectedStorefrontId] = useState<number | null>(null);
  const [selectedMappingId, setSelectedMappingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [storefrontSubmitting, setStorefrontSubmitting] = useState(false);
  const [mappingSubmitting, setMappingSubmitting] = useState(false);
  const [busyStorefrontId, setBusyStorefrontId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (overview?.storefronts.length) {
      if (selectedStorefrontId == null || !overview.storefronts.some((item) => item.id === selectedStorefrontId)) {
        setSelectedStorefrontId(overview.storefronts[0].id);
      }
    } else {
      setSelectedStorefrontId(null);
    }
  }, [overview, selectedStorefrontId]);

  useEffect(() => {
    setCurrentSnapshot(null);
  }, [selectedStorefrontId]);

  useEffect(() => {
    if (overview?.mappings.length) {
      if (selectedMappingId == null || !overview.mappings.some((item) => item.id === selectedMappingId)) {
        setSelectedMappingId(overview.mappings[0].id);
      }
    } else {
      setSelectedMappingId(null);
    }
  }, [overview, selectedMappingId]);

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
        setOverview(null);
        setCurrentSnapshot(null);
        return;
      }
      const [accountRows, shopifyOverview] = await Promise.all([
        apiClient.listMarketplaceAccounts(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.getShopifyOverview(parsedOrganizationId),
      ]);
      setAccounts(accountRows);
      setOverview(shopifyOverview);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load Shopify sync workspace.");
    } finally {
      setLoading(false);
    }
  }

  const selectedMapping = useMemo(
    () => overview?.mappings.find((item) => item.id === selectedMappingId) ?? null,
    [overview, selectedMappingId],
  );

  async function handleCreateStorefront(payload: ShopifyStorefrontCreateRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setStorefrontSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.createShopifyStorefront(parsedOrganizationId, payload);
      setSelectedStorefrontId(body.id);
      setCurrentSnapshot(null);
      setMessage("Shopify storefront registered.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create Shopify storefront.");
    } finally {
      setStorefrontSubmitting(false);
    }
  }

  async function handleCreateOrUpdateMapping(
    payload: ShopifyProductMappingCreateRequest | ShopifyProductMappingUpdateRequest,
  ): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setMappingSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      if (selectedMapping) {
        await apiClient.updateShopifyMapping(parsedOrganizationId, selectedMapping.id, payload as ShopifyProductMappingUpdateRequest);
        setMessage("Shopify mapping updated.");
      } else {
        await apiClient.createShopifyMapping(parsedOrganizationId, payload as ShopifyProductMappingCreateRequest);
        setMessage("Shopify mapping created.");
      }
      setCurrentSnapshot(null);
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to save Shopify mapping.");
    } finally {
      setMappingSubmitting(false);
    }
  }

  async function handleSnapshot(storefrontId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyStorefrontId(storefrontId);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.generateShopifySnapshot(parsedOrganizationId, { storefront_id: storefrontId });
      setCurrentSnapshot(body);
      setMessage("Shopify storefront snapshot generated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to generate Shopify snapshot.");
    } finally {
      setBusyStorefrontId(null);
    }
  }

  const canView = overview?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage = overview?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

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
        eyebrow="P43-08"
        title={organization ? `${organization.display_name} Shopify sync` : "Shopify sync"}
        description="Deterministic Shopify/storefront synchronization, product mapping, sync state tracking, and append-only sync lineage."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplaces`} className="rounded-2xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100">
              Accounts
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-listings`} className="rounded-2xl border border-fuchsia-400/30 px-4 py-2 text-sm font-semibold text-fuchsia-100">
              Listings
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-orders`} className="rounded-2xl border border-teal-400/30 px-4 py-2 text-sm font-semibold text-teal-100">
              Orders
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-pricing`} className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100">
              Pricing
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-events`} className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100">
              Events
            </Link>
            <Link to={`/organizations/${parsedOrganizationId}/marketplace-analytics`} className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100">
              Analytics
            </Link>
          </div>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {message ? (
        <div className="mt-4">
          <StatusBanner tone="success">{message}</StatusBanner>
        </div>
      ) : null}
      {loading ? (
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">
          Loading Shopify sync workspace...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Shopify sync access denied"
            description="Shopify synchronization visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <StatCard label="Storefronts" value={String(overview?.storefronts.length ?? 0)} />
            <StatCard label="Mappings" value={String(overview?.mappings.length ?? 0)} />
            <StatCard label="Sync states" value={String(overview?.sync_states.length ?? 0)} />
            <StatCard label="Managed" value={canManage ? "yes" : "view only"} />
          </section>

          {!canManage ? (
            <div className="mt-4">
              <StatusBanner tone="info">
                This organization can view Shopify synchronization state, but only members with `organization:update` can create storefronts, mappings, or snapshots.
              </StatusBanner>
            </div>
          ) : null}

          <section className="mt-6 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <ShopifyStorefrontForm accounts={accounts?.items ?? []} canManage={canManage} submitting={storefrontSubmitting} onSubmit={handleCreateStorefront} />
            <ShopifyStorefrontTable
              items={overview?.storefronts ?? []}
              selectedStorefrontId={selectedStorefrontId}
              canManage={canManage}
              busyStorefrontId={busyStorefrontId}
              onSelect={setSelectedStorefrontId}
              onSnapshot={handleSnapshot}
            />
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-200">Mapping editor shell</p>
                {selectedMapping ? (
                  <button
                    type="button"
                    onClick={() => setSelectedMappingId(null)}
                    className="rounded-2xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200"
                  >
                    Create new
                  </button>
                ) : null}
              </div>
              <ShopifyMappingEditorShell
                mapping={selectedMapping}
                canManage={canManage}
                submitting={mappingSubmitting}
                onSubmit={handleCreateOrUpdateMapping}
              />
            </div>
            <ShopifyProductMappingTable
              items={overview?.mappings ?? []}
              selectedMappingId={selectedMappingId}
              onSelect={setSelectedMappingId}
            />
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
            <ShopifySyncStateViewer items={overview?.sync_states ?? []} />
            <ShopifyStorefrontProjectionViewer projection={currentSnapshot?.projection_payload_json ?? null} />
          </section>

          {currentSnapshot ? (
            <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-400">
              Selected storefront #{currentSnapshot.storefront.id} generated a deterministic snapshot with {currentSnapshot.mappings.length} mapped items.
              <div className="mt-3 flex flex-wrap gap-2">
                <ShopifyPublicationStatusBadge status={currentSnapshot.storefront.storefront_status} />
                <ShopifyPublicationStatusBadge status={currentSnapshot.sync_state?.sync_status ?? "pending"} />
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
