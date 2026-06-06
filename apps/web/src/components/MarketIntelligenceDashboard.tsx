import { memo, useMemo } from "react";
import { Link } from "react-router-dom";

import {
  type MarketAcquisitionOpportunitySnapshotRead,
  type MarketAcquisitionScoreSnapshotRead,
  type MarketAcquisitionSignalSnapshotRead,
  type MarketNormalizationRunListResponse,
  type PortfolioMarketCouplingSnapshotRead,
} from "../api/client";
import { useMarketIntelligencePanels } from "../hooks/useMarketIntelligencePanels";
import { checksumAlignedWithEnvelope } from "../lib/marketIntelTrace";
import { MarketIntelligenceFeedPanel } from "./MarketIntelligenceFeedPanel";
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

function marketIntelPanelClass(accentBorder: string): string {
  return `mt-6 rounded-3xl border ${accentBorder} bg-slate-900/95 p-5 shadow-xl shadow-black/25`;
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-600/80 bg-slate-950 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-50">{value}</p>
    </div>
  );
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

function formatDateOnly(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function PanelSkeleton(): JSX.Element {
  return (
    <div className="mt-4 animate-pulse space-y-3">
      <div className="h-4 w-48 rounded-lg bg-white/10" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={`sk-${i}`} className="h-20 rounded-2xl bg-white/10" />
        ))}
      </div>
    </div>
  );
}

function PanelFooter(props: {
  layer: "ingestion" | "normalization" | "scoring" | "signals" | "opportunities" | "coupling";
  checksumLabel: string;
  checksum: string;
  metaNote: string;
  onRetry: () => void;
}): JSX.Element {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-600/60 pt-3 text-[11px] text-slate-400">
      <div className="space-y-1">
        <p>
          <span className="text-slate-300">{props.checksumLabel}</span>{" "}
          <span className="font-mono text-slate-100">{props.checksum}</span>
        </p>
        <p className="text-slate-400">{props.metaNote}</p>
      </div>
      <button
        type="button"
        className="rounded-full border border-white/20 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-200 transition hover:border-cyan-400/55 hover:bg-cyan-500/10"
        onClick={() => {
          void props.onRetry();
        }}
      >
        Retry {props.layer}
      </button>
    </div>
  );
}

const marketIntelOpsHashes = [
  ["ingestion", "/ops#market-ingestion-ops"],
  ["normalization", "/ops#market-normalization-ops"],
  ["scoring", "/ops#market-scoring-ops"],
  ["signals", "/ops#market-signal-ops"],
  ["opportunities", "/ops#market-opportunity-ops"],
  ["coupling", "/ops#market-portfolio-coupling-ops"],
] as const;

function normalizeHealth(norm: MarketNormalizationRunListResponse | null) {
  const health = norm?.health;
  const c = health?.candidate_status_counts ?? {};
  const succ = c.SUCCESS ?? 0;
  const part = c.PARTIAL ?? 0;
  const fail = c.FAILED ?? 0;
  const tot = succ + part + fail;
  const pctStr = (n: number): string => (tot > 0 ? `${((100 * n) / tot).toFixed(1)}%` : "—");
  const issues = health?.issue_type_counts ?? {};
  const issueRecords = Object.values(issues).reduce((a, b) => a + b, 0);
  const flags = health?.normalization_flag_counts ?? {};
  return {
    tot,
    succ,
    part,
    fail,
    successRate: pctStr(succ),
    partialRate: pctStr(part),
    failRate: pctStr(fail),
    canonicalPct: health?.canonical_full_success_rate_pct ?? null,
    issueRecords,
    missingPublisher: flags.missing_publisher ?? 0,
    ambiguousTitle: flags.ambiguous_title ?? 0,
    lastCompleted: health?.last_normalization_completed_at ?? null,
  };
}

function ScoreHistogram({ snap }: { snap: MarketAcquisitionScoreSnapshotRead | null | undefined }): JSX.Element | null {
  const segments =
    snap == null
      ? []
      : [
          { key: "STRONG_BUY", n: snap.strong_buy_count ?? 0, tone: "bg-fuchsia-500/65" },
          { key: "BUY", n: snap.buy_count ?? 0, tone: "bg-fuchsia-400/55" },
          { key: "WATCH", n: snap.watch_count ?? 0, tone: "bg-fuchsia-300/35" },
          { key: "IGNORE", n: snap.ignore_count ?? 0, tone: "bg-slate-500/55" },
        ];
  const max = Math.max(...segments.map((s) => s.n), 1);

  if (!snap || segments.every((s) => s.n === 0)) {
    return null;
  }

  return (
    <div className="mt-4">
      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">Recommendation histogram (counts)</p>
      <div className="mt-3 flex h-32 items-end gap-2 rounded-2xl border border-slate-600/70 bg-slate-950 p-3">
        {segments.map((seg) => (
          <div key={seg.key} className="flex min-w-0 flex-1 flex-col items-center gap-2">
            <div
              className={`w-full max-w-[3rem] rounded-t ${seg.tone}`}
              style={{ height: `${Math.max((seg.n / max) * 100, seg.n ? 8 : 0)}%` }}
              title={`${seg.key}: ${seg.n}`}
            />
            <p className="text-center font-mono text-[10px] text-slate-400">{seg.key.replace(/_/g, " ")}</p>
            <p className="text-xs font-semibold text-slate-100">{seg.n}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function IngestionPanel(props: {
  state: ReturnType<typeof useMarketIntelligencePanels>["panels"]["ingestion"];
  onRetry: () => void;
}): JSX.Element {
  const counts = props.state.data?.status_counts ?? {};
  const sumFailedRecords = props.state.data?.items.reduce((a, row) => a + row.failed_records, 0) ?? null;
  const chk = props.state.data?.items[0]?.batch_checksum ?? null;
  const metaOk = checksumAlignedWithEnvelope(props.state.meta, chk);

  return (
    <section className={marketIntelPanelClass("border-cyan-400/40")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-300">Market ingestion (P39-01)</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-50">Batch status & ingestion health</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-300">
            Read-only ingestion ledger summaries using the P39-07 response envelope.
          </p>
        </div>
        <Link
          to="/ops#market-ingestion-ops"
          className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100 transition hover:border-cyan-300/60 hover:bg-cyan-500/10"
        >
          Ops drill-down
        </Link>
      </div>

      {props.state.loading ? <PanelSkeleton /> : null}

      {!props.state.loading && props.state.error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{props.state.error}</StatusBanner>
          <PanelFooter
            layer="ingestion"
            checksumLabel="Latest batch checksum (page)"
            checksum="—"
            metaNote="Panel failed — checksum unavailable until reload succeeds."
            onRetry={props.onRetry}
          />
        </div>
      ) : null}

      {!props.state.loading && !props.state.error && props.state.data ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Total batches" value={String(props.state.data.pagination.total_count)} />
            <StatCard label="Failed batches" value={String(counts.FAILED ?? 0)} />
            <StatCard label="Aggregated failures (sample page)" value={String(sumFailedRecords ?? "—")} />
            <StatCard
              label="Pending batches"
              value={String((counts.PENDING ?? 0) + (counts.PROCESSING ?? 0))}
            />
            <StatCard
              label="Last ingestion"
              value={props.state.data.last_ingestion_at ? formatDateTime(props.state.data.last_ingestion_at) : "—"}
            />
          </div>
          <PanelFooter
            layer="ingestion"
            checksumLabel="First batch checksum (current page)"
            checksum={shortenChecksum(chk)}
            metaNote={
              props.state.meta?.checksum
                ? metaOk
                  ? "Envelope checksum matches anchored batch checksum."
                  : "Envelope checksum does not match the latest batch checksum on this page — treat as stale or mixed."
                : "Standard list envelope omitted meta.checksum; row checksums remain authoritative."
            }
            onRetry={props.onRetry}
          />
        </>
      ) : null}
    </section>
  );
}

const MemoIngestionPanel = memo(IngestionPanel);

function NormalizationPanel(props: {
  state: ReturnType<typeof useMarketIntelligencePanels>["panels"]["normalization"];
  onRetry: () => void;
}): JSX.Element {
  const h = normalizeHealth(props.state.data);
  return (
    <section className={marketIntelPanelClass("border-violet-400/40")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-violet-300">Normalization (P39-02)</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-50">Canonical coverage & success rate</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-300">Deterministic normalization health only — no scoring.</p>
        </div>
        <Link
          to="/ops#market-normalization-ops"
          className="rounded-full border border-violet-400/35 px-3 py-1.5 text-xs font-semibold text-violet-100 transition hover:border-violet-300/60 hover:bg-violet-500/10"
        >
          Ops drill-down
        </Link>
      </div>

      {props.state.loading ? <PanelSkeleton /> : null}

      {!props.state.loading && props.state.error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{props.state.error}</StatusBanner>
          <PanelFooter
            layer="normalization"
            checksumLabel="Checksum"
            checksum="—"
            metaNote="Panel failed — reload to restore normalization health summaries."
            onRetry={props.onRetry}
          />
        </div>
      ) : null}

      {!props.state.loading && !props.state.error && props.state.data ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Normalization runs" value={String(props.state.data.pagination.total_count)} />
            <StatCard label="Success rate (by row)" value={h.successRate} />
            <StatCard label="Partial rate" value={h.partialRate} />
            <StatCard label="Failed rate" value={h.failRate} />
            <StatCard label="Normalized rows sampled" value={String(h.tot)} />
            <StatCard
              label="Canonical success %"
              value={h.canonicalPct != null ? `${h.canonicalPct}%` : "—"}
            />
            <StatCard label="Issue rows" value={String(h.issueRecords)} />
            <StatCard label="Missing publisher flags" value={String(h.missingPublisher)} />
            <StatCard label="Ambiguous title flags" value={String(h.ambiguousTitle)} />
            <StatCard
              label="Last completed run"
              value={h.lastCompleted ? formatDateTime(h.lastCompleted) : "—"}
            />
          </div>
          <PanelFooter
            layer="normalization"
            checksumLabel="Latest run checksum (page)"
            checksum={shortenChecksum(props.state.data.items[0]?.run_checksum ?? null)}
            metaNote="Compare run checksums in ops when reconciling replay boundaries."
            onRetry={props.onRetry}
          />
        </>
      ) : null}
    </section>
  );
}

const MemoNormalizationPanel = memo(NormalizationPanel);

function ScoringPanel(props: {
  state: ReturnType<typeof useMarketIntelligencePanels>["panels"]["scoring"];
  onRetry: () => void;
}): JSX.Element {
  const snap = props.state.data?.items[0];
  const chkMetaOk = checksumAlignedWithEnvelope(props.state.meta, snap?.checksum ?? null);
  return (
    <section className={marketIntelPanelClass("border-fuchsia-400/40")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-fuchsia-300">Scoring (P39-03)</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-50">Score distribution</h2>
        </div>
        <Link
          to="/ops#market-scoring-ops"
          className="rounded-full border border-fuchsia-400/35 px-3 py-1.5 text-xs font-semibold text-fuchsia-100 transition hover:border-fuchsia-300/60 hover:bg-fuchsia-500/10"
        >
          Ops drill-down
        </Link>
      </div>

      {props.state.loading ? <PanelSkeleton /> : null}

      {!props.state.loading && props.state.error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{props.state.error}</StatusBanner>
          <PanelFooter layer="scoring" checksumLabel="Checksum" checksum="—" metaNote="" onRetry={props.onRetry} />
        </div>
      ) : null}

      {!props.state.loading && !props.state.error ? (
        <>
          {snap ? (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="STRONG BUY" value={String(snap.strong_buy_count ?? 0)} />
                <StatCard label="BUY" value={String(snap.buy_count ?? 0)} />
                <StatCard label="WATCH" value={String(snap.watch_count ?? 0)} />
                <StatCard label="IGNORE" value={String(snap.ignore_count ?? 0)} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Avg acquisition score" value={snap.avg_score ?? "—"} />
                <StatCard label="Avg liquidity score" value={snap.avg_liquidity_score ?? "—"} />
                <StatCard label="Portfolio alignment score" value={snap.portfolio_alignment_score ?? "—"} />
                <StatCard label="Snapshot date" value={snap.snapshot_date ? formatDateOnly(snap.snapshot_date) : "—"} />
              </div>
              <ScoreHistogram snap={snap} />
              <PanelFooter
                layer="scoring"
                checksumLabel="Snapshot checksum"
                checksum={shortenChecksum(snap.checksum)}
                metaNote={
                  props.state.meta?.checksum
                    ? chkMetaOk
                      ? "Envelope checksum matches latest snapshot checksum."
                      : "Envelope checksum diverges — do not treat mixed payloads as one snapshot boundary."
                    : "Snapshot list aggregation omits meta.checksum; rely on snapshot row checksum."
                }
                onRetry={props.onRetry}
              />
            </>
          ) : (
            <p className="mt-4 text-sm text-slate-300">No scoring snapshots yet for this workspace.</p>
          )}
        </>
      ) : null}
    </section>
  );
}

const MemoScoringPanel = memo(ScoringPanel);

function SignalsPanel(props: {
  state: ReturnType<typeof useMarketIntelligencePanels>["panels"]["signals"];
  onRetry: () => void;
}): JSX.Element {
  const snap = props.state.data?.items[0] as MarketAcquisitionSignalSnapshotRead | undefined;
  const metaOk = checksumAlignedWithEnvelope(props.state.meta, snap?.checksum ?? null);
  const typeDistribution = snap
    ? [
        ["VALUE_DISLOCATION", snap.value_dislocation_count],
        ["LIQUIDITY_OPPORTUNITY", snap.liquidity_opportunity_count],
        ["PORTFOLIO_GAP_FILL", snap.portfolio_gap_fill_count],
        ["CONCENTRATION_REDUCTION", snap.concentration_reduction_count],
        ["GRADING_UPSIDE", snap.grading_upside_count],
        ["REDUNDANT_ASSET", snap.redundant_asset_count],
        ["HIGH_RISK_ASSET", snap.high_risk_asset_count],
      ] as const
    : [];

  return (
    <section className={marketIntelPanelClass("border-amber-400/40")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-amber-300">Signals (P39-04)</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-50">Signal type & strength breakdown</h2>
        </div>
        <Link
          to="/ops#market-signal-ops"
          className="rounded-full border border-amber-400/35 px-3 py-1.5 text-xs font-semibold text-amber-100 transition hover:border-amber-300/60 hover:bg-amber-500/10"
        >
          Ops drill-down
        </Link>
      </div>

      {props.state.loading ? <PanelSkeleton /> : null}

      {!props.state.loading && props.state.error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{props.state.error}</StatusBanner>
          <PanelFooter layer="signals" checksumLabel="Checksum" checksum="—" metaNote="" onRetry={props.onRetry} />
        </div>
      ) : null}

      {!props.state.loading && !props.state.error ? (
        <>
          {snap ? (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
                {typeDistribution.map(([label, n]) => (
                  <StatCard key={label} label={label.replace(/_/g, " ")} value={String(n ?? 0)} />
                ))}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Elite" value={String(snap.elite_signal_count ?? 0)} />
                <StatCard label="High" value={String(snap.high_signal_count ?? 0)} />
                <StatCard label="Medium" value={String(snap.medium_signal_count ?? 0)} />
                <StatCard label="Low" value={String(snap.low_signal_count ?? 0)} />
              </div>
              <PanelFooter
                layer="signals"
                checksumLabel="Snapshot checksum"
                checksum={shortenChecksum(snap.checksum)}
                metaNote={
                  props.state.meta?.checksum
                    ? metaOk
                      ? "Envelope checksum matches latest signal snapshot checksum."
                      : "Checksum mismatch versus envelope — snapshots may belong to mixed reads."
                    : "List aggregation exposes row checksum without envelope anchor."
                }
                onRetry={props.onRetry}
              />
            </>
          ) : (
            <p className="mt-4 text-sm text-slate-300">No signal snapshots yet.</p>
          )}
        </>
      ) : null}
    </section>
  );
}

const MemoSignalsPanel = memo(SignalsPanel);

function OpportunitiesPanel(props: {
  state: ReturnType<typeof useMarketIntelligencePanels>["panels"]["opportunities"];
  onRetry: () => void;
}): JSX.Element {
  const snap = props.state.data?.items[0] as MarketAcquisitionOpportunitySnapshotRead | undefined;
  const metaOk = checksumAlignedWithEnvelope(props.state.meta, snap?.snapshot_checksum ?? null);
  const classLabel = snap?.opportunity_classification?.replace(/_/g, " ") ?? "—";
  const isEliteTier = /\bELITE\b/i.test(snap?.opportunity_classification ?? "");
  const isStrongTier = /\bSTRONG\b/i.test(snap?.opportunity_classification ?? "");
  const isModerateTier = /\bMODERATE\b/i.test(snap?.opportunity_classification ?? "");

  return (
    <section className={marketIntelPanelClass("border-lime-400/40")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-lime-300">Opportunities (P39-05)</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-50">Tiered opportunity snapshot</h2>
        </div>
        <Link
          to="/ops#market-opportunity-ops"
          className="rounded-full border border-lime-400/35 px-3 py-1.5 text-xs font-semibold text-lime-100 transition hover:border-lime-300/60 hover:bg-lime-500/10"
        >
          Ops drill-down
        </Link>
      </div>

      {props.state.loading ? <PanelSkeleton /> : null}

      {!props.state.loading && props.state.error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{props.state.error}</StatusBanner>
          <PanelFooter layer="opportunities" checksumLabel="Checksum" checksum="—" metaNote="" onRetry={props.onRetry} />
        </div>
      ) : null}

      {!props.state.loading && !props.state.error ? (
        <>
          {snap ? (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Rollup classification" value={classLabel} />
                <StatCard label="ELITE-tier snapshot" value={isEliteTier ? "Yes" : "No"} />
                <StatCard label="STRONG-tier snapshot" value={isStrongTier ? "Yes" : "No"} />
                <StatCard label="MODERATE-tier snapshot" value={isModerateTier ? "Yes" : "No"} />
                <StatCard label="Total candidates" value={String(snap.total_candidates ?? 0)} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <StatCard label="Portfolio gap coverage est." value={snap.estimated_portfolio_gap_coverage ?? "—"} />
                <StatCard label="Liquidity gain est." value={snap.estimated_liquidity_gain ?? "—"} />
                <StatCard label="Diversification gain est." value={snap.estimated_diversification_gain ?? "—"} />
                <StatCard label="Risk adjustment est." value={snap.estimated_risk_adjustment ?? "—"} />
                <StatCard label="Moderate-tier signal mass" value={String(snap.medium_signal_count ?? 0)} />
              </div>
              <PanelFooter
                layer="opportunities"
                checksumLabel="Snapshot checksum"
                checksum={shortenChecksum(snap.snapshot_checksum)}
                metaNote={
                  props.state.meta?.checksum
                    ? metaOk
                      ? "Envelope checksum matches rollup snapshot_checksum."
                      : "Checksum divergence — verify via ops snapshot trace."
                    : "Opportunity list responses omit anchored envelope checksum."
                }
                onRetry={props.onRetry}
              />
            </>
          ) : (
            <p className="mt-4 text-sm text-slate-300">No opportunity snapshots yet.</p>
          )}
        </>
      ) : null}
    </section>
  );
}

const MemoOpportunitiesPanel = memo(OpportunitiesPanel);

function CouplingPanel(props: {
  state: ReturnType<typeof useMarketIntelligencePanels>["panels"]["coupling"];
  onRetry: () => void;
}): JSX.Element {
  const snap = props.state.data?.items[0] as PortfolioMarketCouplingSnapshotRead | undefined;
  const metaOk = checksumAlignedWithEnvelope(props.state.meta, snap?.snapshot_checksum ?? null);

  return (
    <section className={marketIntelPanelClass("border-sky-400/40")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-sky-300">Coupling (P39-06)</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-50">Portfolio-market alignment bridge</h2>
        </div>
        <Link
          to="/ops#market-portfolio-coupling-ops"
          className="rounded-full border border-sky-400/35 px-3 py-1.5 text-xs font-semibold text-sky-100 transition hover:border-sky-300/60 hover:bg-sky-500/10"
        >
          Ops drill-down
        </Link>
      </div>

      {props.state.loading ? <PanelSkeleton /> : null}

      {!props.state.loading && props.state.error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{props.state.error}</StatusBanner>
          <PanelFooter layer="coupling" checksumLabel="Checksum" checksum="—" metaNote="" onRetry={props.onRetry} />
        </div>
      ) : null}

      {!props.state.loading && !props.state.error ? (
        <>
          {snap ? (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <StatCard label="Alignment score" value={snap.portfolio_market_alignment_score ?? "—"} />
                <StatCard label="Misaligned opportunities (conflicts)" value={String(snap.misaligned_opportunity_count ?? 0)} />
                <StatCard label="High-fit items" value={String(snap.high_fit_market_items ?? 0)} />
                <StatCard label="Low-fit items" value={String(snap.low_fit_market_items ?? 0)} />
                <StatCard label="Liquidity alignment" value={snap.liquidity_gap_alignment_score ?? "—"} />
                <StatCard label="Diversification gap alignment" value={snap.diversification_gap_alignment_score ?? "—"} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Edge coverage (signals)" value={snap.signal_coverage_ratio ?? "—"} />
                <StatCard label="Edge coverage (scores)" value={snap.scoring_coverage_ratio ?? "—"} />
                <StatCard label="Edge coverage (normalization)" value={snap.normalization_coverage_ratio ?? "—"} />
                <StatCard label="Snapshot date" value={snap.snapshot_date ? formatDateOnly(snap.snapshot_date) : "—"} />
              </div>
              <PanelFooter
                layer="coupling"
                checksumLabel="Snapshot checksum"
                checksum={shortenChecksum(snap.snapshot_checksum)}
                metaNote={
                  props.state.meta?.checksum
                    ? metaOk
                      ? "Envelope checksum matches coupling snapshot snapshot_checksum."
                      : "Coupling checksum mismatch versus envelope anchoring metadata."
                    : "Aggregated coupling list omits meta.checksum; rely on snapshot row."
                }
                onRetry={props.onRetry}
              />
            </>
          ) : (
            <p className="mt-4 text-sm text-slate-300">No coupling snapshots yet.</p>
          )}
        </>
      ) : null}
    </section>
  );
}

const MemoCouplingPanel = memo(CouplingPanel);

export type MarketIntelligenceDashboardProps = {
  ownerUserId: number | undefined;
};

/** P39-08 unified intelligence surface — envelope reads + isolated panels + deterministic snapshot cues. */
export function MarketIntelligenceDashboard({ ownerUserId }: MarketIntelligenceDashboardProps): JSX.Element | null {
  const { panels, reloadPanel, snapshotChainIssues } = useMarketIntelligencePanels(ownerUserId);

  const overview = useMemo(() => {
    const ingestion = panels.ingestion.data;
    const norm = normalizeHealth(panels.normalization.data);
    const scoreSnap = panels.scoring.data?.items[0];
    const sigSnap = panels.signals.data?.items[0];
    const oppSnap = panels.opportunities.data?.items[0];
    const sumIngestRecords = ingestion?.items.reduce((a, r) => a + r.total_records, 0) ?? null;
    const marketCandidates =
      scoreSnap?.total_candidates_scored ?? (sumIngestRecords != null ? sumIngestRecords : norm.tot || null);
    const normalizedRecords = norm.tot > 0 ? norm.tot : panels.normalization.data?.pagination.total_count ?? null;

    return {
      marketCandidates,
      normalizedRecords,
      scoredItems: scoreSnap?.total_candidates_scored ?? null,
      buys: scoreSnap ? (scoreSnap.strong_buy_count ?? 0) + (scoreSnap.buy_count ?? 0) : null,
      watch: scoreSnap?.watch_count ?? null,
      ignores: scoreSnap?.ignore_count ?? null,
      signalElitePlusHigh:
        sigSnap != null ? (sigSnap.elite_signal_count ?? 0) + (sigSnap.high_signal_count ?? 0) : null,
      opportunityClass: oppSnap?.opportunity_classification ?? null,
    };
  }, [panels.ingestion.data, panels.normalization.data, panels.opportunities.data, panels.scoring.data, panels.signals.data]);

  if (!ownerUserId) {
    return null;
  }

  const summarySnapshotKey = overview.scoredItems != null ? String(panels.scoring.data?.items[0]?.id ?? "unset") : "unset";

  return (
    <>
      <section className={marketIntelPanelClass("border-emerald-400/40")}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-300">
              Unified market intelligence (P39 · P39-07 envelope)
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-50">Deterministic snapshot overview</h2>
            <p className="mt-1 max-w-prose text-sm text-slate-300">
              Each panel loads independently, shares an in-flight dedupe key per endpoint, and tolerates partial outages.
              Summary rolls up whatever layers have surfaced for scoring snapshot boundary{" "}
              <span className="font-mono text-slate-200">{summarySnapshotKey}</span>.
            </p>
          </div>
          <Link
            to="/ops#market-intelligence-p39-trace"
            className="rounded-full border border-emerald-400/45 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/15"
          >
            Ops checksum & snapshot trace
          </Link>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Market candidates tracked"
            value={overview.marketCandidates != null ? String(overview.marketCandidates) : "—"}
          />
          <StatCard
            label="Normalized rows (sampled health)"
            value={overview.normalizedRecords != null ? String(overview.normalizedRecords) : "—"}
          />
          <StatCard label="Scored items (latest snapshot)" value={overview.scoredItems != null ? String(overview.scoredItems) : "—"} />
          <StatCard label="Buy stack (buy + strong buy)" value={overview.buys != null ? String(overview.buys) : "—"} />
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Watch bucket" value={overview.watch != null ? String(overview.watch) : "—"} />
          <StatCard label="Ignore bucket" value={overview.ignores != null ? String(overview.ignores) : "—"} />
          <StatCard
            label="Signal distribution (HIGH+ELITE tier)"
            value={overview.signalElitePlusHigh != null ? String(overview.signalElitePlusHigh) : "—"}
          />
          <StatCard
            label="Latest opportunity rollup"
            value={overview.opportunityClass ? overview.opportunityClass.replace(/_/g, " ") : "—"}
          />
        </div>

        {snapshotChainIssues.length > 0 ? (
          <div className="mt-4">
            <StatusBanner tone="warning">
              Snapshot chain inconsistencies detected — UI stays mounted, but treat automation carefully:
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {snapshotChainIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </StatusBanner>
          </div>
        ) : null}

        <div className="mt-4 rounded-2xl border border-slate-600/70 bg-slate-950 p-4 text-[11px] text-slate-400">
          <p className="font-semibold uppercase tracking-[0.14em] text-slate-100">Ops parity shortcuts</p>
          <div className="mt-3 flex flex-wrap gap-3">
            {marketIntelOpsHashes.map(([layer, hash]) => (
              <a
                key={layer}
                className="rounded-full border border-white/15 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-100 hover:border-emerald-300/55"
                href={hash}
              >
                {layer}
              </a>
            ))}
          </div>
        </div>
      </section>

      <MemoIngestionPanel state={panels.ingestion} onRetry={() => void reloadPanel("ingestion")} />
      <MemoNormalizationPanel state={panels.normalization} onRetry={() => void reloadPanel("normalization")} />
      <MemoScoringPanel state={panels.scoring} onRetry={() => void reloadPanel("scoring")} />
      <MemoSignalsPanel state={panels.signals} onRetry={() => void reloadPanel("signals")} />
      <MemoOpportunitiesPanel state={panels.opportunities} onRetry={() => void reloadPanel("opportunities")} />
      <MemoCouplingPanel state={panels.coupling} onRetry={() => void reloadPanel("coupling")} />
      <MarketIntelligenceFeedPanel ownerUserId={ownerUserId} mode="dashboard" />
    </>
  );
}
