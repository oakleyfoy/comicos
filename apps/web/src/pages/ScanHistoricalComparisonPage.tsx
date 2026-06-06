import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanHistoricalComparisonRunDetail,
  type ScanVisualEvidenceRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanHistoricalComparisonPage() {
  const [visualRuns, setVisualRuns] = useState<ScanVisualEvidenceRunRead[]>([]);
  const [selectedVisualRunId, setSelectedVisualRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanHistoricalComparisonRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanVisualEvidenceRuns({ limit: 24, offset: 0 });
        if (ignore) return;
        const complete = response.items.filter((row) => row.evidence_status === "COMPLETE");
        setVisualRuns(complete);
        setSelectedVisualRunId(complete[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load visual evidence runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const selected = visualRuns.find((row) => row.id === selectedVisualRunId);
    if (!selected) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanHistoricalComparisonRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanHistoricalComparisonRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load historical comparison runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedVisualRunId, visualRuns]);

  const selectedVisualRun = useMemo(
    () => visualRuns.find((row) => row.id === selectedVisualRunId) ?? null,
    [selectedVisualRunId, visualRuns],
  );

  async function submitRun(): Promise<void> {
    if (!selectedVisualRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanHistoricalComparison({
        scan_image_id: selectedVisualRun.scan_image_id,
        visual_evidence_run_id: selectedVisualRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Historical comparison failed.");
    } finally {
      setRunning(false);
    }
  }

  const selectedPair = run?.pairs[0] ?? null;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-15"
        title="Historical Comparison Engine"
        description="Deterministic scan-over-time comparison and evidence delta tracking."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-review" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Review workspace
            </Link>
            <Link to="/ops#scan-historical-comparison-ops" className="rounded-2xl border border-violet-400/35 px-4 py-2 text-sm font-semibold text-violet-100">
              Ops diagnostics
            </Link>
          </div>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 xl:grid-cols-[1fr,1.2fr]">
          <div className="space-y-4">
            <label className="block text-xs font-semibold text-slate-300">
              Current visual evidence run
              <select
                value={selectedVisualRunId ?? ""}
                onChange={(event) => setSelectedVisualRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {visualRuns.map((visualRun) => (
                  <option key={visualRun.id} value={visualRun.id}>
                    Scan #{visualRun.scan_image_id} · visual #{visualRun.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedVisualRun}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-violet-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Comparing history…" : "Run historical comparison"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.comparison_status}</span> · pairs{" "}
                <span className="font-semibold text-white">{run.pairs.length}</span> · deltas{" "}
                <span className="font-semibold text-white">{run.deltas.length}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <PreviewCard title="Current scan" src={run?.current_preview_data_url ?? null} />
            <PreviewCard title="Side-by-side comparison" src={run?.side_by_side_preview_data_url ?? null} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No historical comparison loaded"
            description="Run the historical comparison engine to inspect prior scan matches, evidence deltas, reliability issues, and replay-safe checksum lineage."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Comparison pair panel">
              {selectedPair ? (
                <div className="space-y-2 text-sm text-slate-300">
                  <p>
                    Current scan #{selectedPair.current_scan_image_id} vs prior scan #{selectedPair.prior_scan_image_id}
                  </p>
                  <p>
                    Match basis <span className="font-semibold text-white">{selectedPair.match_basis}</span> · confidence{" "}
                    <span className="font-semibold text-white">{selectedPair.match_confidence.toFixed(3)}</span>
                  </p>
                  <p className="break-all text-xs text-slate-400">{selectedPair.current_identity_key}</p>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No comparison pair selected.</p>
              )}
            </Panel>
            <Panel title="Scan quality comparison panel">
              <p className="text-sm text-slate-300">
                Review comparison reliability through generated scan-quality, geometry, and inconclusive deltas.
              </p>
              <p className="mt-2 text-xs text-slate-400">
                Current boundary checksum {run.current_boundary_checksum ?? "—"}
              </p>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Delta overlay viewer">
              <PreviewCard title="Delta overlay" src={run.delta_overlay_preview_data_url ?? null} compact />
            </Panel>
            <Panel title="Lineage panel">
              <ChecksumRow label="Comparison checksum" value={run.historical_comparison_checksum} />
              <ChecksumRow label="Current normalization checksum" value={run.current_normalization_checksum ?? "—"} />
              <ChecksumRow label="Current review checksum" value={run.current_review_checksum ?? "—"} />
              <ChecksumRow label="Current aggregation checksum" value={run.current_aggregation_checksum ?? "—"} />
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
            <Panel title="Delta table">
              {run.deltas.length === 0 ? (
                <p className="text-sm text-slate-500">No deltas generated.</p>
              ) : (
                <div className="max-h-[28rem] space-y-2 overflow-auto">
                  {run.deltas.map((delta) => (
                    <div key={delta.id} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300">
                      <p className="font-semibold text-violet-100">
                        {delta.delta_type} · {delta.delta_category} · {delta.delta_direction}
                      </p>
                      <p className="mt-1">
                        confidence {delta.confidence_score.toFixed(3)} · severity {delta.severity_hint}
                        {delta.region_type ? ` · ${delta.region_type}` : ""}
                      </p>
                      <p className="mt-1 font-mono text-[10px]">
                        [{delta.x_min}, {delta.y_min}] → [{delta.x_max}, {delta.y_max}]
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Issues panel">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No comparison issues recorded.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-200">
                  {run.issues.map((issue) => (
                    <li key={issue.id} className="rounded-xl border border-white/10 px-3 py-2">
                      <span className="font-semibold text-violet-100">{issue.issue_type}</span> · {issue.severity} · {issue.issue_message}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Prior lineage">
              <pre className="max-h-72 overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-violet-100">
                {JSON.stringify(run.prior_lineage, null, 2)}
              </pre>
            </Panel>
            <Panel title="History timeline">
              <ul className="space-y-2 text-xs text-slate-300">
                {run.history.map((event) => (
                  <li key={event.id} className="rounded-xl border border-white/10 px-3 py-2">
                    <p className="font-semibold text-white">{event.event_type}</p>
                    <p>{event.event_message}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          </section>
        </>
      )}
    </AppShell>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function PreviewCard({ title, src, compact = false }: { title: string; src: string | null; compact?: boolean }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-xs font-semibold text-white">{title}</p>
      {src ? (
        <img
          src={src}
          alt={title}
          className={`mt-2 w-full rounded-xl border border-white/10 object-contain bg-slate-950/50 ${compact ? "h-48" : "h-32"}`}
        />
      ) : (
        <p className="mt-2 text-xs text-slate-500">Preview unavailable.</p>
      )}
    </div>
  );
}

function ChecksumRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="mb-2 rounded-xl border border-white/10 bg-slate-950/40 p-2">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 break-all font-mono text-[10px] text-white">{value}</p>
    </div>
  );
}
