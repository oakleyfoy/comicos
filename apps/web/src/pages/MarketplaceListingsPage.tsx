import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceAccountListResponse,
  type MarketplaceListingDraftCreateRequest,
  type MarketplaceListingDraftDetailResponse,
  type MarketplaceListingDraftResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { MarketplaceListingDetailPanel } from "../components/marketplaces/listings/MarketplaceListingDetailPanel";
import { MarketplaceListingDraftForm } from "../components/marketplaces/listings/MarketplaceListingDraftForm";
import { MarketplaceListingDraftTable } from "../components/marketplaces/listings/MarketplaceListingDraftTable";
import { MarketplaceListingProjectionPreview } from "../components/marketplaces/listings/MarketplaceListingProjectionPreview";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function MarketplaceListingsPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [accounts, setAccounts] = useState<MarketplaceAccountListResponse | null>(null);
  const [listings, setListings] = useState<MarketplaceListingDraftResponse[]>([]);
  const [selectedListingId, setSelectedListingId] = useState<number | null>(null);
  const [detail, setDetail] = useState<MarketplaceListingDraftDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyAction, setBusyAction] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (selectedListingId != null && Number.isFinite(parsedOrganizationId)) {
      void loadDetail(selectedListingId);
    } else {
      setDetail(null);
    }
  }, [selectedListingId, parsedOrganizationId]);

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
        setListings([]);
        return;
      }
      const [accountRows, listingRows] = await Promise.all([
        apiClient.listMarketplaceAccounts(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplaceListings(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setAccounts(accountRows);
      setListings(listingRows.items);
      if (listingRows.items.length && selectedListingId == null) {
        setSelectedListingId(listingRows.items[0].id);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace listings.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(listingId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    try {
      const body = await apiClient.getMarketplaceListing(parsedOrganizationId, listingId);
      setDetail(body);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load listing detail.");
    }
  }

  async function handleCreate(payload: MarketplaceListingDraftCreateRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const created = await apiClient.createMarketplaceListing(parsedOrganizationId, payload);
      setMessage("Listing draft created.");
      setSelectedListingId(created.draft.id);
      await refresh();
      setDetail(created);
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to create listing draft.");
    } finally {
      setSubmitting(false);
    }
  }

  async function runListingAction(action: () => Promise<MarketplaceListingDraftDetailResponse>): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId) || selectedListingId == null) {
      return;
    }
    setBusyAction(true);
    setError(null);
    setMessage(null);
    try {
      const body = await action();
      setDetail(body);
      setMessage("Listing state updated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Listing action failed.");
      await loadDetail(selectedListingId);
    } finally {
      setBusyAction(false);
    }
  }

  const canManage = organization ? hasOrganizationPermission(organization, "organization:update") : false;

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <p className="text-sm text-slate-600">Invalid organization id.</p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P43-02"
        title="Marketplace listings"
        description="Organization-scoped listing drafts, deterministic marketplace payload projections, and append-only listing lineage."
        actions={
          <div className="flex gap-2">
            <Link to={`/organizations/${parsedOrganizationId}`} className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200">
              Organization home
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-sync`}
              className="rounded-2xl border border-amber-400/30 px-4 py-2 text-sm font-semibold text-amber-100"
            >
              Sync workspace
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/shopify`}
              className="rounded-2xl border border-sky-400/30 px-4 py-2 text-sm font-semibold text-sky-100"
            >
              Shopify sync
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
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-orders`}
              className="rounded-2xl border border-teal-400/30 px-4 py-2 text-sm font-semibold text-teal-100"
            >
              Orders workspace
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-pricing`}
              className="rounded-2xl border border-violet-400/30 px-4 py-2 text-sm font-semibold text-violet-100"
            >
              Pricing workspace
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/marketplace-events`}
              className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100"
            >
              Events workspace
            </Link>
            <Link
              to={`/organizations/${parsedOrganizationId}/live-sales`}
              className="rounded-2xl border border-rose-400/30 px-4 py-2 text-sm font-semibold text-rose-100"
            >
              Live sales
            </Link>
          </div>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading marketplace listing workspace…</p> : null}
      {!loading && organization && !hasOrganizationPermission(organization, "organization:view") ? (
        <OrganizationAccessDeniedState title="Access denied" description="Marketplace listing visibility requires organization access." />
      ) : null}
      {!loading && organization && hasOrganizationPermission(organization, "organization:view") ? (
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <section className="space-y-4">
            <MarketplaceListingDraftTable
              organizationId={parsedOrganizationId}
              items={listings}
              selectedListingId={selectedListingId}
              onSelect={setSelectedListingId}
              loading={false}
            />
            {canManage ? (
              <MarketplaceListingDraftForm
                accounts={accounts?.items ?? []}
                submitting={submitting}
                onSubmit={handleCreate}
              />
            ) : null}
          </section>
          <section className="space-y-4">
            <MarketplaceListingDetailPanel
              detail={detail}
              busy={busyAction}
              canManage={canManage}
              onMarkReady={() =>
                void runListingAction(() =>
                  apiClient.updateMarketplaceListing(parsedOrganizationId, selectedListingId as number, { listing_status: "ready" }),
                )
              }
              onGenerateProjection={() =>
                void runListingAction(() =>
                  apiClient.generateMarketplaceListingProjection(parsedOrganizationId, selectedListingId as number),
                )
              }
              onArchive={() =>
                void runListingAction(() => apiClient.archiveMarketplaceListing(parsedOrganizationId, selectedListingId as number))
              }
            />
            <MarketplaceListingProjectionPreview projections={detail?.projections ?? []} />
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
