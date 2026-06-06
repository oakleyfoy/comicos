import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanAuthenticationRunDetail,
  type ScanHistoricalComparisonRunRead,
  type ScanReviewSessionRead,
  type ScanVisualEvidenceRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanAuthenticationPage() {
  const [visualRuns, setVisualRuns] = useState<ScanVisualEvidenceRunRead[]>([]);
  const [historicalRuns, setHistoricalRuns] = useState<ScanHistoricalComparisonRunRead[]>([]);
  const [reviewSessions, setReviewSessions] = useState<ScanReviewSessionRead[]>([]);
  const [selectedVisualRunId, setSelectedVisualRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanAuthenticationRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const [visualResp, historicalResp, reviewResp] = await Promise.all([
          apiClient.listScanVisualEvidenceRuns({ limit: 24, offset: 0 }),
          apiClient.listScanHistoricalComparisonRuns({ limit: 24, offset: 0 }),
          apiClient.listScanReviewSessions({ limit: 24, offset: 0 }),
        ]);
        if (ignore) return;
        const completeVisuals = visualResp.items.filter((row) => row.evidence_status === "COMPLETE");
        setVisualRuns(completeVisuals);
        setHistoricalRuns(historicalResp.items);
        setReviewSessions(reviewResp.items);
        setSelectedVisualRunId(completeVisuals[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load authentication inputs.");
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
    () => historicalRuns.find((row) => row.scan_image_id === selectedVisualRun?.scan_image_id) ?? historicalRuns[0] ?? null,
    [historicalRuns, selectedVisualRun],
  );
  const selectedReviewSession = useMemo(
    () => reviewSessions.find((row) => row.scan_image_id === selectedVisualRun?.scan_image_id) ?? reviewSessions[0] ?? null,
    [reviewSessions, selectedVisualRun],
  );

  useEffect(() => {
    if (!selectedVisualRun) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanAuthenticationRuns({ scan_image_id: selectedVisualRun.scan_image_id, limit: 1, offset: 0 });
        if (!response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanAuthenticationRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load authentication assistance runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedVisualRun]);

  async function submitRun(): Promise<void> {
    if (!selectedVisualRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanAuthentication({
        scan_image_id: selectedVisualRun.scan_image_id,
        visual_evidence_run_id: selectedVisualRun.id,
        historical_comparison_run_id: selectedHistoricalRun?.id ?? null,
        review_session_id: selectedReviewSession?.id ?? null,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Authentication assistance failed.");
    } finally {
      setRunning(false);
    }
  }

  const supportCount = run?.findings.filter((row) => row.finding_status === "SUPPORTIVE").length ?? 0;
  const conflictCount = run?.findings.filter((row) => row.finding_status === "CONFLICT").length ?? 0;
  const inconclusiveCount = run?.findings.filter((row) => row.finding_status === "INCONCLUSIVE").length ?? 0;
  const reviewRequiredCount = run?.findings.filter((row) => row.finding_status === "REVIEW_REQUIRED").length ?? 0;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-16"
        title="Authentication Assistance Layer"
        description="Deterministic authenticity-review support signals without certification claims."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-historical-comparison" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Historical comparison
            </Link>
            <Link to="/ops#scan-authentication-ops" className="rounded-2xl border border-cyan-400/35 px-4 py-2 text-sm font-semibold text-cyan-100">
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
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running assistance…" : "Run authentication assistance"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.authentication_status}</span> · rubric{" "}
                <span className="font-semibold text-white">{run.rubric_version}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Support" value={String(supportCount)} />
            <StatCard label="Conflicts" value={String(conflictCount)} />
            <StatCard label="Inconclusive" value={String(inconclusiveCount)} />
            <StatCard label="Review required" value={String(reviewRequiredCount)} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No authentication assistance loaded"
            description="Run authentication assistance to inspect identity consistency, metadata conflicts, lineage integrity, historical consistency, and review-required flags."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Identity consistency panel">
              <SignalSummary signals={run.signals.filter((row) => row.signal_category === "IDENTITY")} />
            </Panel>
            <Panel title="Metadata conflict panel">
              <SignalSummary signals={run.signals.filter((row) => row.signal_category === "METADATA")} />
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Lineage integrity panel">
              <SignalSummary signals={run.signals.filter((row) => row.signal_category === "LINEAGE")} />
            </Panel>
            <Panel title="Historical consistency panel">
              <SignalSummary signals={run.signals.filter((row) => row.signal_category === "HISTORICAL")} />
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
            <Panel title="Signal table">
              <div className="max-h-[28rem] space-y-2 overflow-auto">
                {run.signals.map((signal) => (
                  <div key={signal.id} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300">
                    <p className="font-semibold text-cyan-100">
                      {signal.signal_type} · {signal.signal_category} · {signal.signal_status}
                    </p>
                    <p className="mt-1">
                      confidence {signal.confidence_score.toFixed(3)} · source {signal.source_system}
                    </p>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Findings panel">
              <div className="space-y-2">
                {run.findings.map((finding) => (
                  <div key={finding.id} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300">
                    <p className="font-semibold text-white">
                      {finding.finding_type} · {finding.finding_status} · {finding.review_priority}
                    </p>
                    <p className="mt-1">{finding.finding_text}</p>
                  </div>
                ))}
              </div>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Issue panel">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No authentication issues recorded.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-200">
                  {run.issues.map((issue) => (
                    <li key={issue.id} className="rounded-xl border border-white/10 px-3 py-2">
                      <span className="font-semibold text-cyan-100">{issue.issue_type}</span> · {issue.severity} · {issue.issue_message}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Lineage panel">
              <ChecksumRow label="Authentication checksum" value={run.authentication_checksum} />
              <ChecksumRow label="Original scan checksum" value={run.original_scan_checksum ?? "—"} />
              <ChecksumRow label="Historical checksum" value={run.historical_comparison_checksum ?? "—"} />
              <ChecksumRow label="Review checksum" value={run.review_checksum ?? "—"} />
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Review-required flags">
              <pre className="max-h-72 overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-cyan-100">
                {JSON.stringify(run.output_manifest_json.review_flags ?? [], null, 2)}
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

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function SignalSummary({
  signals,
}: {
  signals: Array<{ id: number; signal_type: string; signal_status: string; confidence_score: number }>;
}): JSX.Element {
  if (signals.length === 0) {
    return <p className="text-sm text-slate-500">No signals in this panel.</p>;
  }
  return (
    <div className="space-y-2 text-xs text-slate-300">
      {signals.map((signal) => (
        <div key={signal.id} className="rounded-xl border border-white/10 px-3 py-2">
          <p className="font-semibold text-cyan-100">{signal.signal_type}</p>
          <p className="mt-1">
            {signal.signal_status} · confidence {signal.confidence_score.toFixed(3)}
          </p>
        </div>
      ))}
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
