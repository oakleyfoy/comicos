import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanDefectRunRead,
  type ScanStructuralDamageEvidenceRead,
  type ScanStructuralDamageRunDetail,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanStructuralDamagePage() {
  const [defectRuns, setDefectRuns] = useState<ScanDefectRunRead[]>([]);
  const [selectedDefectRunId, setSelectedDefectRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanStructuralDamageRunDetail | null>(null);
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
        const response = await apiClient.listScanStructuralDamageRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanStructuralDamageRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load structural runs.");
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

  const regionPreview = useMemo(
    () => run?.artifacts.find((a) => a.artifact_type === "STRUCTURAL_REGION_PREVIEW")?.preview_data_url ?? run?.structural_region_preview_data_url ?? null,
    [run],
  );
  const deformationMap = useMemo(
    () => run?.artifacts.find((a) => a.artifact_type === "STRUCTURAL_DEFORMATION_MAP")?.preview_data_url ?? null,
    [run],
  );
  const overlayPreview = useMemo(
    () => run?.artifacts.find((a) => a.artifact_type === "STRUCTURAL_DAMAGE_OVERLAY")?.preview_data_url ?? null,
    [run],
  );
  const selectedEvidence = useMemo(() => run?.evidence[0] ?? null, [run]);

  async function submitRun(): Promise<void> {
    if (!selectedDefectRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanStructuralDamageDetection({
        scan_image_id: selectedDefectRun.scan_image_id,
        defect_run_id: selectedDefectRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Structural damage detection failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-10"
        title="Structural Damage Detection"
        description="Deterministic large-scale structural evidence analysis."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-defects" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Defect foundation
            </Link>
            <Link to="/ops#scan-structural-damage-ops" className="rounded-2xl border border-cyan-400/35 px-4 py-2 text-sm font-semibold text-cyan-100">
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
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running structural detection…" : "Run structural damage detection"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.detection_status}</span> · engine{" "}
                <span className="font-semibold text-white">{run.engine_version}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <PreviewCard title="Source scan preview" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="Structural region preview" src={regionPreview} />
            <PreviewCard title="Structural deformation map" src={deformationMap} />
            <PreviewCard title="Structural overlay" src={overlayPreview} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No structural run loaded"
            description="Select a completed defect foundation run and execute structural damage detection to inspect deterministic large-scale evidence, deformation maps, and replay-safe lineage."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
            <Panel title="Evidence table">
              {run.evidence.length === 0 ? (
                <p className="text-sm text-slate-500">No structural evidence recorded.</p>
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
                <pre className="max-h-72 overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-cyan-100">
                  {JSON.stringify(selectedEvidence.measurement_json, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-slate-500">Run detection to populate measurements.</p>
              )}
              <div className="mt-3">
                <KeyValue label="Total evidence" value={String(Number(run.evidence_summary.total_evidence_count ?? 0))} />
                <KeyValue label="Low confidence" value={String(Number(run.evidence_summary.low_confidence_count ?? 0))} />
                <KeyValue label="Major hints" value={String(Number(run.evidence_summary.major_count ?? 0))} />
              </div>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Issues panel">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No pipeline issues recorded.</p>
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
            <Panel title="Checksum lineage">
              <ChecksumRow label="Original scan" value={run.original_scan_checksum ?? "—"} />
              <ChecksumRow label="Normalization" value={run.normalization_checksum ?? "—"} />
              <ChecksumRow label="Boundary" value={run.boundary_checksum ?? "—"} />
              <ChecksumRow label="Defect foundation" value={run.defect_checksum ?? "—"} />
              <ChecksumRow label="Structural damage manifest" value={run.structural_damage_checksum} />
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
                    <p className="mt-1 font-mono text-[10px] text-cyan-100">{event.event_checksum.slice(0, 16)}…</p>
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

function EvidenceRow({ evidence }: { evidence: ScanStructuralDamageEvidenceRead }): JSX.Element {
  const measurements = evidence.measurement_json as Record<string, number>;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white">
            {evidence.evidence_type} · {evidence.evidence_category}
          </p>
          <p className="mt-1 text-slate-400">
            rank {evidence.evidence_rank} · {evidence.region_type} · {evidence.severity_hint} · confidence {evidence.confidence_score.toFixed(3)}
          </p>
        </div>
        <p className="font-mono text-[10px] text-cyan-100">
          [{evidence.x_min}, {evidence.y_min}] → [{evidence.x_max}, {evidence.y_max}]
        </p>
      </div>
      <div className="mt-2 grid gap-2 text-slate-400 md:grid-cols-3">
        <span>area {Number(measurements.pixel_area ?? 0)}</span>
        <span>line {Number(measurements.line_length ?? 0)}</span>
        <span>align {Number(measurements.alignment_delta ?? 0).toFixed(3)}</span>
      </div>
    </div>
  );
}
