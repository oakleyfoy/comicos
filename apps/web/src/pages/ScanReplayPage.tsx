import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanReplayArtifactRead,
  type ScanReplayCheckRead,
  type ScanReplayDiscrepancyRead,
  type ScanReplayRunDetail,
  type ScanReplayRunRead,
  type ScanReplayStepRead,
  type ScanVisualEvidenceRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortenChecksum(value?: string | null): string {
  if (!value) return "—";
  if (value.length <= 18) return value;
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function severityTone(severity: string): string {
  switch (severity) {
    case "CRITICAL":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "ERROR":
      return "border-orange-400/35 bg-orange-400/10 text-orange-100";
    case "WARNING":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    default:
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
  }
}

function stepTone(status: string): string {
  switch (status) {
    case "MATCHED":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "MISMATCHED":
    case "ERROR":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "MISSING_SOURCE":
    case "REPLAY_BLOCKED":
      return "border-orange-400/35 bg-orange-400/10 text-orange-100";
    default:
      return "border-slate-400/35 bg-slate-400/10 text-slate-100";
  }
}

type ReplayScope = "SINGLE_SCAN" | "FULL_P40_PIPELINE" | "SELECTED_STAGE" | "OPS_AUDIT" | "BATCH_REPLAY";

const replayScopes: Array<{ value: ReplayScope; label: string }> = [
  { value: "FULL_P40_PIPELINE", label: "Full P40 pipeline" },
  { value: "SINGLE_SCAN", label: "Single scan" },
  { value: "SELECTED_STAGE", label: "Selected stage" },
  { value: "OPS_AUDIT", label: "Ops audit" },
  { value: "BATCH_REPLAY", label: "Batch replay" },
];

const selectablePhases = [
  "P40_01_SCAN_INGESTION",
  "P40_02_NORMALIZATION",
  "P40_03_BOUNDARY",
  "P40_04_OCR",
  "P40_05_RECONCILIATION",
  "P40_06_DEFECT_FOUNDATION",
  "P40_07_SPINE",
  "P40_08_CORNER_EDGE",
  "P40_09_SURFACE",
  "P40_10_STRUCTURAL",
  "P40_11_AGGREGATION",
  "P40_12_GRADING_ASSISTANCE",
  "P40_13_VISUAL_EVIDENCE",
  "P40_14_REVIEW",
  "P40_15_HISTORICAL_COMPARISON",
  "P40_16_AUTHENTICATION",
  "P40_17_FEED",
] as const;

export function ScanReplayPage() {
  const [visualRuns, setVisualRuns] = useState<ScanVisualEvidenceRunRead[]>([]);
  const [recentRuns, setRecentRuns] = useState<ScanReplayRunRead[]>([]);
  const [opsCritical, setOpsCritical] = useState<ScanReplayDiscrepancyRead[]>([]);
  const [selectedScanImageId, setSelectedScanImageId] = useState<number | null>(null);
  const [scope, setScope] = useState<ReplayScope>("FULL_P40_PIPELINE");
  const [selectedPhaseKey, setSelectedPhaseKey] = useState<string>(selectablePhases[0]);
  const [run, setRun] = useState<ScanReplayRunDetail | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ScanReplayArtifactRead | null>(null);
  const [running, setRunning] = useState(false);
  const [loadingArtifactId, setLoadingArtifactId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const [visualResp, runResp, criticalResp] = await Promise.all([
          apiClient.listScanVisualEvidenceRuns({ limit: 50, offset: 0 }),
          apiClient.listScanReplayRuns({ limit: 20, offset: 0 }),
          apiClient.listOpsScanReplayCritical({ limit: 10, offset: 0 }),
        ]);
        if (ignore) return;
        const completeVisuals = visualResp.items.filter((row) => row.evidence_status === "COMPLETE");
        setVisualRuns(completeVisuals);
        setRecentRuns(runResp.items);
        setOpsCritical(criticalResp.items);
        setSelectedScanImageId(runResp.items[0]?.scan_image_id ?? completeVisuals[0]?.scan_image_id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load replay workspace inputs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedScanImageId) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanReplayRuns({ scan_image_id: selectedScanImageId, limit: 1, offset: 0 });
        if (!response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanReplayRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load replay runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedScanImageId]);

  const scanOptions = useMemo(() => {
    const byId = new Map<number, { scanImageId: number; label: string }>();
    for (const row of visualRuns) {
      byId.set(row.scan_image_id, { scanImageId: row.scan_image_id, label: `Scan #${row.scan_image_id} · visual #${row.id}` });
    }
    for (const row of recentRuns) {
      if (row.scan_image_id) {
        byId.set(row.scan_image_id, { scanImageId: row.scan_image_id, label: `Scan #${row.scan_image_id} · replay #${row.id}` });
      }
    }
    return Array.from(byId.values()).sort((left, right) => right.scanImageId - left.scanImageId);
  }, [recentRuns, visualRuns]);

  const checksumChecks = useMemo(
    () => (run?.checks ?? []).filter((row) => row.check_type === "CHECKSUM_MATCH" || row.check_type === "MANIFEST_MATCH"),
    [run?.checks],
  );
  const criticalWarnings = useMemo(() => opsCritical.slice(0, 4), [opsCritical]);

  async function submitRun(): Promise<void> {
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanReplay({
        scan_image_id: selectedScanImageId,
        replay_scope: scope,
        selected_phase_key: scope === "SELECTED_STAGE" ? selectedPhaseKey : undefined,
      });
      setRun(detail);
      setSelectedArtifact(null);
      const refreshRuns = await apiClient.listScanReplayRuns({ limit: 20, offset: 0 });
      setRecentRuns(refreshRuns.items);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Replay verification failed.");
    } finally {
      setRunning(false);
    }
  }

  async function inspectArtifact(artifactId: number): Promise<void> {
    setLoadingArtifactId(artifactId);
    try {
      const artifact = await apiClient.getScanReplayArtifact(artifactId);
      setSelectedArtifact(artifact);
    } catch (artifactErr) {
      setError(artifactErr instanceof ApiError ? artifactErr.message : "Unable to load replay artifact.");
    } finally {
      setLoadingArtifactId(null);
    }
  }

  function downloadArtifact(artifact: ScanReplayArtifactRead): void {
    const body = artifact.body_base64 ? atob(artifact.body_base64) : artifact.text_preview ?? "";
    const bytes = Uint8Array.from(body, (char) => char.charCodeAt(0));
    const blob = new Blob([bytes], { type: artifact.media_type ?? "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = artifact.storage_path.split("/").pop() || `${artifact.artifact_type.toLowerCase()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const mismatchCount = run?.discrepancies.filter((row) => row.discrepancy_type === "CHECKSUM_MISMATCH").length ?? 0;
  const criticalCount = run?.discrepancies.filter((row) => row.severity === "CRITICAL").length ?? 0;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-18"
        title="Determinism / Replay Layer"
        description="Audit-grade replay verification for scan intelligence lineage, checksum stability, immutable artifacts, and replay-safe discrepancy tracking."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-intelligence-feed" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Feed layer
            </Link>
            <Link to="/ops#scan-replay-ops" className="rounded-2xl border border-cyan-400/35 px-4 py-2 text-sm font-semibold text-cyan-100">
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

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5">
        <div className="grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
          <div className="space-y-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Run Panel</p>
              <h2 className="mt-1 text-lg font-semibold text-white">Launch replay verification</h2>
              <p className="mt-1 text-sm text-slate-400">
                Select a scan and replay scope, then run deterministic verification against the immutable P40 ledger.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <label className="space-y-2 text-sm text-slate-300">
                <span>Scan image</span>
                <select
                  value={selectedScanImageId ?? ""}
                  onChange={(event) => setSelectedScanImageId(event.target.value ? Number(event.target.value) : null)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  <option value="">Choose a scan</option>
                  {scanOptions.map((option) => (
                    <option key={option.scanImageId} value={option.scanImageId}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-300">
                <span>Replay scope</span>
                <select value={scope} onChange={(event) => setScope(event.target.value as ReplayScope)} className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white">
                  {replayScopes.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-300">
                <span>Selected phase</span>
                <select
                  disabled={scope !== "SELECTED_STAGE"}
                  value={selectedPhaseKey}
                  onChange={(event) => setSelectedPhaseKey(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white disabled:opacity-50"
                >
                  {selectablePhases.map((phase) => (
                    <option key={phase} value={phase}>
                      {phase}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void submitRun()}
                disabled={running || (!selectedScanImageId && scope !== "OPS_AUDIT" && scope !== "BATCH_REPLAY")}
                className="rounded-2xl bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {running ? "Running replay…" : "Run replay verification"}
              </button>
              {run ? <p className="text-sm text-slate-400">Latest status: {run.replay_status}</p> : null}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <StatCard label="Latest replay" value={run ? `#${run.id}` : "—"} />
            <StatCard label="Checksum mismatches" value={String(mismatchCount)} />
            <StatCard label="Critical discrepancies" value={String(criticalCount)} />
            <StatCard label="Artifact exports" value={String(run?.artifacts.length ?? 0)} />
          </div>
        </div>
      </section>

      {criticalWarnings.length ? (
        <section className="mt-6 rounded-3xl border border-rose-400/30 bg-rose-950/12 p-5">
          <h2 className="text-sm font-semibold text-white">Ops-critical replay warnings</h2>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {criticalWarnings.map((row) => (
              <div key={row.id} className="rounded-2xl border border-rose-400/20 bg-slate-950/45 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${severityTone(row.severity)}`}>{row.severity}</span>
                  <span className="text-xs text-slate-500">{row.discrepancy_type}</span>
                </div>
                <p className="mt-3 text-sm text-slate-200">{row.discrepancy_message}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {!run ? (
        <div className="mt-6">
          <EmptyState title="No replay selected" description="Run verification for a scan image to inspect replay steps, checksum audits, lineage, issues, and exports." />
        </div>
      ) : (
        <div className="mt-6 grid gap-6 xl:grid-cols-[1.3fr,0.7fr]">
          <div className="space-y-6">
            <Panel title="Replay Step Table">
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm text-slate-300">
                  <thead className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                    <tr>
                      <th className="pb-3 pr-4">Phase</th>
                      <th className="pb-3 pr-4">Expected</th>
                      <th className="pb-3 pr-4">Observed</th>
                      <th className="pb-3 pr-4">Status</th>
                      <th className="pb-3">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.steps.map((row: ScanReplayStepRead) => (
                      <tr key={row.id} className="border-t border-white/5 align-top">
                        <td className="py-3 pr-4">
                          <p className="font-medium text-white">{row.phase_key}</p>
                          <p className="text-xs text-slate-500">Rank {row.step_rank}</p>
                        </td>
                        <td className="py-3 pr-4 font-mono text-xs text-slate-300">{shortenChecksum(row.expected_checksum)}</td>
                        <td className="py-3 pr-4 font-mono text-xs text-slate-300">{shortenChecksum(row.observed_checksum)}</td>
                        <td className="py-3 pr-4">
                          <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${stepTone(row.replay_step_status)}`}>
                            {row.replay_step_status}
                          </span>
                        </td>
                        <td className="py-3 text-xs text-slate-400">{row.source_record_id ? `#${row.source_record_id}` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel title="Checksum Audit Panel">
              <div className="grid gap-3 lg:grid-cols-2">
                {checksumChecks.length ? (
                  checksumChecks.map((row: ScanReplayCheckRead) => (
                    <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-white">{row.check_type}</p>
                        <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${severityTone(row.check_status === "FAIL" ? "ERROR" : row.check_status === "WARNING" ? "WARNING" : "INFO")}`}>
                          {row.check_status}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">Step {row.step_id ?? "Global"}</p>
                      <p className="mt-3 font-mono text-xs text-slate-300">Expected: {shortenChecksum(row.expected_value)}</p>
                      <p className="mt-1 font-mono text-xs text-slate-300">Observed: {shortenChecksum(row.observed_value)}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-400">No checksum audit rows recorded yet.</p>
                )}
              </div>
            </Panel>

            <Panel title="Lineage Panel">
              <div className="space-y-3">
                {run.lineage_chain.map((row, index) => (
                  <div key={`${String(row.phase_key)}-${index}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="font-medium text-white">{String(row.phase_key)}</p>
                      <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${stepTone(String(row.replay_step_status ?? "SKIPPED"))}`}>
                        {String(row.replay_step_status ?? "SKIPPED")}
                      </span>
                    </div>
                    <p className="mt-2 font-mono text-xs text-slate-300">Expected: {shortenChecksum(String(row.expected_checksum ?? ""))}</p>
                    <p className="mt-1 font-mono text-xs text-slate-300">Observed: {shortenChecksum(String(row.observed_checksum ?? ""))}</p>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Discrepancy Table">
              {run.discrepancies.length ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm text-slate-300">
                    <thead className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      <tr>
                        <th className="pb-3 pr-4">Type</th>
                        <th className="pb-3 pr-4">Severity</th>
                        <th className="pb-3 pr-4">Expected</th>
                        <th className="pb-3 pr-4">Observed</th>
                        <th className="pb-3">Message</th>
                      </tr>
                    </thead>
                    <tbody>
                      {run.discrepancies.map((row: ScanReplayDiscrepancyRead) => (
                        <tr key={row.id} className="border-t border-white/5 align-top">
                          <td className="py-3 pr-4">{row.discrepancy_type}</td>
                          <td className="py-3 pr-4">
                            <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${severityTone(row.severity)}`}>{row.severity}</span>
                          </td>
                          <td className="py-3 pr-4 font-mono text-xs text-slate-300">{shortenChecksum(row.expected_value)}</td>
                          <td className="py-3 pr-4 font-mono text-xs text-slate-300">{shortenChecksum(row.observed_value)}</td>
                          <td className="py-3 text-slate-200">{row.discrepancy_message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-400">No replay discrepancies recorded for this run.</p>
              )}
            </Panel>
          </div>

          <div className="space-y-6">
            <Panel title="Issue Panel">
              {run.issues.length ? (
                <div className="space-y-3">
                  {run.issues.map((row) => (
                    <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-white">{row.issue_type}</p>
                        <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${severityTone(row.severity)}`}>{row.severity}</span>
                      </div>
                      <p className="mt-2 text-sm text-slate-300">{row.issue_message}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No replay issues recorded.</p>
              )}
            </Panel>

            <Panel title="Artifact Export Panel">
              <div className="space-y-3">
                {run.artifacts.map((artifact) => (
                  <div key={artifact.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium text-white">{artifact.artifact_type}</p>
                        <p className="mt-1 font-mono text-xs text-slate-500">{artifact.storage_path}</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => void inspectArtifact(artifact.id)}
                          className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200"
                        >
                          {loadingArtifactId === artifact.id ? "Loading…" : "Preview"}
                        </button>
                        <button type="button" onClick={() => downloadArtifact(artifact)} className="rounded-full border border-cyan-400/35 px-3 py-1.5 text-xs font-semibold text-cyan-100">
                          Download
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                {selectedArtifact ? (
                  <div className="rounded-2xl border border-cyan-400/25 bg-slate-950/60 p-4">
                    <p className="text-sm font-semibold text-white">{selectedArtifact.artifact_type}</p>
                    <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-2xl bg-slate-950/80 p-3 text-xs text-slate-200">
                      {selectedArtifact.text_preview ?? "Binary artifact preview unavailable."}
                    </pre>
                  </div>
                ) : null}
              </div>
            </Panel>

            <Panel title="History Timeline">
              {run.history.length ? (
                <div className="space-y-3">
                  {run.history.map((row) => (
                    <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-white">{row.event_type}</p>
                        <p className="text-xs text-slate-500">{formatDateTime(row.created_at)}</p>
                      </div>
                      <p className="mt-2 text-sm text-slate-300">{row.event_message}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No replay history recorded yet.</p>
              )}
            </Panel>
          </div>
        </div>
      )}
    </AppShell>
  );
}
