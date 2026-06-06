import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanDefectAggregateClusterRead,
  type ScanDefectAggregationRunDetail,
  type ScanDefectRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanDefectAggregationPage() {
  const [defectRuns, setDefectRuns] = useState<ScanDefectRunRead[]>([]);
  const [selectedDefectRunId, setSelectedDefectRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanDefectAggregationRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanDefectRuns({ limit: 16, offset: 0 });
        if (ignore) return;
        const complete = response.items.filter((row) => row.defect_status === "COMPLETE");
        setDefectRuns(complete);
        setSelectedDefectRunId(complete[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load defect runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const selected = defectRuns.find((row) => row.id === selectedDefectRunId);
    if (!selected) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanDefectAggregationRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanDefectAggregationRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load aggregation runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [defectRuns, selectedDefectRunId]);

  const selectedDefectRun = useMemo(
    () => defectRuns.find((row) => row.id === selectedDefectRunId) ?? null,
    [defectRuns, selectedDefectRunId],
  );

  const conditionMap = useMemo(
    () => run?.artifacts.find((a) => a.artifact_type === "AGGREGATE_CONDITION_MAP")?.preview_data_url ?? null,
    [run],
  );
  const clusterOverlay = useMemo(
    () => run?.artifacts.find((a) => a.artifact_type === "DEFECT_CLUSTER_OVERLAY")?.preview_data_url ?? null,
    [run],
  );
  const selectedCluster = useMemo(() => run?.clusters[0] ?? null, [run]);

  async function submitRun(): Promise<void> {
    if (!selectedDefectRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanDefectAggregation({
        scan_image_id: selectedDefectRun.scan_image_id,
        defect_run_id: selectedDefectRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Defect aggregation failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-11"
        title="Defect Aggregation Engine"
        description="Deterministic unified condition evidence aggregation."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-structural-damage" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Structural evidence
            </Link>
            <Link to="/ops#scan-defect-aggregation-ops" className="rounded-2xl border border-emerald-400/35 px-4 py-2 text-sm font-semibold text-emerald-100">
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
              Scan / defect foundation run
              <select
                value={selectedDefectRunId ?? ""}
                onChange={(event) => setSelectedDefectRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {defectRuns.map((defectRun) => (
                  <option key={defectRun.id} value={defectRun.id}>
                    Scan #{defectRun.scan_image_id} · defect #{defectRun.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedDefectRun}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-emerald-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running aggregation…" : "Run defect aggregation"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.aggregation_status}</span> · engine{" "}
                <span className="font-semibold text-white">{run.engine_version}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <PreviewCard title="Source scan preview" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="Aggregate condition map" src={conditionMap} />
            <PreviewCard title="Cluster overlay" src={clusterOverlay} />
            <PreviewCard
              title="Debug preview"
              src={run?.artifacts.find((a) => a.artifact_type === "AGGREGATION_DEBUG_PREVIEW")?.preview_data_url ?? null}
            />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No aggregation run loaded"
            description="Select a scan-backed defect foundation run and execute aggregation to inspect unified condition clusters, source evidence lineage, region summaries, and replay-safe checksums."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
            <Panel title="Cluster table">
              {run.clusters.length === 0 ? (
                <p className="text-sm text-slate-500">No aggregate clusters recorded.</p>
              ) : (
                <div className="space-y-2">
                  {run.clusters.map((cluster) => (
                    <ClusterRow key={cluster.id} cluster={cluster} />
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Source evidence lineage">
              {run.evidence.length === 0 ? (
                <p className="text-sm text-slate-500">No source evidence references recorded.</p>
              ) : (
                <div className="space-y-2">
                  {run.evidence.map((evidence) => (
                    <div key={evidence.id} className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs text-slate-300">
                      <p className="font-semibold text-white">
                        {evidence.source_detector} · source #{evidence.source_evidence_id}
                      </p>
                      <p className="mt-1">
                        {evidence.evidence_type} · confidence {evidence.confidence_score.toFixed(3)} · contribution {evidence.contribution_weight.toFixed(3)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Region summary panel">
              <div className="grid gap-3 md:grid-cols-2">
                {Object.entries(run.region_summaries).map(([region, summary]) => (
                  <SummaryCard key={region} region={region} summary={summary as Record<string, unknown>} />
                ))}
              </div>
            </Panel>
            <Panel title="Selected cluster measurements">
              {selectedCluster ? (
                <pre className="max-h-80 overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-emerald-100">
                  {JSON.stringify(selectedCluster.measurement_json, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-slate-500">Run aggregation to populate cluster measurements.</p>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Issues panel">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No aggregation issues recorded.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-200">
                  {run.issues.map((issue) => (
                    <li key={issue.id} className="rounded-xl border border-white/10 px-3 py-2">
                      <span className="font-semibold text-emerald-100">{issue.issue_type}</span> · {issue.severity} · {issue.issue_message}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Checksum lineage">
              <ChecksumRow label="Original scan" value={run.original_scan_checksum ?? "—"} />
              <ChecksumRow label="Normalization" value={run.normalization_checksum ?? "—"} />
              <ChecksumRow label="Boundary" value={run.boundary_checksum ?? "—"} />
              <ChecksumRow label="Defect foundation" value={run.defect_checksum ?? "—"} />
              <ChecksumRow label="Spine tick" value={run.spine_tick_checksum ?? "—"} />
              <ChecksumRow label="Corner / edge" value={run.corner_edge_checksum ?? "—"} />
              <ChecksumRow label="Surface defect" value={run.surface_defect_checksum ?? "—"} />
              <ChecksumRow label="Structural damage" value={run.structural_damage_checksum ?? "—"} />
              <ChecksumRow label="Aggregation manifest" value={run.aggregation_checksum} />
            </Panel>
          </section>

          <section className="mt-6">
            <Panel title="Aggregation history timeline">
              <ul className="space-y-2 text-xs text-slate-300">
                {run.history.map((event) => (
                  <li key={event.id} className="rounded-xl border border-white/10 px-3 py-2">
                    <p className="font-semibold text-white">{event.event_type}</p>
                    <p>{event.event_message}</p>
                    <p className="mt-1 font-mono text-[10px] text-emerald-100">{event.event_checksum.slice(0, 16)}…</p>
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

function PreviewCard({ title, src }: { title: string; src: string | null }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-xs font-semibold text-white">{title}</p>
      {src ? (
        <img src={src} alt={title} className="mt-2 h-32 w-full rounded-xl border border-white/10 object-contain bg-slate-950/50" />
      ) : (
        <p className="mt-2 text-xs text-slate-500">Preview unavailable.</p>
      )}
    </div>
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

function ChecksumRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="mb-2 rounded-xl border border-white/10 bg-slate-950/40 p-2">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 break-all font-mono text-[10px] text-white">{value}</p>
    </div>
  );
}

function ClusterRow({ cluster }: { cluster: ScanDefectAggregateClusterRead }): JSX.Element {
  const measurements = cluster.measurement_json as Record<string, number>;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white">
            {cluster.cluster_type} · {cluster.cluster_region}
          </p>
          <p className="mt-1 text-slate-400">
            rank {cluster.cluster_rank} · {cluster.aggregate_severity_hint} · confidence {cluster.cluster_confidence.toFixed(3)}
          </p>
        </div>
        <p className="font-mono text-[10px] text-emerald-100">
          [{cluster.x_min}, {cluster.y_min}] → [{cluster.x_max}, {cluster.y_max}]
        </p>
      </div>
      <div className="mt-2 grid gap-2 text-slate-400 md:grid-cols-3">
        <span>evidence {Number(measurements.evidence_count ?? 0)}</span>
        <span>bbox {Number(measurements.cluster_bbox_area ?? 0)}</span>
        <span>overlap {Number(measurements.overlap_ratio ?? 0).toFixed(3)}</span>
      </div>
    </div>
  );
}

function SummaryCard({ region, summary }: { region: string; summary: Record<string, unknown> }): JSX.Element {
  const confidence = (summary.confidence_summary as Record<string, number> | undefined) ?? {};
  const severity = (summary.severity_distribution as Record<string, number> | undefined) ?? {};
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-3 text-xs">
      <p className="font-semibold uppercase tracking-[0.16em] text-emerald-100">{region}</p>
      <p className="mt-2 text-slate-300">Evidence {Number(summary.evidence_count ?? 0)} · clusters {Number(summary.cluster_count ?? 0)}</p>
      <p className="mt-1 text-slate-400">
        mean confidence {Number(confidence.mean_confidence ?? 0).toFixed(3)} · max {Number(confidence.max_confidence ?? 0).toFixed(3)}
      </p>
      <p className="mt-1 text-slate-400">
        minor {Number(severity.MINOR ?? 0)} · moderate {Number(severity.MODERATE ?? 0)} · major {Number(severity.MAJOR ?? 0)}
      </p>
    </div>
  );
}
