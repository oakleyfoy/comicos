import { useState } from "react";

import type { OrganizationInvitationResponse } from "../../api/client";

export function OrganizationInvitePanel({
  submitting,
  lastInvitation,
  onInvite,
  disabled = false,
  disabledMessage = "You do not have permission to invite members.",
}: {
  submitting: boolean;
  lastInvitation: OrganizationInvitationResponse | null;
  onInvite: (email: string) => Promise<void>;
  disabled?: boolean;
  disabledMessage?: string;
}): JSX.Element {
  const [email, setEmail] = useState("staff@example.com");

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Invitation shell</p>
        <h2 className="mt-1 text-lg font-semibold text-white">Invite a member</h2>
        <p className="mt-1 text-sm text-slate-400">Notifications and delivery workflows arrive in a later phase. This shell only creates deterministic invitation records.</p>
      </div>
      <div className="mt-4 flex flex-col gap-3 md:flex-row">
        <input
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="member@example.com"
          className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-white outline-none focus:border-fuchsia-400/50"
        />
        <button
          type="button"
          disabled={submitting || disabled}
          onClick={() => void onInvite(email)}
          className="rounded-2xl bg-fuchsia-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-fuchsia-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Inviting..." : "Create invitation"}
        </button>
      </div>
      {disabled ? <p className="mt-3 text-sm text-slate-400">{disabledMessage}</p> : null}
      {lastInvitation ? (
        <div className="mt-4 rounded-2xl border border-fuchsia-400/25 bg-fuchsia-500/10 p-4 text-sm text-fuchsia-100">
          <p className="font-semibold">Latest invitation token</p>
          <p className="mt-2 break-all font-mono text-xs">{lastInvitation.invitation_token}</p>
          <p className="mt-2 text-fuchsia-50/90">
            {lastInvitation.email} • {lastInvitation.status} • expires {new Date(lastInvitation.expires_at).toLocaleString()}
          </p>
        </div>
      ) : null}
    </section>
  );
}
