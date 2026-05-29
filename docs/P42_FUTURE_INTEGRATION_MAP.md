# P42 Future Integration Map

Integration **contracts** for phases after P42 (for example P43). No implementation is defined here.

## Organizations

**Contract**

- Every dealer-facing feature carries a required `organization_id`.
- External systems map to `Organization.public_id` or internal numeric `id` consistently; do not invent parallel tenant tables.

**P43 must not**

- Create shadow org membership outside `organization_members`.
- Bypass archive/status checks on inactive orgs.

## Permissions

**Contract**

- New capabilities extend `PERMISSION_ORDER` and role bundles in `permissions.py`, then route through `evaluate_permission`.
- New deny reasons append to `organization_permission_audit`.

**P43 must not**

- Hard-code role bypasses in marketplace routes.
- Assume owner permissions without session + membership validation.

## Storefronts

**Contract**

- Public commerce surfaces resolve via `public_slug` and `storefront_visibility` rules.
- Listing payloads use the same sanitization boundary as `/storefronts/{slug}/inventory` (no internal cost/review fields).

**P43 must not**

- Expose raw inventory copy rows on public routes.
- Toggle visibility without writing storefront events.

## Inventory

**Contract**

- Marketplace or consignment flows reference `inventory_copy_id` and org assignment state.
- Mutations that affect dealer operations should emit inventory workflow events and activity feed entries.

**P43 must not**

- Reassign inventory across orgs without owner-level provenance.
- Skip `inventory:view` / `inventory:update` gates on org-scoped writes.

## Audit

**Contract**

- Financial or policy-sensitive P43 actions call `create_audit_entry` with category/action/resource_type aligned to [P42_AUDIT_COMPLIANCE_ARCHITECTURE.md](./P42_AUDIT_COMPLIANCE_ARCHITECTURE.md).
- Elevated/critical compliance uses existing severity levels.

**P43 must not**

- Update or delete historical `organization_audit_ledger` rows.
- Store PCI or secrets in `audit_payload_json`.

## Dashboard

**Contract**

- New operational KPIs extend `METRIC_KEYS` and `METRIC_KEY_TO_GROUP` in organization dealer dashboard schemas, with append-only metric rows.
- P43 read-only consumers may call existing GET dashboard routes with `operations:view`.

**P43 must not**

- Overwrite snapshot payloads in place.
- Aggregate cross-org metrics in org dashboard tables.

## Activity feed (recommended)

**Contract**

- User-visible dealer actions publish `create_activity_event` with stable `activity_type` and `category` for feed + notification fan-out.

## Session context (recommended)

**Contract**

- Long-running P43 operator tools set active org via `/auth/security-context/switch-organization` before org-scoped mutations.

## Dependency order for P43 implementers

1. Confirm org + membership + permission.
2. Perform domain action (inventory/storefront/marketplace).
3. Append activity + audit lineage.
4. Refresh dashboard metrics only through existing dashboard service entry points.
