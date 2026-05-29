# P42 Authorization Architecture

## Objective

P42-02 establishes deterministic organization-scoped authorization and tenant-isolation primitives for ComicOS. This phase adds system roles, centralized permission resolution, fail-closed access checks, and append-only authorization audit lineage without redesigning authentication or introducing advanced enterprise RBAC features.

## Role Hierarchy

System roles are immutable and organization-scoped:

1. `owner`
2. `admin`
3. `manager`
4. `staff`
5. `viewer`

Each organization receives the same ordered role registry. Roles are stored per organization, but the role definitions and permission matrix are centrally defined and deterministic.

## Permission Evaluation Flow

Authorization follows an explicit deny-by-default sequence:

1. Resolve the target organization.
2. Resolve the actor's active membership within that organization.
3. Resolve assigned organization roles in stable order.
4. Expand those roles into the centralized permission set.
5. Allow only when the requested permission key is explicitly present.
6. Write an immutable authorization audit row for the allow or deny result.

There are no fallback permissions, no hidden owner bypasses in permission resolution, and no middleware-side implicit escalation in this phase.

## Permission Matrix

Core permission groups:

- Organization: `organization:view`, `organization:update`, `organization:archive`
- Members: `members:view`, `members:invite`, `members:remove`, `members:roles:update`
- Inventory: `inventory:view`, `inventory:create`, `inventory:update`, `inventory:delete`
- Operations: `operations:view`, `operations:manage`
- Audit: `audit:view`

The system role registry maps these permissions deterministically and centrally so replayed authorization decisions remain stable.

## Tenant Isolation Model

Tenant isolation is explicit and organization-scoped:

- every protected organization route resolves the organization context first
- membership is validated against that exact organization
- role and permission evaluation is always scoped to one organization
- helper utilities reject cross-organization resource access
- missing membership or permission resolves to an explicit deny

This phase does not add global tenant middleware. Route-level dependencies and service-layer validation establish the enforcement contracts first.

## Deny-By-Default Principles

P42-02 intentionally fails closed:

- users without active membership have no organization permissions
- users with membership but no assigned role have no permissions
- routes require explicit permission dependencies for sensitive actions
- self-role mutation is blocked
- restricted role assignment and removal is blocked unless the owner invariant allows it

This keeps authorization deterministic and easy to audit.

## Authorization Audit Lineage

`organization_permission_audits` is append-only and immutable after insert. It records:

- permission grants
- permission denials
- role assignments
- role removals
- unauthorized access attempts

Audit payloads are serialized deterministically so investigation and replay comparisons remain stable over time.

## Ownership Invariants

The following invariants are enforced in this phase:

- every organization owner is also an organization member
- every organization owner is seeded with the `owner` role
- accepted invitees receive a baseline `viewer` role
- owner role assignments are immutable through the role management APIs
- users cannot mutate their own roles
- non-owner actors cannot assign or remove protected roles such as `owner` and `admin`

## Future RBAC Expansion

This phase prepares later authorization work without implementing it yet:

- custom organization roles
- role inheritance
- organization-wide policy composition
- tenant middleware auto-injection
- public/storefront permissions
- SSO and external identity sync
- billing-aware permission gates

Those features will build on the deterministic role registry, permission evaluation, and audit lineage introduced here.
