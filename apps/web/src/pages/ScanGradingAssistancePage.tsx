import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanDefectAggregationRunRead,
  type ScanGradingAssistanceCategoryRead,
  type ScanGradingAssistanceRunDetail,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanGradingAssistancePage() {
  const [aggregationRuns, setAggregationRuns] = useState<ScanDefectAggregationRunRead[]>([]);
  const [selectedAggregationRunId, setSelectedAggregationRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanGradingAssistanceRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanDefectAggregationRuns({ limit: 16, offset: 0 });
        if (ignore) return;
        const complete = response.items.filter((row) => row.aggregation_status === "COMPLETE");
        setAggregationRuns(complete);
        setSelectedAggregationRunId(complete[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load aggregation runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const selected = aggregationRuns.find((row) => row.id === selectedAggregationRunId);
    if (!selected) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanGradingAssistanceRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanGradingAssistanceRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load grading assistance runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [aggregationRuns, selectedAggregationRunId]);

  const selectedAggregationRun = useMemo(
    () => aggregationRuns.find((row) => row.id === selectedAggregationRunId) ?? null,
    [aggregationRuns, selectedAggregationRunId],
  );

  const reportArtifact = useMemo(
    () => run?.artifacts.find((a) => a.artifact_type === "GRADING_DEBUG_PREVIEW")?.preview_data_url ?? run?.source_preview_data_url ?? null,
    [run],
  );
  const overallCategory = useMemo(
    () => run?.categories.find((category) => category.category_type === "OVERALL_SUPPORT") ?? null,
    [run],
  );

  async function submitRun(): Promise<void> {
    if (!selectedAggregationRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanGradingAssistance({
        scan_image_id: selectedAggregationRun.scan_image_id,
        aggregation_run_id: selectedAggregationRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Grading assistance failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-12"
        title="Grading Assistance Engine"
        description="Explainable PSA-aligned support ranges from deterministic evidence."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-defect-aggregation" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Aggregation context
            </Link>
            <Link to="/ops#scan-grading-assistance-ops" className="rounded-2xl border border-violet-400/35 px-4 py-2 text-sm font-semibold text-violet-100">
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
              Aggregation run
              <select
                value={selectedAggregationRunId ?? ""}
                onChange={(event) => setSelectedAggregationRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {aggregationRuns.map((aggregationRun) => (
                  <option key={aggregationRun.id} value={aggregationRun.id}>
                    Scan #{aggregationRun.scan_image_id} · aggregation #{aggregationRun.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedAggregationRun}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-violet-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running grading assistance…" : "Run grading assistance"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.assistance_status}</span> · rubric{" "}
                <span className="font-semibold text-white">{run.rubric_version}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <PreviewCard title="Source preview" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="Debug preview" src={reportArtifact} />
            <PreviewCard
              title="Support report"
              src={run?.artifacts.find((a) => a.artifact_type === "GRADING_SUPPORT_REPORT")?.preview_data_url ?? null}
            />
            <PreviewCard
              title="Review-required report"
              src={run?.artifacts.find((a) => a.artifact_type === "REVIEW_REQUIRED_REPORT")?.preview_data_url ?? null}
            />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No grading assistance run loaded"
            description="Select a completed aggregation run and execute grading assistance to inspect support ranges, pressure hints, review-required flags, and replay-safe checksum lineage."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
            <Panel title="Overall support panel">
              {overallCategory ? (
                <div className="space-y-3 text-sm text-slate-200">
                  <p className="text-lg font-semibold text-white">
                    Support Range: {overallCategory.suggested_range_low.toFixed(1)}-{overallCategory.suggested_range_high.toFixed(1)}
                  </p>
                  <p>Confidence {overallCategory.confidence_score.toFixed(3)} · status {overallCategory.category_status}</p>
                  <p>{overallCategory.summary_text}</p>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No overall support range generated.</p>
              )}
            </Panel>
            <Panel title="Review required panel">
              {run.review_flags.length === 0 ? (
                <p className="text-sm text-slate-500">No review-required flags recorded.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-200">
                  {run.review_flags.map((flag, index) => (
                    <li key={`${String(flag.flag_type)}-${index}`} className="rounded-xl border border-white/10 px-3 py-2">
                      <span className="font-semibold text-violet-100">{String(flag.flag_type)}</span> · {String(flag.severity)} · {String(flag.message)}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </section>

          <section className="mt-6">
            <Panel title="Category cards">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {run.categories
                  .filter((category) => category.category_type !== "OVERALL_SUPPORT")
                  .map((category) => (
                    <CategoryCard key={category.id} category={category} />
                  ))}
              </div>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
            <Panel title="Findings table">
              {run.findings.length === 0 ? (
                <p className="text-sm text-slate-500">No findings recorded.</p>
              ) : (
                <div className="space-y-2">
                  {run.findings.map((finding) => (
                    <FindingRow key={finding.id} finding={finding} />
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Evidence-to-grade map">
              {run.findings.length === 0 ? (
                <p className="text-sm text-slate-500">No mapping rows recorded.</p>
              ) : (
                <div className="space-y-2">
                  {run.findings.map((finding) => (
                    <div key={`map-${finding.id}`} className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs text-slate-300">
                      <p className="font-semibold text-white">
                        {finding.category_id} · {finding.finding_type}
                      </p>
                      <p className="mt-1">
                        cluster {finding.source_cluster_id ?? "n/a"} · {finding.source_detector} · pressure {finding.grade_pressure_hint}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Issues panel">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No grading assistance issues recorded.</p>
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
            <Panel title="Checksum lineage">
              <ChecksumRow label="Aggregation checksum" value={run.aggregation_checksum ?? "—"} />
              <ChecksumRow label="Grading assistance checksum" value={run.grading_assistance_checksum} />
              <ChecksumRow label="Rubric version" value={run.rubric_version} />
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
                    <p className="mt-1 font-mono text-[10px] text-violet-100">{event.event_checksum.slice(0, 16)}…</p>
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

function ChecksumRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="mb-2 rounded-xl border border-white/10 bg-slate-950/40 p-2">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 break-all font-mono text-[10px] text-white">{value}</p>
    </div>
  );
}

function CategoryCard({ category }: { category: ScanGradingAssistanceCategoryRead }): JSX.Element {
  const measurements = category.measurement_json as Record<string, number | Record<string, number>>;
  const pressureDistribution = (measurements.grade_pressure_distribution as Record<string, number> | undefined) ?? {};
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-3 text-xs">
      <p className="font-semibold uppercase tracking-[0.16em] text-violet-100">{category.category_type}</p>
      <p className="mt-2 text-white">
        Support Range {category.suggested_range_low.toFixed(1)}-{category.suggested_range_high.toFixed(1)}
      </p>
      <p className="mt-1 text-slate-400">
        {category.category_status} · evidence {category.evidence_count} · confidence {category.confidence_score.toFixed(3)}
      </p>
      <p className="mt-2 text-slate-300">{category.summary_text}</p>
      <p className="mt-2 text-slate-400">
        pressure: low {Number(pressureDistribution.LOW ?? 0)} · moderate {Number(pressureDistribution.MODERATE ?? 0)} · high {Number(pressureDistribution.HIGH ?? 0)}
      </p>
    </div>
  );
}

function FindingRow({ finding }: { finding: ScanGradingAssistanceRunDetail["findings"][number] }): JSX.Element {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white">
            {finding.finding_type} · {finding.grade_pressure_hint}
          </p>
          <p className="mt-1 text-slate-400">
            cluster {finding.source_cluster_id ?? "n/a"} · {finding.source_detector} · confidence {finding.confidence_score.toFixed(3)}
          </p>
        </div>
      </div>
      <p className="mt-2 text-slate-300">{finding.finding_text}</p>
    </div>
  );
}
