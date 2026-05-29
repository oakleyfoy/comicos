# P44 API Reference

All P44 APIs use the scan API v1 envelope and are organization-scoped.

## P44-01 Mobile Foundation

- `GET /api/v1/organizations/{organization_id}/mobile`
- `GET /api/v1/organizations/{organization_id}/mobile/devices`
- `POST /api/v1/organizations/{organization_id}/mobile/devices`
- `PATCH /api/v1/organizations/{organization_id}/mobile/devices/{device_id}`
- `GET /api/v1/organizations/{organization_id}/mobile/sessions`
- `POST /api/v1/organizations/{organization_id}/mobile/sessions`
- `GET /api/v1/organizations/{organization_id}/mobile/contracts`
- `POST /api/v1/organizations/{organization_id}/mobile/contracts`

## P44-02 Offline Inventory

- `GET /api/v1/organizations/{organization_id}/offline-inventory`
- `POST /api/v1/organizations/{organization_id}/offline-inventory`
- `GET /api/v1/organizations/{organization_id}/offline-inventory/changes`
- `POST /api/v1/organizations/{organization_id}/offline-inventory/change`
- `GET /api/v1/organizations/{organization_id}/offline-inventory/queue`
- `POST /api/v1/organizations/{organization_id}/offline-inventory/queue`
- `GET /api/v1/organizations/{organization_id}/offline-inventory/conflicts`
- `PATCH /api/v1/organizations/{organization_id}/offline-inventory/conflicts/{conflict_id}`

## P44-03 Mobile Scanning

- `GET /api/v1/organizations/{organization_id}/mobile-scanning`
- `GET /api/v1/organizations/{organization_id}/mobile-scanning/scans`
- `GET /api/v1/organizations/{organization_id}/mobile-scanning/staging`
- `GET /api/v1/organizations/{organization_id}/mobile-scanning/lookups`
- `POST /api/v1/organizations/{organization_id}/mobile-scanning/capture`
- `POST /api/v1/organizations/{organization_id}/mobile-scanning/staging`
- `PATCH /api/v1/organizations/{organization_id}/mobile-scanning/staging/{staging_id}`

## P44-04 Convention Mode

- `GET /api/v1/organizations/{organization_id}/convention-mode`
- `GET /api/v1/organizations/{organization_id}/convention-mode/sessions`
- `POST /api/v1/organizations/{organization_id}/convention-mode/sessions`
- `PATCH /api/v1/organizations/{organization_id}/convention-mode/sessions/{session_id}`
- `GET /api/v1/organizations/{organization_id}/convention-mode/booths`
- `POST /api/v1/organizations/{organization_id}/convention-mode/booths`
- `PATCH /api/v1/organizations/{organization_id}/convention-mode/booths/{booth_id}`
- `GET /api/v1/organizations/{organization_id}/convention-mode/inventory`
- `POST /api/v1/organizations/{organization_id}/convention-mode/inventory`
- `GET /api/v1/organizations/{organization_id}/convention-mode/activities`

## P44-05 Quick Sales

- `GET /api/v1/organizations/{organization_id}/quick-sales`
- `GET /api/v1/organizations/{organization_id}/quick-sales/{sale_id}`
- `POST /api/v1/organizations/{organization_id}/quick-sales`
- `POST /api/v1/organizations/{organization_id}/quick-sales/{sale_id}/line-items`
- `PATCH /api/v1/organizations/{organization_id}/quick-sales/{sale_id}/line-items/{line_item_id}`
- `POST /api/v1/organizations/{organization_id}/quick-sales/{sale_id}/payments`
- `POST /api/v1/organizations/{organization_id}/quick-sales/{sale_id}/complete`
- `POST /api/v1/organizations/{organization_id}/quick-sales/{sale_id}/void`

## P44-06 Mobile Ops Dashboard

- `GET /api/v1/organizations/{organization_id}/mobile-ops`
- `GET /api/v1/organizations/{organization_id}/mobile-ops/metrics`
- `GET /api/v1/organizations/{organization_id}/mobile-ops/diagnostics`
- `GET /api/v1/organizations/{organization_id}/mobile-ops/snapshots`
- `POST /api/v1/organizations/{organization_id}/mobile-ops/generate`

## P44-07 Mobile Device Security

- `GET /api/v1/organizations/{organization_id}/mobile-security`
- `GET /api/v1/organizations/{organization_id}/mobile-security/trust-states`
- `POST /api/v1/organizations/{organization_id}/mobile-security/trust-states`
- `PATCH /api/v1/organizations/{organization_id}/mobile-security/trust-states/{trust_state_id}`
- `GET /api/v1/organizations/{organization_id}/mobile-security/policies`
- `POST /api/v1/organizations/{organization_id}/mobile-security/policies`
- `PATCH /api/v1/organizations/{organization_id}/mobile-security/policies/{policy_id}`
- `GET /api/v1/organizations/{organization_id}/mobile-security/access-logs`
- `GET /api/v1/organizations/{organization_id}/mobile-security/events`

## P44-08 Mobile Analytics

- `GET /api/v1/organizations/{organization_id}/mobile-analytics`
- `GET /api/v1/organizations/{organization_id}/mobile-analytics/metrics`
- `GET /api/v1/organizations/{organization_id}/mobile-analytics/trends`
- `GET /api/v1/organizations/{organization_id}/mobile-analytics/snapshots`
- `POST /api/v1/organizations/{organization_id}/mobile-analytics/generate`

## Permission Baseline

- View flows require organization-scoped visibility.
- Mutating flows require organization-scoped management.
- Device-aware writes may also require:
  - trusted-device policy compliance
  - non-suspended device state
  - active device session

## Explicit Exclusions

P44 APIs do not expose:

- external payment capture
- marketplace publishing or mutation
- shipping-provider workflows
- native mobile SDK endpoints
- realtime telemetry or push delivery
