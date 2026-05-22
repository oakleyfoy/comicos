# Gmail OAuth Setup

This guide prepares local Gmail receipt ingestion for testing without changing the import confirm boundary.

Important:

- Gmail email sync creates `DraftImport` records only.
- Gmail email sync never creates inventory automatically.
- `POST /imports/{id}/confirm` remains the only path that creates orders and inventory.

## Google Cloud Project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing development project for ComicOS.
3. Make sure billing and organization requirements are satisfied for your environment if Google prompts for them.

## Enable Gmail API

1. In the selected Google Cloud project, open `APIs & Services`.
2. Click `Enable APIs and Services`.
3. Search for `Gmail API`.
4. Enable it for the project.

## OAuth Consent Screen

1. Open `APIs & Services` > `OAuth consent screen`.
2. Choose the app type that fits your environment, usually `External` for local development.
3. Fill in the basic app information Google requires:
   - app name
   - support email
   - developer contact email
4. Save the consent screen configuration.

If the app is still in Google `Testing` mode:

- only listed test users can complete the OAuth flow
- add the Gmail account you want to use for local testing as a test user

## Create OAuth Client Credentials

1. Open `APIs & Services` > `Credentials`.
2. Click `Create Credentials` > `OAuth client ID`.
3. Choose `Web application`.
4. Add the local redirect URI:

```text
http://127.0.0.1:8000/gmail/connect/callback
```

5. Save the client and copy the generated client ID and client secret.

## Required Environment Variables

Set these in the repo root `.env` or `apps/api/.env`:

```text
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/gmail/connect/callback
DEBUG_RUNTIME=false
```

These values are required for:

- `GET /gmail/connect/start`
- `GET /gmail/connect/callback`
- `POST /gmail/sync`

The OAuth authorization request must include:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/gmail.readonly`

If Gmail sync fails with `Request had insufficient authentication scopes.`, disconnect the existing Gmail connection and reconnect through `/settings/integrations` so Google issues a fresh token with the Gmail readonly scope.

## Local Runtime Example

Start the local runtime before testing Gmail:

```bash
npm run kill:dev
npm run db:up
npm run redis:up
npm run db:migrate
npm run dev
npm run dev:worker:local
```

Then:

1. Sign in to the app.
2. Open `/settings/integrations`.
3. Connect Gmail.
4. Open `/imports/email`.
5. Run `Sync Gmail`.

## API Port Sanity Check Before OAuth Testing

Before starting a real local OAuth test:

1. Set `DEBUG_RUNTIME=true` in your local backend env.
2. Restart the API process.
3. Open `http://127.0.0.1:8000/debug/runtime`.
4. Confirm the reported `pid`, `cwd`, masked database URL, and masked Redis URL match the repo and local runtime you expect.
5. Set `DEBUG_RUNTIME=false` again when you are done debugging runtime identity.

The `/debug/runtime` endpoint is intentionally unavailable unless `DEBUG_RUNTIME=true`.

## Behavior Reminder

Even after Gmail is connected successfully:

- supported email receipts are parsed into draft imports only
- imported drafts still require manual review
- inventory is never created automatically from Gmail sync
- confirm remains a separate explicit action
