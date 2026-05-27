import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  fetchMarketV1Envelope,
  type MarketAcquisitionIngestionBatchListResponse,
  type MarketAcquisitionOpportunitySnapshotListResponse,
  type MarketAcquisitionScoreSnapshotListResponse,
  type MarketAcquisitionSignalSnapshotListResponse,
  type MarketApiV1Meta,
  type MarketNormalizationRunListResponse,
  type PortfolioMarketCouplingSnapshotListResponse,
} from "../api/client";
import { dedupedFlight } from "../lib/marketIntelFlight";
import { buildMarketSnapshotChainIssues, checksumAlignedWithEnvelope } from "../lib/marketIntelTrace";
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

function qs(params: Record<string, number | undefined>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) {
      u.set(k, String(v));
    }
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}

function buildDiagnosticParams(ownerUserId: number | undefined): Record<string, number | undefined> {
  const base: Record<string, number | undefined> = { limit: 1, offset: 0 };
  if (ownerUserId !== undefined) {
    base.owner_user_id = ownerUserId;
  }
  return base;
}

type DiagnosticsRow = {
  layer: string;
  snapshotId: string;
  checksum: string;
  generatedAt: string;
  envelopeChecksum: string;
  checksumAligned: boolean;
  error?: string | null;
};

function metaRow(
  layer: string,
  meta: MarketApiV1Meta | null | undefined,
  rowChecksum: string | null | undefined,
  fallbackId?: string | number | null,
): DiagnosticsRow {
  const sidRaw = meta?.snapshot_id ?? (fallbackId != null ? String(fallbackId) : null);
  return {
    layer,
    snapshotId: sidRaw ?? "—",
    checksum: shortenChecksum(rowChecksum),
    generatedAt: meta?.generated_at ?? "—",
    envelopeChecksum: shortenChecksum(meta?.checksum ?? null),
    checksumAligned: checksumAlignedWithEnvelope(meta ?? null, rowChecksum ?? null),
  };
}

/** Ops-only P39 diagnostics: envelope anchors + deterministic FK chain probes (GET `/api/v1/market/ops/*` only). */
export function MarketIntelligenceOpsDiagnostics(props: { ownerUserId?: number | undefined }): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<DiagnosticsRow[]>([]);
  const [chainIssues, setChainIssues] = useState<string[]>([]);

  const scopeKey = props.ownerUserId ?? "global";

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    await dedupedFlight(`opsP39trace:${scopeKey}`, async () => {
      const q = qs(buildDiagnosticParams(props.ownerUserId));

      try {
        const [
          ingestionRes,
          normalizationRes,
          scoringRes,
          signalsRes,
          opportunitiesRes,
          couplingRes,
        ] = await Promise.all([
          fetchMarketV1Envelope<MarketAcquisitionIngestionBatchListResponse>(`/ops/market-ingestion/batches${q}`),
          fetchMarketV1Envelope<MarketNormalizationRunListResponse>(`/ops/market-normalization/runs${q}`),
          fetchMarketV1Envelope<MarketAcquisitionScoreSnapshotListResponse>(`/ops/market-scoring/snapshots${q}`),
          fetchMarketV1Envelope<MarketAcquisitionSignalSnapshotListResponse>(`/ops/market-signal-snapshots${q}`),
          fetchMarketV1Envelope<MarketAcquisitionOpportunitySnapshotListResponse>(`/ops/market-opportunities/snapshots${q}`),
          fetchMarketV1Envelope<PortfolioMarketCouplingSnapshotListResponse>(`/ops/market-portfolio-coupling/snapshots${q}`),
        ]);

        const nextRows: DiagnosticsRow[] = [];

        const ingestBatch = ingestionRes.data.items[0];
        if (ingestBatch) {
          nextRows.push(
            metaRow(
              "ingestion latest batch",
              ingestionRes.meta,
              ingestBatch.batch_checksum ?? null,
              ingestBatch.id ?? null,
            ),
          );
        } else {
          nextRows.push({
            layer: "ingestion latest batch",
            snapshotId: "—",
            checksum: "—",
            generatedAt: ingestionRes.meta?.generated_at ?? "—",
            envelopeChecksum: shortenChecksum(ingestionRes.meta?.checksum ?? null),
            checksumAligned: true,
            error: "No ingestion batches matched the probe query.",
          });
        }

        const normRun = normalizationRes.data.items[0];
        if (normRun) {
          nextRows.push(
            metaRow("normalization latest run", normalizationRes.meta, normRun.run_checksum ?? null, normRun.id ?? null),
          );
        } else {
          nextRows.push({
            layer: "normalization latest run",
            snapshotId: "—",
            checksum: "—",
            generatedAt: normalizationRes.meta?.generated_at ?? "—",
            envelopeChecksum: shortenChecksum(normalizationRes.meta?.checksum ?? null),
            checksumAligned: true,
            error: "No normalization runs matched the probe query.",
          });
        }

        const score = scoringRes.data.items[0];
        const signal = signalsRes.data.items[0];
        const opportunity = opportunitiesRes.data.items[0];
        const coupling = couplingRes.data.items[0];

        nextRows.push(
          metaRow("scoring snapshot", scoringRes.meta, score?.checksum ?? null, score?.id ?? null),
          metaRow("signal snapshot", signalsRes.meta, signal?.checksum ?? null, signal?.id ?? null),
          metaRow(
            "opportunity snapshot",
            opportunitiesRes.meta,
            opportunity?.snapshot_checksum ?? null,
            opportunity?.id ?? null,
          ),
          metaRow("coupling snapshot", couplingRes.meta, coupling?.snapshot_checksum ?? null, coupling?.id ?? null),
        );

        setRows(nextRows);
        setChainIssues(
          buildMarketSnapshotChainIssues({
            score: score ?? null,
            signal: signal ?? null,
            opportunity: opportunity ?? null,
            coupling: coupling ?? null,
          }),
        );
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Unable to load P39 ops trace.";
        setError(msg);
        setRows([]);
        setChainIssues([]);
      } finally {
        setBusy(false);
      }
    });
  }, [props.ownerUserId, scopeKey]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const ownerHint = useMemo(() => {
    if (props.ownerUserId !== undefined) {
      return `Owner filter applied · user #${props.ownerUserId}.`;
    }
    return "No owner selected — fetching global-first rows for each ops list (see portfolio owner filter above).";
  }, [props.ownerUserId]);

  return (
    <section
      id="market-intelligence-p39-trace"
      className="mt-6 rounded-3xl border border-emerald-500/35 bg-slate-950/45 p-5 shadow-xl shadow-black/25"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">P39 checksum verification & snapshot trace</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Read-only probes against the standardized `/api/v1/market/ops/*` envelope. Validates row checksum continuity and
            cross-layer deterministic foreign keys for the newest snapshot boundary returned by each list call.
          </p>
          <p className="mt-2 text-[11px] text-slate-500">{ownerHint}</p>
        </div>
        <button
          type="button"
          disabled={busy}
          className="rounded-full border border-emerald-400/45 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-100 transition hover:border-emerald-300/60 hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => {
            void refresh();
          }}
        >
          {busy ? "Refreshing…" : "Refresh probes"}
        </button>
      </div>

      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {!error && chainIssues.length > 0 ? (
        <div className="mt-4">
          <StatusBanner tone="warning">
            Snapshot lineage diverged for the queried boundary:
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {chainIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </StatusBanner>
        </div>
      ) : null}

      <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/55">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
            <tr>
              <th className="p-3 font-medium">Layer probe</th>
              <th className="p-3 font-medium">Snapshot / entity id</th>
              <th className="p-3 font-medium">Row checksum</th>
              <th className="p-3 font-medium">Envelope checksum</th>
              <th className="p-3 font-medium">Aligned</th>
              <th className="p-3 font-medium">Envelope generated_at</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10 text-slate-200">
            {rows.length === 0 && !busy ? (
              <tr>
                <td className="p-4 text-slate-500" colSpan={6}>
                  No diagnostics rows yet.
                </td>
              </tr>
            ) : null}
            {rows.map((row) => (
              <tr key={row.layer}>
                <td className="p-3 align-top text-slate-100">
                  <div>{row.layer}</div>
                  {row.error ? <div className="mt-2 text-[11px] text-rose-300">{row.error}</div> : null}
                </td>
                <td className="p-3 align-top font-mono text-[11px]">{row.snapshotId}</td>
                <td className="p-3 align-top font-mono text-[11px]">{row.checksum}</td>
                <td className="p-3 align-top font-mono text-[11px]">{row.envelopeChecksum}</td>
                <td className="p-3 align-top">{row.checksumAligned ? "✓" : row.envelopeChecksum === "—" ? "n/a" : "✗"}</td>
                <td className="p-3 align-top text-slate-400">{row.generatedAt}</td>
              </tr>
            ))}
            {busy && rows.length === 0 ? (
              <tr>
                <td className="p-4 text-slate-500" colSpan={6}>
                  Loading P39 probes…
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
