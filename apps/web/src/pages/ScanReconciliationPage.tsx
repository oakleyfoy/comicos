import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanOcrRunRead,
  type ScanReconciliationCandidateRead,
  type ScanReconciliationRunDetail,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanReconciliationPage() {
  const [ocrRuns, setOcrRuns] = useState<ScanOcrRunRead[]>([]);
  const [selectedOcrRunId, setSelectedOcrRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanReconciliationRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanOcrRuns({ limit: 12, offset: 0 });
        if (ignore) return;
        setOcrRuns(response.items);
        setSelectedOcrRunId(response.items[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load OCR runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const selected = ocrRuns.find((row) => row.id === selectedOcrRunId);
    if (!selected) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanReconciliationRuns({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanReconciliationRun(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load reconciliation runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [ocrRuns, selectedOcrRunId]);

  const selectedOcrRun = useMemo(() => ocrRuns.find((row) => row.id === selectedOcrRunId) ?? null, [ocrRuns, selectedOcrRunId]);

  async function submitRun(): Promise<void> {
    if (!selectedOcrRun) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanReconciliation({
        scan_image_id: selectedOcrRun.scan_image_id,
        ocr_run_id: selectedOcrRun.id,
      });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Reconciliation failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-05"
        title="OCR Reconciliation Engine"
        description="Deterministic comic identity resolution from OCR intelligence."
        actions={
          <Link to="/scan-ocr" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
            OCR Intelligence
          </Link>
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
              OCR run
              <select
                value={selectedOcrRunId ?? ""}
                onChange={(event) => setSelectedOcrRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {ocrRuns.map((ocrRun) => (
                  <option key={ocrRun.id} value={ocrRun.id}>
                    OCR #{ocrRun.id} · scan #{ocrRun.scan_image_id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedOcrRun}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-teal-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running reconciliation…" : "Run reconciliation"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.reconciliation_status}</span> · dataset{" "}
                <span className="font-semibold text-white">{run.canonical_dataset_version.slice(0, 12)}…</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <PreviewCard title="OCR source" src={run?.source_preview_data_url ?? null} />
            <Panel title="Match summary">
              {run?.decision ? (
                <div className="space-y-2 text-sm text-slate-300">
                  <p>
                    Status <span className="font-semibold text-white">{run.decision.decision_status}</span>
                  </p>
                  <p>
                    Confidence <span className="font-semibold text-white">{run.decision.final_confidence_score.toFixed(3)}</span>
                  </p>
                  <p className="text-slate-400">{run.decision.decision_reason}</p>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No reconciliation decision loaded.</p>
              )}
            </Panel>
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState title="No reconciliation run loaded" description="Select an OCR run and execute reconciliation to inspect ranked canonical comic matches and decision history." />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
            <Panel title="Ranked candidates">
              {run.candidates.length === 0 ? (
                <p className="text-sm text-slate-500">No canonical candidates recorded.</p>
              ) : (
                <div className="space-y-2">
                  {run.candidates.map((candidate) => (
                    <CandidateRow key={candidate.id} candidate={candidate} selectedId={run.decision?.selected_candidate_id ?? null} />
                  ))}
                </div>
              )}
            </Panel>
            <Panel title="Canonical metadata">
              {run.selected_candidate ? (
                <dl className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                  <Item label="canonical_comic_id" value={String(run.selected_candidate.canonical_comic_id ?? "—")} />
                  <Item label="publisher" value={run.selected_candidate.publisher ?? "—"} />
                  <Item label="title" value={run.selected_candidate.series_title ?? "—"} />
                  <Item label="issue" value={run.selected_candidate.issue_number ?? "—"} />
                  <Item label="variant" value={run.selected_candidate.variant_description ?? "—"} />
                  <Item label="publication_date" value={run.selected_candidate.publication_date ?? "—"} />
                </dl>
              ) : (
                <p className="text-sm text-slate-500">No canonical match selected.</p>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Issues">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No reconciliation issues recorded.</p>
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
              <ChecksumRow label="Original scan" value={run.original_scan_checksum ?? "—"} />
              <ChecksumRow label="Normalization" value={run.normalization_checksum ?? "—"} />
              <ChecksumRow label="Boundary" value={run.boundary_checksum ?? "—"} />
              <ChecksumRow label="OCR" value={run.ocr_checksum ?? "—"} />
              <ChecksumRow label="Reconciliation" value={run.reconciliation_checksum} />
              <ChecksumRow label="Dataset version" value={run.canonical_dataset_version} />
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
        <img src={src} alt={title} className="mt-2 h-40 w-full rounded-xl border border-white/10 object-contain bg-slate-950/50" />
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

function Item({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-mono text-white">{value}</dd>
    </>
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

function CandidateRow({
  candidate,
  selectedId,
}: {
  candidate: ScanReconciliationCandidateRead;
  selectedId: number | null;
}): JSX.Element {
  const selected = selectedId === candidate.id;
  return (
    <div className={`rounded-xl border px-3 py-2 text-xs ${selected ? "border-teal-400/50 bg-teal-400/10" : "border-white/10 bg-slate-950/35"}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white">
            #{candidate.candidate_rank} · {candidate.publisher ?? "—"} · {candidate.series_title ?? "—"} #{candidate.issue_number ?? "—"}
          </p>
          <p className="mt-1 text-slate-400">{candidate.variant_description ?? "No variant description"}</p>
        </div>
        <p className="font-mono text-white">{candidate.confidence_score.toFixed(3)}</p>
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-3 text-slate-400">
        <span>title {candidate.title_similarity_score.toFixed(3)}</span>
        <span>issue {candidate.issue_similarity_score.toFixed(3)}</span>
        <span>publisher {candidate.publisher_similarity_score.toFixed(3)}</span>
      </div>
    </div>
  );
}
