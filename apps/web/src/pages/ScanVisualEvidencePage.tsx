import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanGradingAssistanceRunRead,
  type ScanVisualEvidenceRunDetail,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanVisualEvidencePage() {
  const [gradingRuns, setGradingRuns] = useState<ScanGradingAssistanceRunRead[]>([]);
  const [selectedGradingRunId, setSelectedGradingRunId] = useState<number | null>(null);
  const [selectedPackageType, setSelectedPackageType] = useState<string>("FULL_REVIEW_PACKAGE");
  const [run, setRun] = useState<ScanVisualEvidenceRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanGradingAssistanceRuns({ limit: 16, offset: 0 });
        if (ignore) return;
        const complete = response.items.filter((row) => row.assistance_status === "COMPLETE");
        setGradingRuns(complete);
        setSelectedGradingRunId(complete[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading assistance runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const selected = gradingRuns.find((row) => row.id === selectedGradingRunId);
    if (!selected) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanVisualEvidenceRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanVisualEvidenceRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load visual evidence runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [gradingRuns, selectedGradingRunId]);

  const selectedGradingRun = useMemo(
    () => gradingRuns.find((row) => row.id === selectedGradingRunId) ?? null,
    [gradingRuns, selectedGradingRunId],
  );

  const selectedPackage = useMemo(
    () => run?.packages.find((pkg) => pkg.package_type === selectedPackageType) ?? run?.packages[0] ?? null,
    [run, selectedPackageType],
  );

  const packageItems = useMemo(() => {
    if (!run || !selectedPackage) return [];
    return run.items.filter((item) => item.package_id === selectedPackage.id);
  }, [run, selectedPackage]);

  async function submitRun(): Promise<void> {
    if (!selectedGradingRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanVisualEvidence({
        scan_image_id: selectedGradingRun.scan_image_id,
        aggregation_run_id: selectedGradingRun.aggregation_run_id,
        grading_assistance_run_id: selectedGradingRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Visual evidence generation failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-13"
        title="Visual Evidence System"
        description="Deterministic review packets and evidence overlays from scan intelligence."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-grading-assistance" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Grading support
            </Link>
            <Link to="/ops#scan-visual-evidence-ops" className="rounded-2xl border border-cyan-400/35 px-4 py-2 text-sm font-semibold text-cyan-100">
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
              Grading assistance run
              <select
                value={selectedGradingRunId ?? ""}
                onChange={(event) => setSelectedGradingRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {gradingRuns.map((gradingRun) => (
                  <option key={gradingRun.id} value={gradingRun.id}>
                    Scan #{gradingRun.scan_image_id} · grading #{gradingRun.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedGradingRun}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Generating visual evidence…" : "Run visual evidence generation"}
            </button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <PreviewCard title="Source preview" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="Unified overlay" src={run?.overlay_preview_data_url ?? null} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No visual evidence run loaded"
            description="Select a grading assistance run and generate visual evidence to inspect packages, annotations, review packets, and checksum lineage."
          />
        </div>
      ) : (
        <>
          <section className="mt-6">
            <Panel title="Evidence package selector">
              <div className="flex flex-wrap gap-2">
                {run.packages.map((pkg) => (
                  <button
                    key={pkg.id}
                    type="button"
                    onClick={() => setSelectedPackageType(pkg.package_type)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
                      selectedPackageType === pkg.package_type
                        ? "border-cyan-400/50 bg-cyan-950/40 text-cyan-100"
                        : "border-white/10 text-slate-300"
                    }`}
                  >
                    {pkg.package_type.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
              {selectedPackage ? (
                <p className="mt-3 text-sm text-slate-300">{selectedPackage.package_summary}</p>
              ) : null}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
            <Panel title="Evidence items">
              {packageItems.length === 0 ? (
                <p className="text-sm text-slate-500">No items in this package.</p>
              ) : (
                <div className="space-y-2">
                  {packageItems.map((item) => (
                    <div key={item.id} className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs text-slate-300">
                      <p className="font-semibold text-white">
                        {item.item_title} · {item.source_system}
                      </p>
                      <p className="mt-1">
                        record #{item.source_record_id} · confidence {item.confidence_score.toFixed(3)}
                        {item.severity_hint ? ` · ${item.severity_hint}` : ""}
                      </p>
                      <p className="mt-1 text-slate-400">{item.item_summary}</p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Annotation table">
              {run.annotations.length === 0 ? (
                <p className="text-sm text-slate-500">No annotations recorded.</p>
              ) : (
                <div className="max-h-96 space-y-2 overflow-auto">
                  {run.annotations.map((ann) => (
                    <div key={ann.id} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300">
                      <p className="font-semibold text-cyan-100">
                        {ann.annotation_type} · {ann.label}
                      </p>
                      <p className="mt-1 font-mono text-[10px]">
                        [{ann.x_min}, {ann.y_min}] → [{ann.x_max}, {ann.y_max}] · order {ann.display_order}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Review packet panel">
              <p className="text-sm font-semibold text-slate-900">{selectedPackage?.package_title ?? "Review packet"}</p>
              <ul className="mt-2 space-y-1 text-xs text-slate-400">
                {run.artifacts
                  .filter((a) => a.artifact_type.includes("REPORT") || a.artifact_type.includes("PACKET") || a.artifact_type.includes("EXPORT"))
                  .map((artifact) => (
                    <li key={artifact.id}>
                      {artifact.artifact_type} · {artifact.artifact_checksum.slice(0, 12)}…
                    </li>
                  ))}
              </ul>
            </Panel>
            <Panel title="Checksum lineage">
              <ChecksumRow label="Visual evidence checksum" value={run.visual_evidence_checksum} />
              <ChecksumRow label="Aggregation checksum" value={run.aggregation_checksum ?? "—"} />
              <ChecksumRow label="Grading assistance checksum" value={run.grading_assistance_checksum ?? "—"} />
              <ChecksumRow label="Defect checksum" value={run.defect_checksum ?? "—"} />
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Issues panel">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No visual evidence issues recorded.</p>
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
