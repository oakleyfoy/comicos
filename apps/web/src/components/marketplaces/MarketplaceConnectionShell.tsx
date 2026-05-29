import { type FormEvent, useMemo, useState } from "react";

import type { MarketplaceAccountConnectRequest, MarketplaceRegistryEntryResponse } from "../../api/client";

interface MarketplaceConnectionShellProps {
  registry: MarketplaceRegistryEntryResponse[];
  canManage: boolean;
  submitting: boolean;
  onConnect: (payload: MarketplaceAccountConnectRequest) => Promise<void>;
}

export function MarketplaceConnectionShell({
  registry,
  canManage,
  submitting,
  onConnect,
}: MarketplaceConnectionShellProps): JSX.Element {
  const [marketplaceType, setMarketplaceType] = useState(registry[0]?.marketplace_key ?? "ebay");
  const [marketplaceAccountId, setMarketplaceAccountId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [credentialType, setCredentialType] = useState("oauth_token");
  const [credentialReference, setCredentialReference] = useState("");

  const selectedRegistryEntry = useMemo(
    () => registry.find((entry) => entry.marketplace_key === marketplaceType) ?? registry[0] ?? null,
    [marketplaceType, registry],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage || submitting) {
      return;
    }
    await onConnect({
      marketplace_type: marketplaceType,
      marketplace_account_id: marketplaceAccountId.trim(),
      display_name: displayName.trim(),
      credential_type: credentialType.trim(),
      credential_reference: credentialReference.trim(),
    });
    setMarketplaceAccountId("");
    setDisplayName("");
    setCredentialReference("");
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-white">Connect marketplace account</h2>
          <p className="mt-1 text-sm text-slate-400">
            Register the marketplace identity and external credential reference without calling live marketplace APIs.
          </p>
        </div>
        <span className="rounded-full border border-sky-400/25 bg-sky-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-100">
          P43-01
        </span>
      </div>
      <form className="mt-5 space-y-4" onSubmit={(event) => void handleSubmit(event)}>
        <label className="block text-xs text-slate-400">
          Marketplace
          <select
            className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
            value={marketplaceType}
            onChange={(event) => setMarketplaceType(event.target.value)}
            disabled={!canManage || submitting}
          >
            {registry.map((entry) => (
              <option key={entry.marketplace_key} value={entry.marketplace_key}>
                {entry.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs text-slate-400">
          Marketplace account ID
          <input
            className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
            value={marketplaceAccountId}
            onChange={(event) => setMarketplaceAccountId(event.target.value)}
            disabled={!canManage || submitting}
            placeholder="seller-123"
            required
          />
        </label>
        <label className="block text-xs text-slate-400">
          Display name
          <input
            className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            disabled={!canManage || submitting}
            placeholder="Primary eBay account"
            required
          />
        </label>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="block text-xs text-slate-400">
            Credential type
            <input
              className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              value={credentialType}
              onChange={(event) => setCredentialType(event.target.value)}
              disabled={!canManage || submitting}
            />
          </label>
          <label className="block text-xs text-slate-400">
            Credential reference
            <input
              className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"
              value={credentialReference}
              onChange={(event) => setCredentialReference(event.target.value)}
              disabled={!canManage || submitting}
              placeholder="vault://marketplace/ebay-primary"
              required
            />
          </label>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4 text-xs text-slate-300">
          <p className="font-semibold text-white">Registry capabilities</p>
          <p className="mt-2 text-slate-400">{selectedRegistryEntry?.display_name ?? "Marketplace"} remains foundation-only in this phase.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(selectedRegistryEntry?.capability_flags ?? []).map((flag) => (
              <span key={flag} className="rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-slate-200">
                {flag}
              </span>
            ))}
          </div>
        </div>
        <button
          type="submit"
          disabled={!canManage || submitting || !registry.length}
          className="rounded-xl bg-violet-500 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Connecting..." : "Connect marketplace"}
        </button>
      </form>
    </section>
  );
}
