import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type {
  MarketplaceAccountResponse,
  MarketplaceEventIngestRequest,
} from "../../../api/client";

export function MarketplaceEventIngestShell({
  accounts,
  canManage,
  submitting,
  onSubmit,
}: {
  accounts: MarketplaceAccountResponse[];
  canManage: boolean;
  submitting: boolean;
  onSubmit: (payload: MarketplaceEventIngestRequest) => Promise<void>;
}): JSX.Element {
  const defaultAccountId = accounts[0]?.id ?? 0;
  const [marketplaceAccountId, setMarketplaceAccountId] = useState(String(defaultAccountId));
  const [externalEventIdentifier, setExternalEventIdentifier] = useState("");
  const [eventType, setEventType] = useState("listing_created");
  const [receivedAt, setReceivedAt] = useState("");
  const [payloadJson, setPayloadJson] = useState('{"source":"manual_test"}');
  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => {
    if (defaultAccountId > 0) {
      setMarketplaceAccountId(String(defaultAccountId));
    }
  }, [defaultAccountId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    let parsedPayload: Record<string, unknown>;
    try {
      parsedPayload = JSON.parse(payloadJson) as Record<string, unknown>;
      setJsonError(null);
    } catch {
      setJsonError("Event payload must be valid JSON.");
      return;
    }
    await onSubmit({
      marketplace_account_id: Number(marketplaceAccountId),
      external_event_identifier: externalEventIdentifier.trim(),
      event_type: eventType.trim(),
      event_payload_json: parsedPayload,
      received_at: receivedAt.trim() ? new Date(receivedAt).toISOString() : null,
    });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Event ingest shell</p>
          <h2 className="mt-1 text-base font-semibold text-white">Create a replay-safe marketplace event</h2>
        </div>
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">No public webhook URLs</p>
      </div>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Marketplace account</span>
          <select
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={marketplaceAccountId}
            onChange={(event) => setMarketplaceAccountId(event.target.value)}
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.display_name}
              </option>
            ))}
          </select>
        </label>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">External event identifier</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={externalEventIdentifier}
              onChange={(event) => setExternalEventIdentifier(event.target.value)}
              placeholder="evt_12345"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Event type</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={eventType}
              onChange={(event) => setEventType(event.target.value)}
              placeholder="listing_created"
            />
          </label>
        </div>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Received at</span>
          <input
            type="datetime-local"
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={receivedAt}
            onChange={(event) => setReceivedAt(event.target.value)}
          />
        </label>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Payload JSON</span>
          <textarea
            className="min-h-[180px] rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 font-mono text-xs text-slate-100"
            value={payloadJson}
            onChange={(event) => setPayloadJson(event.target.value)}
          />
        </label>
        {jsonError ? <p className="text-sm text-rose-300">{jsonError}</p> : null}
        <button
          type="submit"
          disabled={!canManage || submitting || accounts.length === 0}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Ingesting..." : "Ingest event"}
        </button>
      </form>
    </section>
  );
}
