# eBay Marketplace Account Deletion Compliance

ComicOS implements the [eBay Marketplace Account Deletion](https://developer.ebay.com/marketplace-account-deletion) notification endpoint so production keysets can be activated. This is **compliance only** — no P70 sold-listing ingest, OAuth token storage, or marketplace sync.

## Production endpoint

Register this URL in the eBay Developer Portal (Alerts & Notifications → Marketplace Account Deletion):

`https://api.comicosapp.com/api/v1/ebay/account-deletion`

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `EBAY_ACCOUNT_DELETION_VERIFICATION_TOKEN` | **Yes** (for verification) | Shared secret you choose in the eBay portal; used in the challenge hash. Never commit to git. |
| `EBAY_ACCOUNT_DELETION_ENDPOINT_URL` | Recommended | Must match the URL registered with eBay **exactly** (default: production URL above). |
| `EBAY_ACCOUNT_DELETION_COMPLIANCE_ENABLED` | No | Default `true`. Set `false` to disable the endpoint (returns 503). |
| `EBAY_API_CLIENT_ID` | For P68 readiness only | Declares eBay app client id for provider health; unrelated to deletion POST handling. |

## Verification (GET)

eBay sends:

```http
GET /api/v1/ebay/account-deletion?challenge_code=<code>
```

Response (JSON, unwrapped — not the Scan v1 envelope):

```json
{ "challengeResponse": "<sha256-hex>" }
```

`challengeResponse` = SHA-256 hex digest of UTF-8 bytes: `challenge_code` + `verification_token` + `endpoint_url` (concatenated in that order, no separators).

## Notifications (POST)

eBay sends a JSON body when a marketplace user requests account deletion. ComicOS:

1. Acknowledges with HTTP 200 and `{ "status": "ok", "noop_action": "acknowledged_no_user_data_retained" }`
2. Persists a **no-op** row in `ebay_account_deletion_audit_log` (notification id + payload digest only — no username, userId, or eiasToken stored)
3. Does **not** delete or mutate ComicOS user data automatically (ComicOS does not map eBay accounts to local users in this flow)

## Audit table

`ebay_account_deletion_audit_log` columns: `event_kind`, `external_notification_id`, `payload_digest`, `noop_action`, `created_at`.

## Ops checklist

1. Set `EBAY_ACCOUNT_DELETION_VERIFICATION_TOKEN` on the API host (Render: `comic-os-api` env).
2. Confirm `EBAY_ACCOUNT_DELETION_ENDPOINT_URL` matches the portal URL character-for-character.
3. Deploy API and run DB migration `20260605_0231`.
4. Save the notification endpoint in eBay Developer Portal; complete the challenge verification.
5. Optionally send a test notification from the portal and confirm a new audit row.

## Out of scope (explicit)

- P70 / live sold listing integration
- Storing eBay OAuth secrets in the database
- Automatic GDPR-style erasure tied to eBay `userId`
