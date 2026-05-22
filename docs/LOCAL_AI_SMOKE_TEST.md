# Local AI Smoke Test

Use this checklist to run a local AI import smoke test after configuring the backend.

## Setup
1. Put `OPENAI_API_KEY` in one of these files:
   - `apps/api/.env`
   - repo root `.env`
2. Make sure `SECRET_KEY` is also set there and is at least 32 bytes long.
3. Restart the backend after adding or changing environment variables.

Example:

```bash
cd apps/api
uvicorn app.main:app --reload
```

Or from the repo root:

```bash
npm run dev
```

## Smoke Test Steps
1. Run `npm run dev` from the repo root if the app is not already running.
2. Open `http://127.0.0.1:5173/orders/import`.
3. Paste the sample text from `docs/sample_order_texts/whatnot_sample.txt`.
4. Click `Parse and Save Draft`.
5. Review the parsed draft, warnings, and confidence score.
6. Click `Confirm Import and Create Order`.
7. Open `http://127.0.0.1:5173/imports` and verify the import shows as `confirmed` with a linked order.
8. Open the linked order and verify it exists.
9. Open `http://127.0.0.1:5173/dashboard` and verify inventory increased after the confirmed import.

## Expected Behavior
- AI parsing works only when `OPENAI_API_KEY` is present.
- The draft can be reviewed and edited before confirmation.
- Inventory is created only when the import is confirmed.
- The confirmed import remains visible in `/imports` with a linked order.
