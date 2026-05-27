import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanBoundaryRunRead,
  type ScanDefectEvidenceRead,
  type ScanDefectRunDetail,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanDefectsPage() {
  const [boundaryRuns, setBoundaryRuns] = useState<ScanBoundaryRunRead[]>([]);
  const [selectedBoundaryRunId, setSelectedBoundaryRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanDefectRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanBoundaryRuns({ limit: 16, offset: 0 });
        if (ignore) return;
        setBoundaryRuns(response.items);
        setSelectedBoundaryRunId(response.items[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load boundary runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const selected = boundaryRuns.find((row) => row.id === selectedBoundaryRunId);
    if (!selected) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanDefectRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanDefectRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load defect runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [boundaryRuns, selectedBoundaryRunId]);

  const selectedBoundaryRun = useMemo(
    () => boundaryRuns.find((row) => row.id === selectedBoundaryRunId) ?? null,
    [boundaryRuns, selectedBoundaryRunId],
  );

  const regionMapPreview = useMemo(
    () => run?.artifacts.find((artifact) => artifact.artifact_type === "DEFECT_REGION_MAP")?.preview_data_url ?? null,
    [run],
  );
  const evidenceOverlayPreview = useMemo(
    () => run?.artifacts.find((artifact) => artifact.artifact_type === "BASELINE_EVIDENCE_OVERLAY")?.preview_data_url ?? null,
    [run],
  );

  async function submitRun(): Promise<void> {
    if (!selectedBoundaryRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanDefectFoundation({
        scan_image_id: selectedBoundaryRun.scan_image_id,
        boundary_run_id: selectedBoundaryRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Defect foundation failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-06"
        title="Defect Detection Foundation"
        description="Deterministic visual evidence infrastructure for future condition analysis."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-reconciliation" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Reconciliation
            </Link>
            <Link to="/ops#scan-defects-ops" className="rounded-2xl border border-teal-400/35 px-4 py-2 text-sm font-semibold text-teal-100">
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
        <div className="grid gap-4 xl:grid-cols-[1fr,1.2fr]">
          <div className="space-y-4">
            <label className="block text-xs font-semibold text-slate-300">
              Boundary run
              <select
                value={selectedBoundaryRunId ?? ""}
                onChange={(event) => setSelectedBoundaryRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {boundaryRuns.map((boundaryRun) => (
                  <option key={boundaryRun.id} value={boundaryRun.id}>
                    Boundary #{boundaryRun.id} · scan #{boundaryRun.scan_image_id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedBoundaryRun}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-teal-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running defect foundation…" : "Run defect foundation"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.defect_status}</span> · engine{" "}
                <span className="font-semibold text-white">{run.detection_engine_version}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 xl:grid-cols-3">
            <PreviewCard title="Source scan" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="Condition regions" src={regionMapPreview} />
            <PreviewCard title="Evidence overlay" src={evidenceOverlayPreview} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No defect foundation run loaded"
            description="Select a boundary-mapped scan and execute the defect foundation to inspect condition regions, scan-quality gates, and baseline evidence anchors."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr,0.9fr]">
            <Panel title="Condition regions">
              <div className="grid gap-2 md:grid-cols-2">
                {run.regions.map((region) => (
                  <div key={region.id} className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs text-slate-300">
                    <p className="font-semibold text-white">{region.region_type}</p>
                    <p className="mt-1 font-mono text-[10px] text-slate-400">
                      [{region.x_min}, {region.y_min}] → [{region.x_max}, {region.y_max}]
                    </p>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Quality gates">
              {run.quality_gates.length === 0 ? (
                <p className="text-sm text-slate-500">No quality-gate findings recorded.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-200">
                  {run.quality_gates.map((gate) => (
                    <li key={`${String(gate.issue_type)}-${String(gate.severity)}`} className="rounded-xl border border-white/10 px-3 py-2">
                      <p className="font-semibold text-white">
                        {String(gate.issue_type)} · {String(gate.severity)}
                      </p>
                      <p className="mt-1 text-slate-400">{String(gate.issue_message ?? "")}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Evidence summary">
              <KeyValue label="Total evidence" value={String(Number(run.evidence_summary.total_evidence_count ?? 0))} />
              <KeyValue label="Low confidence" value={String(Number(run.evidence_summary.low_confidence_count ?? 0))} />
              <KeyValue label="High confidence" value={String(Number(run.evidence_summary.high_confidence_count ?? 0))} />
              {Object.entries((run.evidence_summary.category_counts as Record<string, number> | undefined) ?? {}).map(([key, value]) => (
                <KeyValue key={key} label={key} value={String(value)} />
              ))}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
            <Panel title="Baseline evidence table">
              {run.evidence.length === 0 ? (
                <p className="text-sm text-slate-500">No evidence recorded.</p>
              ) : (
                <div className="space-y-2">
                  {run.evidence.map((row) => (
                    <EvidenceRow key={row.id} evidence={row} />
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Issues">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No defect-foundation issues recorded.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-200">
                  {run.issues.map((issue) => (
                    <li key={issue.id} className="rounded-xl border border-white/10 px-3 py-2">
                      <span className="font-semibold text-teal-100">{issue.issue_type}</span> · {issue.severity} · {issue.issue_message}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Lineage / checksums">
              <ChecksumRow label="Original scan" value={run.original_scan_checksum ?? "—"} />
              <ChecksumRow label="Normalization" value={run.normalization_checksum ?? "—"} />
              <ChecksumRow label="Boundary" value={run.boundary_checksum ?? "—"} />
              <ChecksumRow label="OCR" value={run.ocr_checksum ?? "—"} />
              <ChecksumRow label="Reconciliation" value={run.reconciliation_checksum ?? "—"} />
              <ChecksumRow label="Defect foundation" value={run.defect_checksum} />
              {run.artifacts.map((artifact) => (
                <ChecksumRow key={artifact.id} label={artifact.artifact_type} value={artifact.artifact_checksum} />
              ))}
            </Panel>
            <Panel title="History timeline">
              <ul className="space-y-2 text-xs text-slate-300">
                {run.history.map((event) => (
                  <li key={event.id} className="rounded-xl border border-white/10 px-3 py-2">
                    <p className="font-semibold text-white">{event.event_type}</p>
                    <p>{event.event_message}</p>
                    <p className="mt-1 font-mono text-[10px] text-teal-100">{event.event_checksum.slice(0, 16)}…</p>
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
        <img src={src} alt={title} className="mt-2 h-40 w-full rounded-xl border border-white/10 object-contain bg-slate-950/50" />
      ) : (
        <p className="mt-2 text-xs text-slate-500">Preview unavailable.</p>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="mb-2 rounded-xl border border-white/10 bg-slate-950/40 p-2">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-white">{value}</p>
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

function EvidenceRow({ evidence }: { evidence: ScanDefectEvidenceRead }): JSX.Element {
  const measurements = evidence.measurement_json as Record<string, number | string | Record<string, unknown>>;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white">
            {evidence.evidence_category} · {evidence.evidence_type}
          </p>
          <p className="mt-1 text-slate-400">
            {evidence.severity_hint} · confidence {evidence.confidence_score.toFixed(3)}
          </p>
        </div>
        <p className="font-mono text-[10px] text-teal-100">
          [{evidence.x_min}, {evidence.y_min}] → [{evidence.x_max}, {evidence.y_max}]
        </p>
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-3 text-slate-400">
        <span>brightness {Number(measurements.brightness_delta ?? 0).toFixed(3)}</span>
        <span>contrast {Number(measurements.contrast_delta ?? 0).toFixed(3)}</span>
        <span>edge {Number(measurements.edge_sharpness_delta ?? 0).toFixed(3)}</span>
      </div>
    </div>
  );
}
