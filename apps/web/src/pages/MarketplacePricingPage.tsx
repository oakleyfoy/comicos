import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MarketplaceAccountListResponse,
  type MarketplaceListingDraftResponse,
  type MarketplaceOfferListResponse,
  type MarketplacePriceRecommendationListResponse,
  type OrganizationResponse,
  type MarketplacePricingRuleCreateRequest,
  type MarketplacePricingRuleUpdateRequest,
  type MarketplacePriceRecommendationGenerateRequest,
  type MarketplacePriceRecommendationReviewRequest,
  type MarketplaceOfferStatusUpdateRequest,
  type MarketplacePricingRuleResponse,
  type MarketplacePricingRuleListResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { MarketplaceOfferSummaryPanel } from "../components/marketplaces/pricing/MarketplaceOfferSummaryPanel";
import { MarketplaceOfferTable } from "../components/marketplaces/pricing/MarketplaceOfferTable";
import { MarketplacePriceRecommendationGeneratorShell } from "../components/marketplaces/pricing/MarketplacePriceRecommendationGeneratorShell";
import { MarketplacePriceRecommendationTable } from "../components/marketplaces/pricing/MarketplacePriceRecommendationTable";
import { MarketplacePricingRuleEditorShell } from "../components/marketplaces/pricing/MarketplacePricingRuleEditorShell";
import { MarketplacePricingRuleList } from "../components/marketplaces/pricing/MarketplacePricingRuleList";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function MarketplacePricingPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [accounts, setAccounts] = useState<MarketplaceAccountListResponse | null>(null);
  const [listings, setListings] = useState<MarketplaceListingDraftResponse[]>([]);
  const [recommendations, setRecommendations] = useState<MarketplacePriceRecommendationListResponse | null>(null);
  const [offers, setOffers] = useState<MarketplaceOfferListResponse | null>(null);
  const [rules, setRules] = useState<MarketplacePricingRuleListResponse | null>(null);
  const [selectedRule, setSelectedRule] = useState<MarketplacePricingRuleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyRecommendationId, setBusyRecommendationId] = useState<number | null>(null);
  const [busyOfferId, setBusyOfferId] = useState<number | null>(null);
  const [busyRuleId, setBusyRuleId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (rules?.items.length && selectedRule == null) {
      setSelectedRule(rules.items[0]);
    }
    if (rules && selectedRule && !rules.items.some((item) => item.id === selectedRule.id)) {
      setSelectedRule(rules.items[0] ?? null);
    }
  }, [rules, selectedRule]);

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
        setRecommendations(null);
        setOffers(null);
        setRules(null);
        return;
      }
      const [accountRows, listingRows, recommendationRows, offerRows, ruleRows] = await Promise.all([
        apiClient.listMarketplaceAccounts(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplaceListings(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplacePricingRecommendations(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplacePricingOffers(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listMarketplacePricingRules(parsedOrganizationId, { limit: 100, offset: 0 }),
      ]);
      setAccounts(accountRows);
      setListings(listingRows.items);
      setRecommendations(recommendationRows);
      setOffers(offerRows);
      setRules(ruleRows);
      if (ruleRows.items.length > 0) {
        const refreshedSelectedRule = selectedRule ? ruleRows.items.find((item) => item.id === selectedRule.id) ?? null : null;
        setSelectedRule(refreshedSelectedRule ?? ruleRows.items[0]);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load marketplace pricing workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateRecommendation(payload: MarketplacePriceRecommendationGenerateRequest): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.generateMarketplacePriceRecommendation(parsedOrganizationId, payload);
      setMessage("Price recommendation generated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to generate price recommendation.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReviewRecommendation(
    recommendationId: number,
    recommendationStatus: "reviewed" | "applied_internal" | "dismissed",
  ): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyRecommendationId(recommendationId);
    setError(null);
    setMessage(null);
    try {
      const payload: MarketplacePriceRecommendationReviewRequest = {
        recommendation_status: recommendationStatus,
        review_reason: recommendationStatus,
      };
      await apiClient.reviewMarketplacePriceRecommendation(parsedOrganizationId, recommendationId, payload);
      setMessage("Recommendation review state updated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to review price recommendation.");
    } finally {
      setBusyRecommendationId(null);
    }
  }

  async function handleSaveRule(
    payload: MarketplacePricingRuleCreateRequest | MarketplacePricingRuleUpdateRequest,
    ruleId: number | null,
  ): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      if (ruleId == null) {
        await apiClient.createMarketplacePricingRule(parsedOrganizationId, payload as MarketplacePricingRuleCreateRequest);
        setMessage("Pricing rule created.");
      } else {
        await apiClient.updateMarketplacePricingRule(parsedOrganizationId, ruleId, payload as MarketplacePricingRuleUpdateRequest);
        setMessage("Pricing rule updated.");
      }
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to save pricing rule.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleRuleStatus(ruleId: number, ruleStatus: "active" | "inactive"): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyRuleId(ruleId);
    setError(null);
    setMessage(null);
    try {
      await apiClient.updateMarketplacePricingRule(parsedOrganizationId, ruleId, { rule_status: ruleStatus });
      setMessage("Pricing rule status updated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to update pricing rule status.");
    } finally {
      setBusyRuleId(null);
    }
  }

  async function handleUpdateOfferStatus(
    offerId: number,
    offerStatus: "reviewed" | "accepted_internal" | "rejected_internal" | "expired",
  ): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyOfferId(offerId);
    setError(null);
    setMessage(null);
    try {
      const payload: MarketplaceOfferStatusUpdateRequest = { offer_status: offerStatus };
      await apiClient.updateMarketplaceOfferStatus(parsedOrganizationId, offerId, payload);
      setMessage("Offer status updated.");
      await refresh();
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to update offer status.");
    } finally {
      setBusyOfferId(null);
    }
  }

  const canView = organization ? hasOrganizationPermission(organization, "organization:view") : false;
  const canManage = organization ? hasOrganizationPermission(organization, "organization:update") : false;

  const recommendationCount = recommendations?.items.length ?? 0;
  const offerCount = offers?.items.length ?? 0;
  const ruleCount = rules?.items.length ?? 0;
  const activeRuleCount = useMemo(() => rules?.items.filter((rule) => rule.rule_status === "active").length ?? 0, [rules]);

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
        eyebrow="P43-05"
        title={organization ? `${organization.display_name} marketplace pricing` : "Marketplace pricing"}
        description="Deterministic pricing rules, recommendation records, offer tracking, and replay-safe pricing lineage for organization-scoped workflows."
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
              to={`/organizations/${parsedOrganizationId}/marketplace-orders`}
              className="rounded-2xl border border-teal-400/30 px-4 py-2 text-sm font-semibold text-teal-100"
            >
              Orders
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
          Loading marketplace pricing workspace...
        </section>
      ) : null}
      {!loading && organization && !canView ? (
        <div className="mt-6">
          <OrganizationAccessDeniedState
            title="Marketplace pricing access denied"
            description="Pricing visibility is deny-by-default and requires `organization:view`."
          />
        </div>
      ) : null}
      {!loading && organization && canView ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-4">
            <StatCard label="Recommendations" value={String(recommendationCount)} />
            <StatCard label="Offers" value={String(offerCount)} />
            <StatCard label="Pricing rules" value={String(ruleCount)} />
            <StatCard label="Active rules" value={String(activeRuleCount)} />
          </section>
          <section className="mt-4 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
            <div className="space-y-6">
              <MarketplacePriceRecommendationGeneratorShell
                accounts={accounts?.items ?? []}
                listings={listings}
                canManage={canManage}
                submitting={submitting}
                onGenerate={handleGenerateRecommendation}
              />
              <MarketplacePriceRecommendationTable
                items={recommendations?.items ?? []}
                busyRecommendationId={busyRecommendationId}
                canManage={canManage}
                onReview={handleReviewRecommendation}
              />
              <MarketplaceOfferSummaryPanel summary={offers?.summary ?? null} />
              <MarketplaceOfferTable
                items={offers?.items ?? []}
                busyOfferId={busyOfferId}
                canManage={canManage}
                onUpdateStatus={handleUpdateOfferStatus}
              />
            </div>
            <div className="space-y-6">
              <MarketplacePricingRuleEditorShell
                canManage={canManage}
                submitting={submitting}
                selectedRule={selectedRule}
                onSave={handleSaveRule}
                onClear={() => setSelectedRule(null)}
              />
              <MarketplacePricingRuleList
                items={rules?.items ?? []}
                busyRuleId={busyRuleId}
                canManage={canManage}
                onSelect={setSelectedRule}
                onToggleStatus={handleToggleRuleStatus}
              />
            </div>
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
