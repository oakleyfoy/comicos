import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanDefectRunRead,
  type ScanSpineTickEvidenceRead,
  type ScanSpineTickRunDetail,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanSpineTicksPage() {
  const [defectRuns, setDefectRuns] = useState<ScanDefectRunRead[]>([]);
  const [selectedDefectRunId, setSelectedDefectRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanSpineTickRunDetail | null>(null);
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
        const response = await apiClient.listScanSpineTickRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanSpineTickRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load spine tick runs.");
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

  const spineRegionPreview = useMemo(
    () => run?.artifacts.find((artifact) => artifact.artifact_type === "SPINE_REGION_PREVIEW")?.preview_data_url ?? run?.spine_region_preview_data_url ?? null,
    [run],
  );
  const edgeMapPreview = useMemo(
    () => run?.artifacts.find((artifact) => artifact.artifact_type === "SPINE_EDGE_MAP")?.preview_data_url ?? null,
    [run],
  );
  const overlayPreview = useMemo(
    () => run?.artifacts.find((artifact) => artifact.artifact_type === "SPINE_TICK_OVERLAY")?.preview_data_url ?? null,
    [run],
  );
  const selectedEvidence = useMemo(() => run?.evidence[0] ?? null, [run]);

  async function submitRun(): Promise<void> {
    if (!selectedDefectRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanSpineTickDetection({
        scan_image_id: selectedDefectRun.scan_image_id,
        defect_run_id: selectedDefectRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Spine tick detection failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-07"
        title="Spine Tick Detection"
        description="Deterministic spine stress evidence analysis."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-defects" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Defect foundation
            </Link>
            <Link to="/ops#scan-spine-ticks-ops" className="rounded-2xl border border-teal-400/35 px-4 py-2 text-sm font-semibold text-teal-100">
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
              Defect foundation run
              <select
                value={selectedDefectRunId ?? ""}
                onChange={(event) => setSelectedDefectRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {defectRuns.map((defectRun) => (
                  <option key={defectRun.id} value={defectRun.id}>
                    Defect #{defectRun.id} · scan #{defectRun.scan_image_id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedDefectRun}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-teal-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running spine detection…" : "Run spine tick detection"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.detection_status}</span> · engine{" "}
                <span className="font-semibold text-white">{run.engine_version}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <PreviewCard title="Source scan" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="Spine region" src={spineRegionPreview} />
            <PreviewCard title="Spine edge map" src={edgeMapPreview} />
            <PreviewCard title="Spine tick overlay" src={overlayPreview} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No spine tick run loaded"
            description="Select a completed defect foundation run and execute spine tick detection to inspect spine stress evidence, measurements, and replay-safe lineage."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
            <Panel title="Evidence table">
              {run.evidence.length === 0 ? (
                <p className="text-sm text-slate-500">No spine tick evidence recorded.</p>
              ) : (
                <div className="space-y-2">
                  {run.evidence.map((row) => (
                    <EvidenceRow key={row.id} evidence={row} />
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Measurement panel">
              {selectedEvidence ? (
                <pre className="max-h-72 overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-teal-100">
                  {JSON.stringify(selectedEvidence.measurement_json, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-slate-500">Select evidence by running detection.</p>
              )}
              <div className="mt-3">
                <KeyValue label="Total ticks" value={String(Number(run.evidence_summary.total_tick_count ?? 0))} />
                <KeyValue label="Low confidence" value={String(Number(run.evidence_summary.low_confidence_count ?? 0))} />
                <KeyValue label="Major hints" value={String(Number(run.evidence_summary.major_count ?? 0))} />
              </div>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Issues">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No pipeline issues recorded.</p>
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
            <Panel title="Lineage / checksums">
              <ChecksumRow label="Defect foundation" value={run.defect_checksum ?? "—"} />
              <ChecksumRow label="Spine tick manifest" value={run.spine_tick_checksum} />
              {run.artifacts.map((artifact) => (
                <ChecksumRow key={artifact.id} label={artifact.artifact_type} value={artifact.artifact_checksum} />
              ))}
            </Panel>
          </section>

          <section className="mt-6">
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
        <img src={src} alt={title} className="mt-2 h-36 w-full rounded-xl border border-white/10 object-contain bg-slate-950/50" />
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

function EvidenceRow({ evidence }: { evidence: ScanSpineTickEvidenceRead }): JSX.Element {
  const measurements = evidence.measurement_json as Record<string, number>;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white">
            Rank {evidence.tick_rank} · {evidence.severity_hint}
          </p>
          <p className="mt-1 text-slate-400">
            confidence {evidence.confidence_score.toFixed(3)} · angle {evidence.angle_degrees.toFixed(1)}° · overlap{" "}
            {evidence.spine_overlap_ratio.toFixed(3)}
          </p>
        </div>
        <p className="font-mono text-[10px] text-teal-100">
          [{evidence.x_min}, {evidence.y_min}] → [{evidence.x_max}, {evidence.y_max}]
        </p>
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-3 text-slate-400">
        <span>length {Number(measurements.pixel_length ?? 0)}</span>
        <span>width {Number(measurements.pixel_width ?? 0)}</span>
        <span>edge disruption {Number(measurements.edge_disruption_ratio ?? 0).toFixed(3)}</span>
      </div>
    </div>
  );
}
