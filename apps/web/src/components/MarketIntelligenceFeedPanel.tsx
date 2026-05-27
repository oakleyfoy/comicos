import { memo } from "react";
import { Link } from "react-router-dom";

import { type MarketFeedPanelMode, useMarketFeed } from "../hooks/useMarketFeed";
import { StatusBanner } from "./StatusBanner";

function shortenChecksum(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function severityTone(severity: string): string {
  switch (severity.toUpperCase()) {
    case "CRITICAL":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "WARNING":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    default:
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
  }
}

function FeedEventRow(props: { event: ReturnType<typeof useMarketFeed>["latestEvent"] | null }): JSX.Element | null {
  const event = props.event;
  if (!event) {
    return null;
  }
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Latest event</p>
          <p className="mt-1 text-base font-semibold text-white">{event.event_type.replace(/_/g, " ")}</p>
          <p className="mt-1 text-sm text-slate-400">
            Sequence #{event.event_sequence_id} · {formatDateTime(event.created_at)}
          </p>
        </div>
        <span className={`inline-flex rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${severityTone(event.severity)}`}>
          {event.severity}
        </span>
      </div>
      <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
        <p>
          Checksum: <span className="font-mono text-slate-200">{shortenChecksum(event.event_checksum)}</span>
        </p>
        <p>Snapshot date: {formatDate(event.snapshot_date)}</p>
      </div>
    </div>
  );
}

function FeedRows(props: {
  rows: Array<{
    id: number;
    event_sequence_id: number;
    event_type: string;
    severity: string;
    snapshot_date: string;
    event_checksum: string;
    created_at: string;
  }>;
}): JSX.Element {
  return (
    <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/45">
      <table className="w-full border-collapse text-left text-xs">
        <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
          <tr>
            <th className="p-3 font-medium">Seq</th>
            <th className="p-3 font-medium">Event</th>
            <th className="p-3 font-medium">Severity</th>
            <th className="p-3 font-medium">Snapshot date</th>
            <th className="p-3 font-medium">Checksum</th>
            <th className="p-3 font-medium">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10 text-slate-200">
          {props.rows.length === 0 ? (
            <tr>
              <td className="p-4 text-slate-500" colSpan={6}>
                No feed events available yet.
              </td>
            </tr>
          ) : null}
          {props.rows.map((row) => (
            <tr key={row.id}>
              <td className="p-3 font-mono text-[11px]">{row.event_sequence_id}</td>
              <td className="p-3">{row.event_type.replace(/_/g, " ")}</td>
              <td className="p-3">
                <span
                  className={`inline-flex rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${severityTone(
                    row.severity,
                  )}`}
                >
                  {row.severity}
                </span>
              </td>
              <td className="p-3 text-slate-400">{formatDate(row.snapshot_date)}</td>
              <td className="p-3 font-mono text-[11px] text-slate-400">{shortenChecksum(row.event_checksum)}</td>
              <td className="p-3 text-slate-400">{formatDateTime(row.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Props = {
  ownerUserId?: number;
  mode?: MarketFeedPanelMode;
};

function MarketIntelligenceFeedPanelInner({ ownerUserId, mode = "dashboard" }: Props): JSX.Element | null {
  const { state, reload, latestEvent, latestSnapshot } = useMarketFeed(ownerUserId, mode);

  if (!ownerUserId) {
    return null;
  }

  const eventCount = state.events?.pagination.total_count ?? 0;
  const snapshotCount = state.snapshots?.pagination.total_count ?? 0;
  const warningCount =
    state.events?.items.filter((item) => item.severity.toUpperCase() === "WARNING" || item.severity.toUpperCase() === "CRITICAL")
      .length ?? 0;
  const latestEventType = latestEvent?.event_type.replace(/_/g, " ") ?? "—";
  const latestSnapshotChecksum = latestSnapshot?.snapshot_checksum ?? null;

  if (mode === "teaser") {
    return (
      <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
        {state.error ? <StatusBanner tone="warning">{state.error}</StatusBanner> : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">P39 feed</p>
            <p className="mt-1 text-sm font-semibold text-white">{latestEventType}</p>
            <p className="mt-1 text-xs text-slate-400">
              {eventCount} events · latest snapshot {latestSnapshot ? `#${latestSnapshot.id}` : "—"}
            </p>
          </div>
          <span className="rounded-full border border-white/10 px-2 py-1 font-mono text-[11px] text-slate-300">
            {shortenChecksum(latestSnapshotChecksum)}
          </span>
        </div>
      </div>
    );
  }

  return (
    <section
      id="market-feed"
      className={
        mode === "ops"
          ? "mt-6 rounded-3xl border border-emerald-500/25 bg-slate-950/45 p-5 shadow-xl shadow-black/15"
          : "mt-6 rounded-3xl border border-cyan-400/25 bg-cyan-950/12 p-5 shadow-xl shadow-black/15"
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className={`text-[11px] uppercase tracking-[0.16em] ${mode === "ops" ? "text-emerald-200/70" : "text-cyan-200/70"}`}>
            Market feed (P39-09)
          </p>
          <h2 className="mt-1 text-lg font-semibold text-white">
            {mode === "ops" ? "Feed timeline, replay anchors & snapshot history" : "Append-only feed summary"}
          </h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">
            Deterministic event stream derived from the P39 stage engines. The feed is append-only, replay-safe, and queryable
            without mutating upstream snapshots.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/ops#market-feed"
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
              mode === "ops"
                ? "border-emerald-400/35 text-emerald-100 hover:border-emerald-300/60 hover:bg-emerald-500/10"
                : "border-cyan-400/35 text-cyan-100 hover:border-cyan-300/60 hover:bg-cyan-500/10"
            }`}
          >
            Ops view
          </Link>
          <button
            type="button"
            className="rounded-full border border-white/15 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-white/30 hover:bg-white/5"
            onClick={() => {
              void reload();
            }}
          >
            Refresh feed
          </button>
        </div>
      </div>

      {state.loading ? (
        <div className="mt-4 animate-pulse space-y-3">
          <div className="h-4 w-56 rounded-lg bg-white/10" />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={`feed-skel-${index}`} className="h-20 rounded-2xl bg-white/10" />
            ))}
          </div>
        </div>
      ) : null}

      {!state.loading && state.error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{state.error}</StatusBanner>
        </div>
      ) : null}

      {!state.loading && !state.error && state.events && state.snapshots ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Feed events" value={String(eventCount)} />
            <StatCard label="Snapshots" value={String(snapshotCount)} />
            <StatCard label="Warnings / critical" value={String(warningCount)} />
            <StatCard label="Latest event" value={latestEventType} />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
            <div className="space-y-4">
              <FeedEventRow event={latestEvent} />
              <FeedRows rows={state.events.items.slice(0, mode === "ops" ? 10 : 5)} />
            </div>
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Latest snapshot</p>
                <p className="mt-1 text-base font-semibold text-white">#{latestSnapshot?.id ?? "—"}</p>
                <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-400">
                  <p>Total events: {latestSnapshot?.total_events ?? "—"}</p>
                  <p>Sequence: {latestSnapshot?.latest_event_sequence_id ?? "—"}</p>
                  <p>Snapshot date: {latestSnapshot ? formatDate(latestSnapshot.snapshot_date) : "—"}</p>
                  <p className="font-mono">Checksum: {shortenChecksum(latestSnapshot?.snapshot_checksum ?? null)}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">Event counts</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(latestSnapshot?.event_type_counts_json ?? {}).map(([key, value]) => (
                    <span
                      key={key}
                      className="rounded-full border border-white/10 bg-white/5 px-2 py-1 font-mono text-[11px] text-slate-300"
                    >
                      {key.replace(/_/g, " ")}: {String(value)}
                    </span>
                  ))}
                  {Object.keys(latestSnapshot?.event_type_counts_json ?? {}).length === 0 ? (
                    <span className="text-xs text-slate-500">No counts yet.</span>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

export const MarketIntelligenceFeedPanel = memo(MarketIntelligenceFeedPanelInner);
