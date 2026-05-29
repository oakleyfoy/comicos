# P44-07 Device Management / Security

P44-07 establishes the application-level mobile device security layer for ComicOS. This phase adds organization-scoped trust states, deterministic policy controls, access validation hooks for device-aware mobile workflows, append-only access logs, and replay-safe security lineage.

## Device Trust Model

- `MobileDeviceTrustState` stores the current security posture for each registered mobile device.
- Trust states are limited to `trusted`, `untrusted`, and `suspended`.
- Trust-state rows are mutable current-state records, but every change also writes immutable `MobileDeviceSecurityEvent` lineage.
- Suspensions also update the associated `MobileDevice.device_status` and terminate active device sessions deterministically.

## Security Policy Model

- `MobileDeviceSecurityPolicy` stores organization-scoped policy rows keyed by:
  - `require_trusted_device`
  - `block_suspended_device`
  - `require_active_session`
  - `allow_offline_actions`
- Policies transition only between `active` and `inactive`.
- Effective defaults are intentionally conservative for suspended devices and active-session requirements, while trusted-device enforcement is opt-in until explicitly activated.
- Policy mutations emit append-only `device_security_policy_created` and `device_security_policy_updated` events.

## Access Validation Flow

Device-aware mobile services call `validate_mobile_device_access()` before performing writes that already carry a device reference:

- mobile session creation
- offline inventory change registration and queueing
- scan capture and staging actions
- quick-sale create/update/payment/complete/void flows when a mobile device is attached

The validator:

1. Confirms organization visibility for the actor.
2. Resolves the device, trust state, and effective policy set.
3. Denies suspended devices when `block_suspended_device` is active.
4. Requires trusted state when `require_trusted_device` is active.
5. Requires an active mobile session where applicable.
6. Applies offline policy checks for offline queue operations and offline quick sales.

Allowed and denied evaluations both write append-only lineage:

- `MobileDeviceAccessLog`
- `device_access_allowed`
- `device_access_denied`

## Access Logging

- `MobileDeviceAccessLog` records one row per evaluated access attempt.
- Logs are ordered by `(accessed_at, id)` for deterministic replay.
- `MobileDeviceSecurityEvent` records the higher-level immutable timeline for trust-state updates, suspensions, unsuspensions, policy mutations, denied attempts, allowed access, and unauthorized security API access attempts.
- Security API permission failures emit `unauthorized_mobile_security_access_attempt`.

## Replay-Safe Guarantees

- Security event payloads are JSON-normalized with stable key ordering.
- Timestamps are generated in UTC and stored explicitly.
- Trust-state and policy rows use stable organization-scoped uniqueness constraints.
- Access logs and security events are append-only and never rewritten.
- All device lookups enforce organization ownership before state changes or validation decisions.

## Frontend Workspace

The mobile security workspace provides:

- trust-state table
- policy table
- suspend / unsuspend controls
- recent access-log viewer
- append-only event timeline
- derived summary and diagnostic cards

The UI is backend-authoritative and intentionally excludes biometric, MFA, native MDM, remote wipe, and OS-level attestation features.

## Future Dependencies

This phase prepares future work for:

- stronger trusted-device enforcement defaults
- offline security hardening
- richer mobile policy payloads
- future native-security integrations

This phase does not implement biometric authentication, MFA, native mobile device management, encrypted local storage, or real-time device tracking.
