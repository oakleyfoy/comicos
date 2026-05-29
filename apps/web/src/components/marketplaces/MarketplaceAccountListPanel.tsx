import type { MarketplaceAccountResponse, MarketplaceRegistryEntryResponse } from "../../api/client";
import { EmptyState } from "../EmptyState";
import { MarketplaceAccountStatusBadge } from "./MarketplaceAccountStatusBadge";
import { MarketplaceVerificationStatusBadge } from "./MarketplaceVerificationStatusBadge";

interface MarketplaceAccountListPanelProps {
  accounts: MarketplaceAccountResponse[];
  registry: MarketplaceRegistryEntryResponse[];
  canManage: boolean;
  busyActionKey: string | null;
  onVerify: (accountId: number, verificationStatus: "verified" | "failed") => Promise<void>;
  onDisconnect: (accountId: number) => Promise<void>;
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "—";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function MarketplaceAccountListPanel({
  accounts,
  registry,
  canManage,
  busyActionKey,
  onVerify,
  onDisconnect,
}: MarketplaceAccountListPanelProps): JSX.Element {
  const registryLabels = registry.reduce<Record<string, string>>((accumulator, entry) => {
    accumulator[entry.marketplace_key] = entry.display_name;
    return accumulator;
  }, {});

  if (!accounts.length) {
    return (
      <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
        <EmptyState
          title="No marketplace accounts yet"
          description="Once connected, marketplace identities, verification state, and append-only lineage will appear here in deterministic order."
        />
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-white">Marketplace registry</h2>
          <p className="mt-1 text-sm text-slate-400">Backend-authoritative account status, verification state, and org-scoped ownership.</p>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-slate-300">
          {accounts.length} account{accounts.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="mt-5 space-y-4">
        {accounts.map((account) => {
          const verifyKey = `verify:${account.id}`;
          const failKey = `fail:${account.id}`;
          const disconnectKey = `disconnect:${account.id}`;
          return (
            <article key={account.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-white">{account.display_name}</h3>
                    <MarketplaceAccountStatusBadge status={account.account_status} />
                    <MarketplaceVerificationStatusBadge status={account.verification_status} />
                  </div>
                  <p className="mt-2 text-sm text-slate-400">
                    {registryLabels[account.marketplace_type] ?? account.marketplace_type} · identity `{account.marketplace_account_id}`
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={!canManage || busyActionKey !== null}
                    onClick={() => void onVerify(account.id, "verified")}
                    className="rounded-xl border border-cyan-400/30 px-3 py-2 text-sm font-semibold text-cyan-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busyActionKey === verifyKey ? "Verifying..." : "Mark verified"}
                  </button>
                  <button
                    type="button"
                    disabled={!canManage || busyActionKey !== null}
                    onClick={() => void onVerify(account.id, "failed")}
                    className="rounded-xl border border-amber-400/30 px-3 py-2 text-sm font-semibold text-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busyActionKey === failKey ? "Updating..." : "Mark failed"}
                  </button>
                  <button
                    type="button"
                    disabled={!canManage || busyActionKey !== null || account.account_status === "disconnected"}
                    onClick={() => void onDisconnect(account.id)}
                    className="rounded-xl border border-rose-400/30 px-3 py-2 text-sm font-semibold text-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busyActionKey === disconnectKey ? "Disconnecting..." : account.account_status === "disconnected" ? "Disconnected" : "Disconnect"}
                  </button>
                </div>
              </div>
              <dl className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-3">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Connected</dt>
                  <dd className="mt-2">{formatDateTime(account.connected_at)}</dd>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-3">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Disconnected</dt>
                  <dd className="mt-2">{formatDateTime(account.disconnected_at)}</dd>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-3">
                  <dt className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Created</dt>
                  <dd className="mt-2">{formatDateTime(account.created_at)}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </div>
    </section>
  );
}
