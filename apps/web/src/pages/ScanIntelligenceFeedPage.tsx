import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanAuthenticationRunRead,
  type ScanHistoricalComparisonRunRead,
  type ScanIntelligenceFeedArtifactRead,
  type ScanIntelligenceFeedEventRead,
  type ScanIntelligenceFeedRunDetail,
  type ScanReviewSessionRead,
  type ScanVisualEvidenceRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function ChecksumRow({ label, value }: { label: string; value?: string | null }): JSX.Element {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/45 px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 break-all font-mono text-xs text-slate-200">{value || "—"}</p>
    </div>
  );
}

function severityTone(severity: string): string {
  switch (severity) {
    case "SUCCESS":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "ERROR":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "REVIEW_REQUIRED":
      return "border-fuchsia-400/35 bg-fuchsia-400/10 text-fuchsia-100";
    default:
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
  }
}

export function ScanIntelligenceFeedPage() {
  const [visualRuns, setVisualRuns] = useState<ScanVisualEvidenceRunRead[]>([]);
  const [historicalRuns, setHistoricalRuns] = useState<ScanHistoricalComparisonRunRead[]>([]);
  const [reviewSessions, setReviewSessions] = useState<ScanReviewSessionRead[]>([]);
  const [authenticationRuns, setAuthenticationRuns] = useState<ScanAuthenticationRunRead[]>([]);
  const [selectedVisualRunId, setSelectedVisualRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanIntelligenceFeedRunDetail | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ScanIntelligenceFeedArtifactRead | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [sourceFilter, setSourceFilter] = useState<string>("ALL");
  const [running, setRunning] = useState(false);
  const [loadingArtifactId, setLoadingArtifactId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const [visualResp, historicalResp, reviewResp, authResp] = await Promise.all([
          apiClient.listScanVisualEvidenceRuns({ limit: 40, offset: 0 }),
          apiClient.listScanHistoricalComparisonRuns({ limit: 40, offset: 0 }),
          apiClient.listScanReviewSessions({ limit: 40, offset: 0 }),
          apiClient.listScanAuthenticationRuns({ limit: 40, offset: 0 }),
        ]);
        if (ignore) return;
        const completeVisuals = visualResp.items.filter((row) => row.evidence_status === "COMPLETE");
        setVisualRuns(completeVisuals);
        setHistoricalRuns(historicalResp.items);
        setReviewSessions(reviewResp.items);
        setAuthenticationRuns(authResp.items);
        setSelectedVisualRunId(completeVisuals[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan intelligence feed inputs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const selectedVisualRun = useMemo(
    () => visualRuns.find((row) => row.id === selectedVisualRunId) ?? null,
    [selectedVisualRunId, visualRuns],
  );
  const selectedHistoricalRun = useMemo(
    () => historicalRuns.find((row) => row.scan_image_id === selectedVisualRun?.scan_image_id) ?? null,
    [historicalRuns, selectedVisualRun],
  );
  const selectedReviewSession = useMemo(
    () => reviewSessions.find((row) => row.scan_image_id === selectedVisualRun?.scan_image_id) ?? null,
    [reviewSessions, selectedVisualRun],
  );
  const selectedAuthenticationRun = useMemo(
    () => authenticationRuns.find((row) => row.scan_image_id === selectedVisualRun?.scan_image_id) ?? null,
    [authenticationRuns, selectedVisualRun],
  );

  useEffect(() => {
    if (!selectedVisualRun) {
      setRun(null);
      setSelectedArtifact(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanIntelligenceFeedRuns({ scan_image_id: selectedVisualRun.scan_image_id, limit: 1, offset: 0 });
        if (!response.items[0]) {
          if (!ignore) {
            setRun(null);
            setSelectedArtifact(null);
          }
          return;
        }
        const detail = await apiClient.getScanIntelligenceFeedRun(response.items[0].id);
        if (!ignore) {
          setRun(detail);
          setSelectedArtifact(null);
        }
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan intelligence feed runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedVisualRun]);

  const filteredEvents = useMemo(
    () =>
      (run?.events ?? []).filter((row) => {
        if (severityFilter !== "ALL" && row.severity !== severityFilter) return false;
        if (categoryFilter !== "ALL" && row.event_category !== categoryFilter) return false;
        if (sourceFilter !== "ALL" && row.source_system !== sourceFilter) return false;
        return true;
      }),
    [categoryFilter, run?.events, severityFilter, sourceFilter],
  );

  const severityOptions = useMemo(
    () => ["ALL", ...Array.from(new Set((run?.events ?? []).map((row) => row.severity)))],
    [run?.events],
  );
  const categoryOptions = useMemo(
    () => ["ALL", ...Array.from(new Set((run?.events ?? []).map((row) => row.event_category)))],
    [run?.events],
  );
  const sourceOptions = useMemo(
    () => ["ALL", ...Array.from(new Set((run?.events ?? []).map((row) => row.source_system)))],
    [run?.events],
  );

  async function submitRun(): Promise<void> {
    if (!selectedVisualRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanIntelligenceFeed({
        scan_image_id: selectedVisualRun.scan_image_id,
        visual_evidence_run_id: selectedVisualRun.id,
        review_session_id: selectedReviewSession?.id ?? null,
        historical_comparison_run_id: selectedHistoricalRun?.id ?? null,
        authentication_run_id: selectedAuthenticationRun?.id ?? null,
      });
      setRun(detail);
      setSelectedArtifact(null);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Scan intelligence feed run failed.");
    } finally {
      setRunning(false);
    }
  }

  async function inspectArtifact(artifactId: number): Promise<void> {
    setLoadingArtifactId(artifactId);
    try {
      const artifact = await apiClient.getScanIntelligenceFeedArtifact(artifactId);
      setSelectedArtifact(artifact);
    } catch (artifactErr) {
      setError(artifactErr instanceof ApiError ? artifactErr.message : "Unable to load artifact preview.");
    } finally {
      setLoadingArtifactId(null);
    }
  }

  function downloadArtifact(artifact: ScanIntelligenceFeedArtifactRead): void {
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

  const infoCount = run?.events.filter((row) => row.severity === "INFO" || row.severity === "SUCCESS").length ?? 0;
  const warningCount = run?.events.filter((row) => row.severity === "WARNING").length ?? 0;
  const reviewRequiredCount = run?.events.filter((row) => row.severity === "REVIEW_REQUIRED").length ?? 0;
  const errorCount = run?.events.filter((row) => row.severity === "ERROR").length ?? 0;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-17"
        title="Scan Intelligence Feed Layer"
        description="Deterministic chronological feed for scan pipeline checkpoints, review actions, support outputs, warnings, and replay-safe lineage."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-authentication" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Authentication layer
            </Link>
            <Link to="/ops#scan-intelligence-feed-ops" className="rounded-2xl border border-fuchsia-400/35 px-4 py-2 text-sm font-semibold text-fuchsia-100">
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
        <div className="grid gap-4 xl:grid-cols-[1fr,1fr]">
          <div className="space-y-4">
            <label className="block text-xs font-semibold text-slate-300">
              Visual evidence run
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
              className="rounded-2xl bg-fuchsia-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Building feed…" : "Run scan intelligence feed"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.feed_status}</span> · engine{" "}
                <span className="font-semibold text-white">{run.engine_version}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Info / success" value={String(infoCount)} />
            <StatCard label="Warnings" value={String(warningCount)} />
            <StatCard label="Review required" value={String(reviewRequiredCount)} />
            <StatCard label="Errors" value={String(errorCount)} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No scan intelligence feed loaded"
            description="Run the feed layer to generate a replay-safe timeline across ingestion, detectors, review, authentication support, and system diagnostics."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr,1fr]">
            <Panel title="Severity filter">
              <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white">
                {severityOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Panel>
            <Panel title="Category filter">
              <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white">
                {categoryOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Panel>
            <Panel title="Source-system filter">
              <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white">
                {sourceOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.3fr,0.7fr]">
            <Panel title="Timeline viewer">
              <div className="max-h-[34rem] space-y-2 overflow-auto">
                {filteredEvents.map((event: ScanIntelligenceFeedEventRead) => (
                  <div key={event.id} className="rounded-2xl border border-white/10 px-3 py-3 text-xs text-slate-300">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-white">
                          #{event.timeline_rank} · {event.event_type}
                        </p>
                        <p className="mt-1 text-slate-400">
                          {event.event_category} · {event.source_system} · {formatDateTime(event.event_occurred_at)}
                        </p>
                      </div>
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${severityTone(event.severity)}`}>
                        {event.severity}
                      </span>
                    </div>
                    <pre className="mt-2 overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-cyan-100">
                      {JSON.stringify(event.event_payload_json, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Lineage panel">
              <div className="space-y-2">
                <ChecksumRow label="Feed checksum" value={run.feed_checksum} />
                <ChecksumRow label="Original scan checksum" value={run.original_scan_checksum} />
                <ChecksumRow label="Visual evidence checksum" value={run.visual_evidence_checksum} />
                <ChecksumRow label="Historical checksum" value={run.historical_comparison_checksum} />
                <ChecksumRow label="Authentication checksum" value={run.authentication_checksum} />
              </div>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[0.8fr,1.2fr]">
            <Panel title="Issue panel">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No feed issues recorded.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-200">
                  {run.issues.map((issue) => (
                    <li key={issue.id} className="rounded-xl border border-white/10 px-3 py-2">
                      <span className="font-semibold text-fuchsia-100">{issue.issue_type}</span> · {issue.severity} · {issue.issue_message}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Artifacts and preview">
              <div className="grid gap-3 xl:grid-cols-[0.65fr,1.35fr]">
                <div className="space-y-2">
                  {run.artifacts.map((artifact) => (
                    <div key={artifact.id} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300">
                      <p className="font-semibold text-white">{artifact.artifact_type}</p>
                      <div className="mt-2 flex gap-2">
                        <button
                          type="button"
                          onClick={() => void inspectArtifact(artifact.id)}
                          className="rounded-full border border-fuchsia-400/35 px-3 py-1 text-[11px] font-semibold text-fuchsia-100"
                        >
                          {loadingArtifactId === artifact.id ? "Loading…" : "Preview"}
                        </button>
                        <button
                          type="button"
                          onClick={() => downloadArtifact(selectedArtifact?.id === artifact.id ? selectedArtifact : artifact)}
                          className="rounded-full border border-white/10 px-3 py-1 text-[11px] font-semibold text-slate-200"
                        >
                          Download
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <pre className="max-h-[26rem] overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-fuchsia-100">
                  {selectedArtifact?.text_preview ?? "Select an artifact preview."}
                </pre>
              </div>
            </Panel>
          </section>
        </>
      )}
    </AppShell>
  );
}
