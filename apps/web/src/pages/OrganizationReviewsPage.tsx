import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type OrganizationApprovalQueueResponse,
  type OrganizationReviewDecisionResponse,
  type OrganizationReviewResponse,
  type OrganizationResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { OrganizationReviewDetailPanel } from "../components/organizations/reviews/OrganizationReviewDetailPanel";
import { OrganizationReviewListPanel } from "../components/organizations/reviews/OrganizationReviewListPanel";
import { OrganizationReviewQueuesPanel } from "../components/organizations/reviews/OrganizationReviewQueuesPanel";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function OrganizationReviewsPage(): JSX.Element {
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [reviews, setReviews] = useState<OrganizationReviewResponse[]>([]);
  const [queues, setQueues] = useState<OrganizationApprovalQueueResponse[]>([]);
  const [selectedReviewId, setSelectedReviewId] = useState<number | null>(null);
  const [decisions, setDecisions] = useState<OrganizationReviewDecisionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (Number.isFinite(parsedOrganizationId)) {
      void refresh();
    }
  }, [parsedOrganizationId]);

  useEffect(() => {
    if (selectedReviewId && Number.isFinite(parsedOrganizationId)) {
      void loadDecisions(selectedReviewId);
    } else {
      setDecisions([]);
    }
  }, [selectedReviewId, parsedOrganizationId]);

  async function refresh(): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const org = await apiClient.getOrganization(parsedOrganizationId);
      setOrganization(org);
      if (!hasOrganizationPermission(org, "operations:view")) {
        setReviews([]);
        setQueues([]);
        return;
      }
      const [reviewList, queueList] = await Promise.all([
        apiClient.listOrganizationReviews(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listOrganizationReviewQueues(parsedOrganizationId, { limit: 200, offset: 0 }),
      ]);
      setReviews(reviewList.items);
      setQueues(queueList.items);
      if (reviewList.items.length && selectedReviewId === null) {
        setSelectedReviewId(reviewList.items[0].id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load organization reviews.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDecisions(reviewId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    try {
      const response = await apiClient.listOrganizationReviewDecisions(parsedOrganizationId, reviewId, {
        limit: 50,
        offset: 0,
      });
      setDecisions(response.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load review decisions.");
    }
  }

  async function handleApprove(): Promise<void> {
    if (!selectedReviewId || !Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusy(true);
    try {
      await apiClient.approveOrganizationReview(parsedOrganizationId, selectedReviewId, {});
      await refresh();
      await loadDecisions(selectedReviewId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approve failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReject(): Promise<void> {
    if (!selectedReviewId || !Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusy(true);
    try {
      await apiClient.rejectOrganizationReview(parsedOrganizationId, selectedReviewId, {});
      await refresh();
      await loadDecisions(selectedReviewId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reject failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAssign(): Promise<void> {
    if (!selectedReviewId || !Number.isFinite(parsedOrganizationId)) {
      return;
    }
    const raw = window.prompt("Assign to user id:");
    const assignedUserId = raw ? Number(raw) : NaN;
    if (!Number.isFinite(assignedUserId)) {
      return;
    }
    setBusy(true);
    try {
      await apiClient.assignOrganizationReview(parsedOrganizationId, selectedReviewId, { assigned_user_id: assignedUserId });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Assign failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <EmptyState title="Organization not found" description="Provide a valid organization id in the route." />
      </AppShell>
    );
  }

  const canView = organization ? hasOrganizationPermission(organization, "operations:view") : false;
  const canManage = organization ? hasOrganizationPermission(organization, "operations:manage") : false;
  const selectedReview = reviews.find((row) => row.id === selectedReviewId) ?? null;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P42-05"
        title="Team reviews"
        description="Deterministic review routing, approval queues, and immutable decision lineage for dealer operations."
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
      {loading ? <p className="text-sm text-slate-600">Loading review workspace…</p> : null}
      {!loading && organization && !canView ? (
        <OrganizationAccessDeniedState
          title="Access denied"
          description="You do not have permission to view organization reviews."
        />
      ) : null}
      {!loading && organization && canView ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          <section className="space-y-6">
            <OrganizationReviewListPanel
              reviews={reviews}
              selectedReviewId={selectedReviewId}
              onSelect={setSelectedReviewId}
            />
            <OrganizationReviewQueuesPanel queues={queues} />
          </section>
          <OrganizationReviewDetailPanel
            review={selectedReview}
            decisions={decisions}
            canManage={canManage}
            busy={busy}
            onApprove={() => void handleApprove()}
            onReject={() => void handleReject()}
            onAssign={() => void handleAssign()}
          />
        </div>
      ) : null}
    </AppShell>
  );
}
