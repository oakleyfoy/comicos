import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceAccountConnectRequest,
  type MarketplaceAccountListResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { MarketplaceAccountListPanel } from "../components/marketplaces/MarketplaceAccountListPanel";
import { MarketplaceConnectionShell } from "../components/marketplaces/MarketplaceConnectionShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function MarketplaceAccountsPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [marketplaceData, setMarketplaceData] = useState<MarketplaceAccountListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyActionKey, setBusyActionKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  async function refresh(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [org, accounts] = await Promise.all([
        apiClient.getOrganization(parsedOrganizationId),
        apiClient.listMarketplaceAccounts(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setOrganization(org);
      setMarketplaceData(accounts);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace foundation.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect(payload: MarketplaceAccountConnectRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.connectMarketplaceAccount(parsedOrganizationId, payload);
      setMessage("Marketplace account connection state saved.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to connect marketplace account.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerify(accountId: number, verificationStatus: "verified" | "failed"): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    const actionKey = verificationStatus === "verified" ? `verify:${accountId}` : `fail:${accountId}`;
    setBusyActionKey(actionKey);
    setError(null);
    setMessage(null);
    try {
      await apiClient.verifyMarketplaceAccount(parsedOrganizationId, {
        account_id: accountId,
        verification_status: verificationStatus,
      });
      setMessage(
        verificationStatus === "verified"
          ? "Marketplace verification state updated to verified."
          : "Marketplace verification state updated to failed.",
      );
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to update marketplace verification status.");
    } finally {
      setBusyActionKey(null);
    }
  }

  async function handleDisconnect(accountId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyActionKey(`disconnect:${accountId}`);
    setError(null);
    setMessage(null);
    try {
      await apiClient.disconnectMarketplaceAccount(parsedOrganizationId, { account_id: accountId });
      setMessage("Marketplace account disconnected.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to disconnect marketplace account.");
    } finally {
      setBusyActionKey(null);
    }
  }

  const canView = marketplaceData?.permissions.can_view ?? (organization ? hasOrganizationPermission(organization, "organization:view") : false);
  const canManage =
    marketplaceData?.permissions.can_manage ?? (organization ? hasOrganizationPermission(organization, "organization:update") : false);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P43-01"
        title={organization ? `${organization.display_name} marketplaces` : "Marketplace accounts"}
        description="Organization-owned marketplace connectivity foundation with deterministic registry ordering, verification state tracking, and append-only connection lineage."
        actions={
          <div className="flex gap-2">
            <Link
              to={`/organizations/${parsedOrganizationId}`}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200"
            >
              Organization
            </Link>
            <Link
              to="/organizations"
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200"
            >
              All organizations
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
        <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 text-sm text-slate-300">Loading marketplace foundation...</section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Marketplace access denied"
            description="Organization marketplace visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && marketplaceData && canView ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <StatCard label="Registered accounts" value={String(marketplaceData.items.length)} />
            <StatCard
              label="Connected"
              value={String(marketplaceData.items.filter((account) => account.account_status === "connected").length)}
            />
            <StatCard
              label="Verified"
              value={String(marketplaceData.items.filter((account) => account.verification_status === "verified").length)}
            />
            <StatCard label="Registry entries" value={String(marketplaceData.registry.length)} />
          </section>
          {!canManage ? (
            <div className="mt-4">
              <StatusBanner tone="info">
                This organization can view marketplace ownership, but only members with `organization:update` can connect, verify, or disconnect accounts.
              </StatusBanner>
            </div>
          ) : null}
          <div className="mt-4 grid gap-4 xl:grid-cols-[0.92fr,1.08fr]">
            <MarketplaceConnectionShell
              registry={marketplaceData.registry}
              canManage={canManage}
              submitting={submitting}
              onConnect={handleConnect}
            />
            <MarketplaceAccountListPanel
              accounts={marketplaceData.items}
              registry={marketplaceData.registry}
              canManage={canManage}
              busyActionKey={busyActionKey}
              onVerify={handleVerify}
              onDisconnect={handleDisconnect}
            />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
