import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type InventoryItem,
  type OrganizationInventoryAssignmentResponse,
  type OrganizationInventoryQueueResponse,
  type OrganizationInventoryWorkflowEventResponse,
  type OrganizationMemberResponse,
  type OrganizationResponse,
  type MarketplaceListingDraftResponse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { OrganizationAccessDeniedState } from "../components/organizations/permissions/OrganizationAccessDeniedState";
import { OrganizationInventoryAssignmentsPanel } from "../components/organizations/inventory/OrganizationInventoryAssignmentsPanel";
import { OrganizationInventoryQueuesPanel } from "../components/organizations/inventory/OrganizationInventoryQueuesPanel";
import { OrganizationInventoryWorkflowEventsPanel } from "../components/organizations/inventory/OrganizationInventoryWorkflowEventsPanel";
import { OrganizationSharedInventoryListPanel } from "../components/organizations/inventory/OrganizationSharedInventoryListPanel";
import { hasOrganizationPermission } from "../lib/organizationPermissions";

export function OrganizationInventoryPage(): JSX.Element {
  const navigate = useNavigate();
  const { organizationId } = useParams();
  const parsedOrganizationId = Number(organizationId);

  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [assignments, setAssignments] = useState<OrganizationInventoryAssignmentResponse[]>([]);
  const [queues, setQueues] = useState<OrganizationInventoryQueueResponse[]>([]);
  const [events, setEvents] = useState<OrganizationInventoryWorkflowEventResponse[]>([]);
  const [members, setMembers] = useState<OrganizationMemberResponse[]>([]);
  const [listingDrafts, setListingDrafts] = useState<MarketplaceListingDraftResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyInventoryId, setBusyInventoryId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      if (!hasOrganizationPermission(org, "inventory:view")) {
        setInventory([]);
        setAssignments([]);
        setQueues([]);
        setEvents([]);
        setMembers([]);
        return;
      }
      const [inventoryResponse, assignmentResponse, queueResponse, memberResponse, listingResponse] = await Promise.all([
        apiClient.getInventory({ page: 1, page_size: 50, organization_id: parsedOrganizationId }),
        apiClient.listOrganizationInventoryAssignments(parsedOrganizationId, { limit: 100, offset: 0 }),
        apiClient.listOrganizationInventoryQueues(parsedOrganizationId, { limit: 200, offset: 0 }),
        hasOrganizationPermission(org, "members:view")
          ? apiClient.listOrganizationMembers(parsedOrganizationId, { limit: 100, offset: 0 })
          : Promise.resolve({ items: [], pagination: { total_count: 0, limit: 0, offset: 0, has_next: false, next_cursor: null } }),
        hasOrganizationPermission(org, "organization:view")
          ? apiClient.listMarketplaceListings(parsedOrganizationId, { limit: 200, offset: 0 })
          : Promise.resolve({ items: [], permissions: { can_view: false, can_manage: false }, pagination: { total_count: 0, limit: 0, offset: 0, has_next: false, next_cursor: null } }),
      ]);
      setInventory(inventoryResponse.items);
      setAssignments(assignmentResponse.items);
      setQueues(queueResponse.items);
      setMembers(memberResponse.items);
      setListingDrafts(listingResponse.items);
      if (hasOrganizationPermission(org, "audit:view")) {
        const eventResponse = await apiClient.listOrganizationInventoryWorkflowEvents(parsedOrganizationId, {
          limit: 50,
          offset: 0,
        });
        setEvents(eventResponse.items);
      } else {
        setEvents([]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load organization inventory.");
    } finally {
      setLoading(false);
    }
  }

  async function handleAssign(inventoryItemId: number, assignedUserId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyInventoryId(inventoryItemId);
    try {
      await apiClient.assignOrganizationInventoryItem(parsedOrganizationId, {
        inventory_item_id: inventoryItemId,
        assigned_user_id: assignedUserId,
      });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Assignment failed.");
    } finally {
      setBusyInventoryId(null);
    }
  }

  async function handleComplete(inventoryItemId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyInventoryId(inventoryItemId);
    try {
      await apiClient.completeOrganizationInventoryAssignment(parsedOrganizationId, { inventory_item_id: inventoryItemId });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to complete assignment.");
    } finally {
      setBusyInventoryId(null);
    }
  }

  async function handleUnassign(inventoryItemId: number): Promise<void> {
    if (!Number.isFinite(parsedOrganizationId)) {
      return;
    }
    setBusyInventoryId(inventoryItemId);
    try {
      await apiClient.unassignOrganizationInventoryItem(parsedOrganizationId, { inventory_item_id: inventoryItemId });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to unassign inventory.");
    } finally {
      setBusyInventoryId(null);
    }
  }

  if (!Number.isFinite(parsedOrganizationId)) {
    return (
      <AppShell>
        <EmptyState title="Organization not found" description="Provide a valid organization id in the route." />
      </AppShell>
    );
  }

  const canViewInventory = organization ? hasOrganizationPermission(organization, "inventory:view") : false;
  const canManageInventory = organization ? hasOrganizationPermission(organization, "inventory:update") : false;
  const canManageListings = organization ? hasOrganizationPermission(organization, "organization:update") : false;
  const canViewAudit = organization ? hasOrganizationPermission(organization, "audit:view") : false;
  const listingDraftsByInventoryId = new Map<number, MarketplaceListingDraftResponse>();
  for (const row of listingDrafts) {
    if (!listingDraftsByInventoryId.has(row.inventory_item_id)) {
      listingDraftsByInventoryId.set(row.inventory_item_id, row);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P42-04"
        title="Organization inventory"
        description="Shared dealer inventory visibility, staff assignments, deterministic queues, and append-only workflow lineage."
        actions={
          <div className="flex gap-2">
            <Link
              to={`/organizations/${parsedOrganizationId}`}
              className="rounded-xl border border-white/15 px-4 py-2 text-sm text-slate-200 hover:bg-white/5"
            >
              Back to organization
            </Link>
            {organization && hasOrganizationPermission(organization, "organization:view") ? (
              <Link
                to={`/organizations/${parsedOrganizationId}/marketplace-listings`}
                className="rounded-xl border border-indigo-400/30 px-4 py-2 text-sm font-semibold text-indigo-100"
              >
                Marketplace listings
              </Link>
            ) : null}
          </div>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading organization inventory workspace…</p> : null}
      {!loading && organization && !canViewInventory ? (
        <OrganizationAccessDeniedState
          title="Access denied"
          description="You do not have permission to view organization inventory."
        />
      ) : null}
      {!loading && organization && canViewInventory ? (
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <section className="space-y-4">
            <OrganizationSharedInventoryListPanel
              items={inventory}
              loading={false}
              organizationId={parsedOrganizationId}
              listingDraftsByInventoryId={listingDraftsByInventoryId}
              canCreateListing={canManageListings}
              onCreateListingDraft={(inventoryItemId) =>
                navigate(`/organizations/${parsedOrganizationId}/marketplace-listings`, {
                  state: { inventoryItemId },
                })
              }
            />
            <OrganizationInventoryAssignmentsPanel
              assignments={assignments}
              members={members}
              canManage={canManageInventory}
              busyInventoryId={busyInventoryId}
              onAssign={(inventoryItemId, assignedUserId) => void handleAssign(inventoryItemId, assignedUserId)}
              onComplete={(inventoryItemId) => void handleComplete(inventoryItemId)}
              onUnassign={(inventoryItemId) => void handleUnassign(inventoryItemId)}
            />
          </section>
          <section className="space-y-6">
            <OrganizationInventoryQueuesPanel queues={queues} />
            <OrganizationInventoryWorkflowEventsPanel events={events} canView={canViewAudit} />
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
