# P42 Architecture Inventory

Authoritative file-level inventory for P42 multi-user dealer infrastructure (`comic-os-p41-feed`).

## Models (`apps/api/app/models/`)

| Subsystem | Files |
|-----------|--------|
| P42-01 | `organization.py`, `organization_events.py` |
| P42-02 | `organization_permissions.py` |
| P42-03 | `auth_sessions.py` |
| P42-04 | `organization_inventory.py` |
| P42-05 | `organization_reviews.py` |
| P42-06 | `dealer_profiles.py` (includes `DealerStorefrontEvent`) |
| P42-07 | `organization_activity.py` |
| P42-08 | `organization_audit.py` |
| P42-09 | `organization_dealer_dashboard.py` |

Legacy (not P42 org dashboard): `dealer_dashboard.py`, `dealer_grading_dashboard.py`.

## Schemas (`apps/api/app/schemas/`)

| Subsystem | Files |
|-----------|--------|
| P42-01 | `organization.py` |
| P42-04 | `organization_inventory.py` |
| P42-05 | `organization_reviews.py` |
| P42-06 | `dealer_storefront.py` (and related dealer profile schemas) |
| P42-07 | `organization_activity.py` |
| P42-08 | `organization_audit.py` |
| P42-09 | `organization_dealer_dashboard.py` |

## Services (`apps/api/app/services/`)

| Subsystem | Files |
|-----------|--------|
| P42-01 | `organization_service.py` |
| P42-02 | `authorization_service.py` |
| P42-03 | `session_manager.py` (security), `tenant_context` (security) |
| P42-04 | `shared_inventory_service.py`, `organization_inventory_access.py` |
| P42-05 | `review_workflow_service.py`, `review_permissions.py` |
| P42-06 | `dealer_profile_service.py`, `storefront_visibility_service.py` |
| P42-07 | `activity_feed_service.py`, `notification_permissions.py` |
| P42-08 | `audit_ledger_service.py`, `audit_ledger_integration.py` |
| P42-09 | `dealer_dashboard_service.py` |

## APIs (`apps/api/app/api/`)

| Subsystem | Module |
|-----------|--------|
| P42-01 | `organization.py` |
| P42-03 | `routes/auth_sessions.py` |
| P42-04 | `shared_inventory.py` |
| P42-05 | `reviews.py` |
| P42-06 | `storefronts.py` |
| P42-07 | `activity.py` |
| P42-08 | `audit.py` |
| P42-09 | `dealer_dashboard.py` |

Shared dependency: `api/dependencies/organization_auth.py`.

Wiring: `apps/api/app/main.py` (`attach_organization_layer`, `attach_auth_sessions_layer`, `attach_shared_inventory_layer`, `attach_reviews_layer`, `attach_storefronts_layer`, `attach_activity_layer`, `attach_audit_layer`, `attach_dealer_dashboard_layer`).

Inventory hydration: `GET /inventory?organization_id=` in `main.py` (org-scoped shared inventory reads).

## Frontend pages (`apps/web/src/pages/`)

| Page | Route (typical) |
|------|-----------------|
| `OrganizationsPage.tsx` | `/organizations` |
| `OrganizationDetailPage.tsx` | `/organizations/:organizationId` |
| `OrganizationInventoryPage.tsx` | `/organizations/:organizationId/inventory` |
| `OrganizationReviewsPage.tsx` | `/organizations/:organizationId/reviews` |
| `OrganizationActivityPage.tsx` | `/organizations/:organizationId/activity` |
| `OrganizationAuditPage.tsx` | `/organizations/:organizationId/audit` |
| `DealerOperationsDashboardPage.tsx` | `/organizations/:organizationId/dashboard` |
| `DealerProfileSettingsPage.tsx` | `/organizations/:organizationId/storefront` |
| `DealerStorefrontPage.tsx` | `/storefront/:publicSlug` (public) |

## Frontend components (`apps/web/src/components/`)

- `organizations/` — create, list, members, invite, events, permissions panels
- `organizations/inventory/` — shared list, assignments, queues, workflow events
- `organizations/reviews/` — list, queues, detail
- `organizations/activity/` — timeline, filters, notification center
- `organizations/audit/` — timeline, compliance, access log, filters
- `organizations/permissions/` — role matrix, assignments, denied state
- `dashboard/` — metric cards, section panels, timeline shell

Client bindings: `apps/web/src/api/client.ts` (organization, inventory, reviews, activity, audit, dashboard, storefront methods).

Permission UI helper: `apps/web/src/lib/organizationPermissions.ts`.

Routes: `apps/web/src/App.tsx`.

## Tests (`apps/api/tests/`)

| File |
|------|
| `test_organizations.py` |
| `test_organization_permissions.py` |
| `test_auth_sessions.py` |
| `test_shared_inventory.py` |
| `test_review_workflows.py` |
| `test_storefronts.py` |
| `test_activity_feed.py` |
| `test_audit_ledger.py` |
| `test_dealer_dashboard.py` |
| `test_p42_regression.py` |

## Migrations (`apps/api/alembic/versions/`)

| Revision | File |
|----------|------|
| 0112 | `20260624_0112_add_organization_foundation.py` |
| 0113 | `20260625_0113_add_organization_authorization_foundation.py` |
| 0114 | `20260626_0114_add_auth_session_security_context.py` |
| 0115 | `20260627_0115_add_shared_inventory_workflow.py` |
| 0116 | `20260628_0116_add_organization_review_workflow.py` |
| 0117 | `20260629_0117_add_dealer_storefront_foundation.py` |
| 0118 | `20260630_0118_add_organization_activity_feed.py` |
| 0119 | `20260701_0119_add_organization_audit_ledger.py` |
| 0120 | `20260702_0120_add_organization_dealer_dashboard.py` (**head**) |

## Documentation (`docs/`)

| Doc |
|-----|
| `P42_ORGANIZATION_ARCHITECTURE.md` |
| `P42_AUTHORIZATION_ARCHITECTURE.md` |
| `P42_SHARED_INVENTORY_ARCHITECTURE.md` |
| `P42_REVIEW_WORKFLOW_ARCHITECTURE.md` |
| `P42_STOREFRONT_ARCHITECTURE.md` |
| `P42_ACTIVITY_FEED_ARCHITECTURE.md` |
| `P42_AUDIT_COMPLIANCE_ARCHITECTURE.md` |
| `P42_DEALER_DASHBOARD_ARCHITECTURE.md` |
| `P42_HARDENING_REPORT.md` |
| `P42_ARCHITECTURE_INDEX.md` |
| `P42_DEPENDENCY_GRAPH.md` |
| `P42_OPERATIONS_GUIDE.md` |
| `P42_API_REFERENCE.md` |
| `P42_DETERMINISM_GUARANTEES.md` |
| `P42_PRODUCTION_READINESS.md` |
| `P42_FUTURE_INTEGRATION_MAP.md` |
| `P42_ARCHITECTURE_INVENTORY.md` (this file) |
| `P42_CLOSEOUT_SUMMARY.md` |
