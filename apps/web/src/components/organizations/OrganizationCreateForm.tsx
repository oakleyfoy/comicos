import { useState } from "react";

import type { OrganizationCreateRequest } from "../../api/client";

export function OrganizationCreateForm({
  submitting,
  onSubmit,
}: {
  submitting: boolean;
  onSubmit: (payload: OrganizationCreateRequest) => Promise<void>;
}): JSX.Element {
  const [displayName, setDisplayName] = useState("Northside Comics");
  const [slug, setSlug] = useState("northside-comics");
  const [organizationType, setOrganizationType] = useState("DEALER");

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Organization setup</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Create dealer foundation</h2>
        <p className="mt-1 text-sm text-slate-400">
          This phase only establishes identity, membership, invitation, and audit lineage contracts.
        </p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label className="space-y-2 text-sm text-slate-300">
          <span>Display name</span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-white outline-none focus:border-fuchsia-400/50"
          />
        </label>
        <label className="space-y-2 text-sm text-slate-300">
          <span>Slug</span>
          <input
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-white outline-none focus:border-fuchsia-400/50"
          />
        </label>
        <label className="space-y-2 text-sm text-slate-300">
          <span>Type</span>
          <select
            value={organizationType}
            onChange={(event) => setOrganizationType(event.target.value)}
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-white outline-none focus:border-fuchsia-400/50"
          >
            <option value="DEALER">Dealer</option>
            <option value="COLLECTOR">Collector</option>
            <option value="INTERNAL">Internal</option>
          </select>
        </label>
      </div>
      <button
        type="button"
        disabled={submitting}
        onClick={() =>
          void onSubmit({
            display_name: displayName,
            slug,
            organization_type: organizationType,
          })
        }
        className="mt-4 rounded-2xl bg-fuchsia-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-fuchsia-400 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Creating..." : "Create organization"}
      </button>
    </section>
  );
}
