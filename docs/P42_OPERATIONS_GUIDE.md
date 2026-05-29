# P42 Operations Guide

Operator- and admin-oriented workflows for ComicOS dealer organizations. This guide describes **what** to do, not implementation internals.

## Prerequisites

- Users authenticate with a valid session.
- Dealers create or join organizations before using shared inventory, reviews, or dashboards.

## Create and manage an organization

1. Create an organization (display name, slug, type `DEALER`).
2. Confirm the creator is the **owner** with full permissions.
3. Use the organization detail workspace to view status, member counts, and navigation to subsystems.

## Invite members

1. Owner or a role with `members:invite` sends an invitation by email.
2. Invitee registers or logs in and accepts via the invitation token.
3. New members receive the default **viewer** role unless changed.
4. Duplicate invitations for the same email return the same pending invite (idempotent).

## Assign permissions

1. Owners use **role assignment** to grant `admin`, `manager`, `staff`, or additional roles.
2. Only roles with `members:roles:update` may change another member’s roles.
3. The **owner** role cannot be removed from the organization owner via self-escalation paths.
4. Permission denials are recorded for compliance review.

## Manage shared inventory

1. Ensure inventory copies exist under the owning user account.
2. Members with `inventory:view` open **Shared inventory** for the organization.
3. Users with `inventory:update` assign items to staff, move queues, and complete assignments.
4. Workflow history is visible to roles with `audit:view` on the inventory events panel.

## Run review workflows

1. Users with `operations:view` see pending and historical team reviews.
2. Users with `operations:manage` create reviews, assign reviewers, move queues, approve, or reject.
3. Approved or rejected reviews retain an append-only decision history.
4. Inventory views show active review metadata when hydrated for the org.

## Manage storefronts

1. Users authorized for storefront management configure **profile** (slug, display name, status).
2. **Settings** control public vs private visibility and featured inventory.
3. Public storefront URLs expose only sanitized inventory fields.
4. Private or inactive storefronts do not expose inventory listings publicly.

## Activity and notifications

1. Users with `operations:view` read the org **activity feed**.
2. All active members receive **notifications** targeted to them; read and acknowledge from the activity workspace.
3. Unread counts are available per organization for the signed-in user.

## Audit and compliance

1. Users with `audit:view` open the **audit ledger** and compliance panels.
2. Access attempts (granted or denied) appear in the audit access log.
3. Critical org actions (for example member removal) surface as compliance events.

## Dealer operations dashboard

1. Users with `operations:view` open the **Operations dashboard** for the organization.
2. Refresh loads deterministic metric cards and section summaries (inventory, reviews, activity, storefront, notifications, security).
3. Snapshot history is append-only; use the timeline shell for recent snapshot lineage (no live websocket in P42).

## Archive an organization

1. Owner (or role with `organization:archive`) archives the organization.
2. Archived organizations reject new invitations and operational extensions per service rules.

## When access is denied

- Confirm membership is **ACTIVE**.
- Confirm the user’s roles include the required permission (see [P42_API_REFERENCE.md](./P42_API_REFERENCE.md)).
- Some routes return **404** instead of **403** to avoid leaking org or resource existence; treat both as deny.
