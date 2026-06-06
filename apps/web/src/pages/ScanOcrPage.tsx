import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanImageSummaryRead,
  type ScanOcrCandidateRead,
  type ScanOcrRunDetail,
  type ScanOcrTextRegionRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanOcrPage() {
  const [images, setImages] = useState<ScanImageSummaryRead[]>([]);
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanOcrRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeRegionId, setActiveRegionId] = useState<number | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const batches = await apiClient.listScanBatches({ limit: 8, offset: 0 });
        const details = await Promise.all(batches.items.map((row) => apiClient.getScanBatch(row.id)));
        const flattened = details.flatMap((batch) => batch.images.filter((row) => row.processing_status !== "FAILED"));
        if (ignore) return;
        setImages(flattened);
        setSelectedImageId(flattened[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan images.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedImageId) {
      setRun(null);
      setActiveRegionId(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const resp = await apiClient.listScanOcrRuns({ scan_image_id: selectedImageId, limit: 1, offset: 0 });
        if (ignore || !resp.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanOcrRun(resp.items[0].id);
        if (!ignore) {
          setRun(detail);
          setActiveRegionId(detail.regions[0]?.id ?? null);
        }
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load OCR runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedImageId]);

  const groupedCandidates = useMemo(() => {
    const groups: Record<string, ScanOcrCandidateRead[]> = {};
    for (const candidate of run?.candidates ?? []) {
      groups[candidate.candidate_type] = [...(groups[candidate.candidate_type] ?? []), candidate];
    }
    return groups;
  }, [run]);

  const activeRegion = useMemo(
    () => run?.regions.find((row) => row.id === activeRegionId) ?? run?.regions[0] ?? null,
    [activeRegionId, run],
  );

  async function submitRun(): Promise<void> {
    if (!selectedImageId) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanOcr({ scan_image_id: selectedImageId });
      setRun(detail);
      setActiveRegionId(detail.regions[0]?.id ?? null);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "OCR execution failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-04"
        title="OCR Intelligence Layer"
        description="Deterministic comic metadata extraction from normalized cover scans."
        actions={
          <Link to="/scan-boundary" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
            Boundary Mapping
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
              Source scan
              <select
                value={selectedImageId ?? ""}
                onChange={(event) => setSelectedImageId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {images.map((image) => (
                  <option key={image.id} value={image.id}>
                    #{image.id} · {image.original_filename}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={running || !selectedImageId}
              onClick={() => void submitRun()}
              className="rounded-2xl bg-teal-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {running ? "Running OCR…" : "Run OCR"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.ocr_status}</span> · average region confidence{" "}
                <span className="font-semibold text-white">{String(run.confidence_summary.average_region_confidence ?? "—")}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 xl:grid-cols-3">
            <PreviewCard title="Normalized source" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="OCR overlay" src={run?.ocr_overlay_preview_data_url ?? null} />
            <PreviewCard title="OCR region map" src={run?.ocr_region_map_preview_data_url ?? null} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState title="No OCR run loaded" description="Select a scan image and run OCR to inspect extracted text, candidates, issues, and lineage." />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[0.8fr,1.2fr]">
            <Panel title="OCR regions">
              <div className="space-y-2">
                {run.regions.map((region) => (
                  <button
                    key={region.id}
                    type="button"
                    onClick={() => setActiveRegionId(region.id)}
                    className={`w-full rounded-xl border px-3 py-2 text-left text-xs ${
                      activeRegion?.id === region.id ? "border-teal-400/50 bg-teal-400/10 text-white" : "border-white/10 bg-slate-950/35 text-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{region.region_type}</span>
                      <span>{region.confidence_score.toFixed(3)}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-[11px] text-slate-400">{region.normalized_text ?? "No text detected."}</p>
                  </button>
                ))}
              </div>
            </Panel>
            <Panel title="Extracted text">
              {activeRegion ? (
                <div className="space-y-4 text-sm text-slate-300">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Raw OCR</p>
                      <pre className="mt-2 whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/45 p-3 text-xs text-white">
                        {activeRegion.extracted_text || "No raw text"}
                      </pre>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Normalized OCR</p>
                      <pre className="mt-2 whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/45 p-3 text-xs text-white">
                        {activeRegion.normalized_text || "No normalized text"}
                      </pre>
                    </div>
                  </div>
                  <dl className="grid grid-cols-2 gap-2 text-xs">
                    <Item label="Region type" value={activeRegion.region_type} />
                    <Item label="Confidence" value={activeRegion.confidence_score.toFixed(3)} />
                    <Item label="x / y" value={`${activeRegion.x_min}, ${activeRegion.y_min}`} />
                    <Item label="w / h" value={`${activeRegion.width_px} × ${activeRegion.height_px}`} />
                  </dl>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No OCR region selected.</p>
              )}
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Candidates">
              <div className="space-y-4">
                {(["TITLE", "ISSUE_NUMBER", "PUBLISHER", "DATE", "PRICE"] as const).map((group) => (
                  <CandidateGroup key={group} title={group} items={groupedCandidates[group] ?? []} />
                ))}
              </div>
            </Panel>
            <Panel title="Issues">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No OCR issues recorded.</p>
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
              <ChecksumRow label="OCR run" value={run.ocr_checksum} />
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

function CandidateGroup({ title, items }: { title: string; items: ScanOcrCandidateRead[] }): JSX.Element {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">No candidates.</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item) => (
            <div key={item.id} className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2 text-xs text-slate-200">
              <p className="font-semibold text-white">{item.normalized_candidate_value ?? item.candidate_value}</p>
              <p className="mt-1 text-slate-400">Raw: {item.candidate_value}</p>
              <p className="mt-1 text-slate-400">Confidence: {item.confidence_score.toFixed(3)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
