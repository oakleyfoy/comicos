# P42 Organization Architecture

## Objective

P42-01 establishes the first multi-tenant organization and dealer-account foundation for ComicOS without introducing role matrices, shared workflows, tenant middleware, notifications, or analytics. The goal is to create deterministic identity primitives that later phases can safely build on.

## Core Model

The organization foundation introduces four tables:

- `organizations`: stable external identity, owner linkage, lifecycle state, and archive metadata.
- `organization_members`: active or removed organization membership records keyed by organization and user.
- `organization_invitations`: deterministic invitation tokens, invite lifecycle state, and acceptance timestamps.
- `organization_events`: append-only audit ledger for organization lifecycle actions.

Each table is ordered deterministically with `created_at` and `id` indexes so list APIs, replay comparisons, and audit reviews return stable results.

## Organization Lifecycle

The initial lifecycle is intentionally small:

1. An authenticated user creates an organization with a normalized slug and stable `public_id`.
2. The owner is immediately inserted as an active member record.
3. An `organization_created` event is written to the append-only ledger.
4. Owners can create deterministic invitations for future members.
5. Matching authenticated users accept invitations, which creates membership records and `invitation_accepted` audit events.
6. Owners can archive organizations, which prevents new invitations but preserves all history.

No destructive deletes are used in this phase. Archiving and member removal are represented as state transitions plus new event ledger entries.

## Membership Model

Membership currently supports foundation-only states:

- `ACTIVE`
- `REMOVED`

There is no permissions or role matrix yet. Ownership is represented by `organizations.owner_user_id`, while access for read routes is granted to the owner or any active member. Write flows remain owner-only in this phase.

## Invitation Lifecycle

Invitations are deterministic and duplicate-safe:

- Invitation email addresses are normalized to lowercase.
- Repeated invites for the same pending email reuse the existing invitation record instead of creating duplicates.
- Invitation tokens are derived from organization identity, invited email, inviter, and a deterministic sequence number.
- Expired invitations are marked expired before a later invite can create a new record.

This phase stores invitation state only. Delivery, messaging, and reminder workflows are deferred.

## Event Lineage Model

`organization_events` is append-only and immutable after insert. Initial supported event types:

- `organization_created`
- `member_invited`
- `invitation_accepted`
- `member_removed`
- `organization_archived`

These events provide the replay-safe audit lineage for later organization features. State tables answer current status queries, while the event ledger preserves the historical trail.

## Tenant Foundation Contracts

P42-01 establishes the contracts later phases depend on:

- organizations have stable public identity via `public_id`
- users can belong to organizations through explicit membership records
- invitation acceptance requires an authenticated user email match
- owner and member lookups are deterministic and organization-scoped
- organization lifecycle actions generate append-only ledger events
- future org-aware systems can attach `organization_id` without redesigning identity

## Ownership Assumptions

Current assumptions are intentionally narrow:

- one organization has one owner user in this phase
- the owner is always also an active member
- owners cannot be removed through the current service contract
- archived organizations remain readable but reject new invitations
- there is no tenant-wide inventory or data isolation middleware yet

## Future P42 Dependency Map

Later P42 phases can build on this foundation for:

- role and permission matrices
- organization-scoped tenant enforcement
- shared inventory and workflow collaboration
- organization notifications and invites delivery
- multi-user review systems
- organization analytics and ops visibility

Those features are intentionally deferred so this phase can stay deterministic, replay-safe, and auditable.
