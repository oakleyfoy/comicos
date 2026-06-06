import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type OrganizationActivityCategory,
  type OrganizationActivityEventResponse,
  type OrganizationNotificationResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { OrganizationActivityFilters } from "../components/organizations/activity/OrganizationActivityFilters";
import { OrganizationActivityTimeline } from "../components/organizations/activity/OrganizationActivityTimeline";
import { OrganizationNotificationCenter } from "../components/organizations/activity/OrganizationNotificationCenter";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function OrganizationActivityPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [events, setEvents] = useState<OrganizationActivityEventResponse[]>([]);
  const [notifications, setNotifications] = useState<OrganizationNotificationResponse[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [category, setCategory] = useState<OrganizationActivityCategory | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const org = await apiClient.getOrganization(parsedOrganizationId);
      setOrganization(org);
      const [noteList, unread] = await Promise.all([
        apiClient.listOrganizationNotifications(parsedOrganizationId, { limit: 50, offset: 0 }),
        apiClient.getOrganizationNotificationUnreadCount(parsedOrganizationId),
      ]);
      setNotifications(noteList.items);
      setUnreadCount(unread.unread_count);
      if (!hasOrganizationPermission(org, "operations:view")) {
        setEvents([]);
        return;
      }
      const feed = await apiClient.listOrganizationActivity(parsedOrganizationId, {
        limit: 100,
        offset: 0,
        category: category ?? undefined,
      });
      setEvents(feed.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load organization activity.");
    } finally {
      setLoading(false);
    }
  }, [parsedOrganizationId, category]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleMarkRead(notificationId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusy(true);
    try {
      await apiClient.markOrganizationNotificationRead(parsedOrganizationId, notificationId);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to mark notification read.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAcknowledge(notificationId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusy(true);
    try {
      await apiClient.acknowledgeOrganizationNotification(parsedOrganizationId, notificationId);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to acknowledge notification.");
    } finally {
      setBusy(false);
    }
  }

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <EmptyState title="Invalid organization" description="The organization id in the URL is not valid." />
      </AppShell>
    );
  }

  const canViewFeed = organization ? hasOrganizationPermission(organization, "operations:view") : false;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Organization workspace"
        title="Activity feed"
        description="Internal operational activity and notifications for this dealer organization."
        actions={
          organization ? (
            <Link
              to={`/organizations/${organization.id}`}
              className="rounded-2xl border border-white/15 px-4 py-2 text-sm font-semibold text-slate-200"
            >
              Back to organization
            </Link>
          ) : null
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {loading || !organization ? (
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm text-sm text-slate-300">
          Loading activity workspace...
        </section>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-900">Activity timeline</h2>
              {canViewFeed ? <OrganizationActivityFilters category={category} onCategoryChange={setCategory} /> : null}
            </div>
            {!canViewFeed ? (
              <OrganizationAccessDeniedState
                title="Activity feed unavailable"
                description="You do not have permission to view the organization activity feed."
              />
            ) : (
              <OrganizationActivityTimeline events={events} />
            )}
          </section>
          <OrganizationNotificationCenter
            notifications={notifications}
            unreadCount={unreadCount}
            busy={busy}
            onMarkRead={(id) => void handleMarkRead(id)}
            onAcknowledge={(id) => void handleAcknowledge(id)}
          />
        </div>
      )}
    </AppShell>
  );
}
