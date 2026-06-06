import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiClient, type OrganizationResponse } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function DealerProfileSettingsPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [publicSlug, setPublicSlug] = useState("my-dealer-shop");
  const [displayName, setDisplayName] = useState("");
  const [tagline, setTagline] = useState("");
  const [visibility, setVisibility] = useState<"PUBLIC" | "UNLISTED" | "PRIVATE">("PRIVATE");
  const [publicInventoryEnabled, setPublicInventoryEnabled] = useState(false);
  const [featuredSort, setFeaturedSort] = useState<"newest" | "recently_updated" | "highest_value" | "manually_selected">("newest");
  const [manualFeaturedIds, setManualFeaturedIds] = useState("");
  const [savedPublicSlug, setSavedPublicSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
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
      const org = await apiClient.getOrganization(parsedOrganizationId);
      setOrganization(org);
      setDisplayName(org.display_name);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load organization.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const profile = await apiClient.upsertDealerStorefrontProfile(parsedOrganizationId, {
        public_slug: publicSlug,
        display_name: displayName || "Dealer",
        tagline: tagline || null,
        profile_status: "ACTIVE",
      });
      await apiClient.updateDealerStorefrontSettings(parsedOrganizationId, {
        storefront_visibility: visibility,
        public_inventory_enabled: publicInventoryEnabled,
        featured_inventory_limit: 12,
        featured_inventory_sort: featuredSort,
        featured_manual_inventory_ids: manualFeaturedIds
          .split(",")
          .map((value) => Number(value.trim()))
          .filter((value) => Number.isFinite(value)),
      });
      setSavedPublicSlug(profile.public_slug);
      setMessage("Storefront profile and visibility settings saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save storefront settings.");
    } finally {
      setSaving(false);
    }
  }

  const canManage = organization ? hasOrganizationPermission(organization, "organization:update") : false;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P42-06"
        title="Dealer storefront settings"
        description="Configure public dealer identity, visibility controls, and deterministic featured inventory presentation."
        actions={
          <Link
            to={`/organizations/${parsedOrganizationId}`}
            className="rounded-xl border border-white/15 px-4 py-2 text-sm text-slate-200 hover:bg-white/5"
          >
            Back to organization
          </Link>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading storefront settings…</p> : null}
      {!loading && organization && !canManage ? (
        <OrganizationAccessDeniedState
          title="Access denied"
          description="Organization update permission is required to manage storefront settings."
        />
      ) : null}
      {!loading && organization && canManage ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-900">Dealer profile</h2>
            <label className="block text-xs text-slate-400">
              Public slug
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                value={publicSlug}
                onChange={(event) => setPublicSlug(event.target.value)}
              />
            </label>
            <label className="block text-xs text-slate-400">
              Display name
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <label className="block text-xs text-slate-400">
              Tagline
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                value={tagline}
                onChange={(event) => setTagline(event.target.value)}
              />
            </label>
          </section>
          <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-900">Visibility & featured inventory</h2>
            <label className="block text-xs text-slate-400">
              Storefront visibility
              <select
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                value={visibility}
                onChange={(event) => setVisibility(event.target.value as "PUBLIC" | "UNLISTED" | "PRIVATE")}
              >
                <option value="PRIVATE">Private</option>
                <option value="UNLISTED">Unlisted</option>
                <option value="PUBLIC">Public</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={publicInventoryEnabled}
                onChange={(event) => setPublicInventoryEnabled(event.target.checked)}
              />
              Enable public inventory
            </label>
            <label className="block text-xs text-slate-400">
              Featured sort mode
              <select
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                value={featuredSort}
                onChange={(event) =>
                  setFeaturedSort(event.target.value as "newest" | "recently_updated" | "highest_value" | "manually_selected")
                }
              >
                <option value="newest">Newest</option>
                <option value="recently_updated">Recently updated</option>
                <option value="highest_value">Highest value</option>
                <option value="manually_selected">Manually selected</option>
              </select>
            </label>
            <label className="block text-xs text-slate-400">
              Manual featured inventory IDs (comma-separated)
              <input
                className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                value={manualFeaturedIds}
                onChange={(event) => setManualFeaturedIds(event.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={saving}
              onClick={() => void handleSave()}
              className="rounded-xl bg-violet-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save storefront"}
            </button>
            {savedPublicSlug && visibility !== "PRIVATE" && publicInventoryEnabled ? (
              <Link to={`/storefront/${savedPublicSlug}`} className="block text-sm text-violet-300 hover:underline">
                Preview public storefront
              </Link>
            ) : null}
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
