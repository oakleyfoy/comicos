# P42 Audit / Compliance Architecture

## Objective

P42-08 establishes an immutable organization audit ledger and compliance event layer for ComicOS dealer organizations. The phase focuses on append-only accountability, deterministic ordering, org-scoped visibility, and replay-safe operational traceability. It does not implement external exports, legal hold workflows, enterprise retention deletion, or third-party SIEM integration.

## Core Model

- `organization_audit_ledger`
  - append-only organization audit rows
  - tracks `audit_category`, `audit_action`, `resource_type`, optional `resource_id`, stable JSON payload, and actor linkage
- `organization_compliance_events`
  - append-only compliance and lineage rows
  - tracks `compliance_event_type`, severity, and replay-safe payloads
- `organization_audit_access_logs`
  - append-only access-attempt rows for audit/compliance queries
  - records granted and denied audit visibility attempts inside the organization boundary

All rows are ordered newest-first with deterministic tie-breaking on descending `id` after `created_at`.

## Category / Severity Registry

Audit categories:

- `organization`
- `permissions`
- `inventory`
- `reviews`
- `storefront`
- `security`
- `sessions`
- `notifications`

Compliance severity levels:

- `info`
- `warning`
- `elevated`
- `critical`

The registry is centralized in `app/schemas/organization_audit.py` so category and severity handling stays deterministic across storage, API, tests, and UI.

## Replay-Safe Guarantees

- JSON payloads are normalized with sorted keys and UTC timestamps.
- Public list endpoints sort by `created_at DESC, id DESC`.
- Lineage rows use the `lineage.` prefix and remain immutable.
- Access-log writes and unauthorized audit attempts are append-only.
- No destructive cascades are introduced on organization/user foreign keys.

## Audit Ledger Service

`app/services/audit_ledger_service.py` provides:

- `create_audit_entry`
- `create_compliance_event`
- `create_audit_access_log`
- `list_org_audit_entries`
- `list_org_compliance_events`
- `list_org_audit_access_logs`
- `resolve_audit_visibility`

Audit visibility is fail-closed:

- active organization required
- active membership required
- `audit:view` required
- org scoping enforced before rows are returned

Successful and denied audit queries are both logged to the immutable access log.

## Immutable Compliance Lineage

Lineage compliance rows include:

- `lineage.audit_entry_created`
- `lineage.compliance_event_created`
- `lineage.audit_access_logged`
- `lineage.unauthorized_audit_access_attempt`
- `lineage.elevated_security_event`
- `lineage.critical_org_action`

Lineage rows are stored in the same immutable compliance table but excluded from the operator-facing compliance list.

## Unified Projection Layer

P42-08 projects audit rows from existing systems without replacing their native lineage tables:

- organization membership accept/remove
- permission role assign/remove
- inventory assignment, unassign, completion
- review approve/reject decisions
- storefront profile/settings changes
- session organization switch / revoke
- notification acknowledgements

This preserves source-of-truth workflow tables while adding a deterministic org-wide audit view.

## API Surface

- `GET /api/v1/organizations/{organization_id}/audit`
- `GET /api/v1/organizations/{organization_id}/compliance-events`
- `GET /api/v1/organizations/{organization_id}/audit/access-log`

All endpoints use the v1 envelope helpers and remain org-scoped. No audit data is exposed outside organization boundaries.

## Frontend Foundation

`OrganizationAuditPage` renders:

- audit timeline
- compliance event panel
- category / severity / actor / resource filters
- access-log panel
- audit detail viewer shell

The UI is backend-authoritative and does not infer visibility beyond `audit:view`.

## Future Expansion Points

- external compliance exports
- legal hold / retention policy controls
- enterprise evidence packaging
- SIEM connectors
- auditor-specific access models

Those remain intentionally out of scope for P42-08.
