# P42 Architecture Index

Authoritative entry point for ComicOS multi-user dealer organization infrastructure (P42).

## Platform freeze

P42 is **closed** at migration head `20260702_0120`. Downstream phases must treat organizations, permissions, sessions, shared inventory, reviews, storefronts, activity, audit, and the org dealer dashboard as stable platform contracts unless a later phase explicitly revises them.

## Subsystem inventory

| Phase | Name | Purpose | Deep-dive doc |
|-------|------|---------|----------------|
| P42-01 | Organization Foundation | Multi-tenant orgs, members, invitations, append-only org events | [P42_ORGANIZATION_ARCHITECTURE.md](./P42_ORGANIZATION_ARCHITECTURE.md) |
| P42-02 | Roles / Permissions / Tenant Isolation | System roles, permission evaluation, deny-by-default, audit of permission checks | [P42_AUTHORIZATION_ARCHITECTURE.md](./P42_AUTHORIZATION_ARCHITECTURE.md) |
| P42-03 | Auth Sessions / Security Context | Session lifecycle, org context switch, revocation, cross-org session boundaries | (see [P42_API_REFERENCE.md](./P42_API_REFERENCE.md) § Sessions) |
| P42-04 | Shared Inventory | Org-scoped assignments, queues, workflow events, inventory hydration | [P42_SHARED_INVENTORY_ARCHITECTURE.md](./P42_SHARED_INVENTORY_ARCHITECTURE.md) |
| P42-05 | Review Workflows | Team reviews, queues, append-only decisions | [P42_REVIEW_WORKFLOW_ARCHITECTURE.md](./P42_REVIEW_WORKFLOW_ARCHITECTURE.md) |
| P42-06 | Storefront Foundation | Public dealer profiles, visibility, sanitized public inventory | [P42_STOREFRONT_ARCHITECTURE.md](./P42_STOREFRONT_ARCHITECTURE.md) |
| P42-07 | Activity Feed | Org activity timeline, notifications, lineage | [P42_ACTIVITY_FEED_ARCHITECTURE.md](./P42_ACTIVITY_FEED_ARCHITECTURE.md) |
| P42-08 | Audit / Compliance | Immutable audit ledger, compliance events, access logs | [P42_AUDIT_COMPLIANCE_ARCHITECTURE.md](./P42_AUDIT_COMPLIANCE_ARCHITECTURE.md) |
| P42-09 | Dealer Dashboard | Org operational metrics, snapshots, dashboard lineage | [P42_DEALER_DASHBOARD_ARCHITECTURE.md](./P42_DEALER_DASHBOARD_ARCHITECTURE.md) |
| P42-10 | Hardening | Regression, isolation, replay, determinism verification | [P42_HARDENING_REPORT.md](./P42_HARDENING_REPORT.md) |
| P42-11 | Closeout | Documentation package, production readiness, platform freeze | [P42_CLOSEOUT_SUMMARY.md](./P42_CLOSEOUT_SUMMARY.md) |

## Closeout and operations docs

- [P42_DEPENDENCY_GRAPH.md](./P42_DEPENDENCY_GRAPH.md) — subsystem dependencies and P43 touchpoints
- [P42_OPERATIONS_GUIDE.md](./P42_OPERATIONS_GUIDE.md) — operator workflows
- [P42_API_REFERENCE.md](./P42_API_REFERENCE.md) — `/api/v1` org surface
- [P42_DETERMINISM_GUARANTEES.md](./P42_DETERMINISM_GUARANTEES.md) — invariants
- [P42_PRODUCTION_READINESS.md](./P42_PRODUCTION_READINESS.md) — readiness findings
- [P42_FUTURE_INTEGRATION_MAP.md](./P42_FUTURE_INTEGRATION_MAP.md) — P43 integration contracts
- [P42_ARCHITECTURE_INVENTORY.md](./P42_ARCHITECTURE_INVENTORY.md) — file-level inventory

## Dependency summary

All P42 feature surfaces hang from **P42-01 organizations** and **P42-02 permissions**. **P42-03 sessions** bind the active org to the authenticated user. Inventory, reviews, storefront, activity, audit, and dashboard layers read org membership and permissions; they do not bypass tenant checks.

## Future phase references

P43 and later phases should integrate via documented contracts in [P42_FUTURE_INTEGRATION_MAP.md](./P42_FUTURE_INTEGRATION_MAP.md), not by duplicating org or permission tables.
