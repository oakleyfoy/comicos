import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanImageSummaryRead,
  type ScanIngestionBatchRead,
  type ScanNormalizationArtifactRead,
  type ScanNormalizationRunRead,
  type ScanNormalizationRunSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function ScanNormalizationPage() {
  const [batches, setBatches] = useState<ScanIngestionBatchRead[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null);
  const [runList, setRunList] = useState<ScanNormalizationRunSummaryRead[]>([]);
  const [currentRun, setCurrentRun] = useState<ScanNormalizationRunRead | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ScanNormalizationArtifactRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await apiClient.listScanBatches({ limit: 8, offset: 0 });
        const detailRows = await Promise.all(resp.items.map((row) => apiClient.getScanBatch(row.id)));
        if (ignore) return;
        setBatches(detailRows);
        const firstBatch = detailRows[0] ?? null;
        const firstImage = firstBatch?.images.find((row) => row.processing_status !== "FAILED") ?? null;
        setSelectedBatchId(firstBatch?.id ?? null);
        setSelectedImageId(firstImage?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load scan normalization inputs.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedImageId) {
      setRunList([]);
      setCurrentRun(null);
      setSelectedArtifact(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const resp = await apiClient.listNormalizationRuns({ scan_image_id: selectedImageId, limit: 20, offset: 0 });
        if (ignore) return;
        setRunList(resp.items);
        if (resp.items[0]) {
          const detail = await apiClient.getNormalizationRun(resp.items[0].id);
          if (ignore) return;
          setCurrentRun(detail);
          setSelectedArtifact(detail.artifacts.find((artifact) => artifact.id === detail.final_artifact_id) ?? null);
        } else {
          setCurrentRun(null);
          setSelectedArtifact(null);
        }
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load normalization runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedImageId]);

  const selectedBatch = useMemo(
    () => batches.find((row) => row.id === selectedBatchId) ?? null,
    [batches, selectedBatchId],
  );
  const selectableImages = useMemo(
    () => selectedBatch?.images.filter((row) => row.processing_status !== "FAILED") ?? [],
    [selectedBatch],
  );
  const selectedImage = useMemo(
    () => selectableImages.find((row) => row.id === selectedImageId) ?? null,
    [selectableImages, selectedImageId],
  );

  async function runNormalization(): Promise<void> {
    if (!selectedImageId) {
      setError("Choose a scan image first.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanNormalization({ scan_image_id: selectedImageId });
      setCurrentRun(detail);
      setSelectedArtifact(detail.artifacts.find((artifact) => artifact.id === detail.final_artifact_id) ?? null);
      const refreshed = await apiClient.listNormalizationRuns({ scan_image_id: selectedImageId, limit: 20, offset: 0 });
      setRunList(refreshed.items);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Scan normalization failed.");
    } finally {
      setRunning(false);
    }
  }

  async function inspectArtifact(artifactId: number): Promise<void> {
    try {
      const detail = await apiClient.getNormalizationArtifacts(artifactId);
      setSelectedArtifact(detail);
    } catch (artifactErr) {
      setError(artifactErr instanceof ApiError ? artifactErr.message : "Unable to load artifact preview.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-02"
        title="Scan normalization"
        description="Deterministic rotation, crop, perspective, color, and derivative generation only. Originals remain immutable."
        actions={
          <>
            <Link
              to="/dashboard"
              className="inline-flex rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-violet-300/35 hover:bg-white/5"
            >
              Dashboard
            </Link>
            <Link
              to="/ops#scan-normalization-ops"
              className="inline-flex rounded-2xl border border-violet-300/35 px-4 py-2 text-sm font-semibold text-violet-100 transition hover:border-violet-200/50 hover:bg-violet-500/10"
            >
              Ops diagnostics
            </Link>
          </>
        }
      />

      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15">
        <div className="grid gap-4 xl:grid-cols-[1fr,1.2fr]">
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-slate-300">
                Scan batch
                <select
                  value={selectedBatchId ?? ""}
                  onChange={(event) => {
                    const nextBatchId = Number(event.target.value);
                    const nextBatch = batches.find((row) => row.id === nextBatchId) ?? null;
                    const nextImage = nextBatch?.images.find((row) => row.processing_status !== "FAILED") ?? null;
                    setSelectedBatchId(nextBatchId || null);
                    setSelectedImageId(nextImage?.id ?? null);
                  }}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  <option value="">Select batch</option>
                  {batches.map((batch) => (
                    <option key={batch.id} value={batch.id}>
                      #{batch.id} · {batch.source_type} · {batch.image_count} images
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-300">
                Scan image
                <select
                  value={selectedImageId ?? ""}
                  onChange={(event) => setSelectedImageId(Number(event.target.value) || null)}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  <option value="">Select image</option>
                  {selectableImages.map((image) => (
                    <option key={image.id} value={image.id}>
                      #{image.id} · {image.original_filename}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="rounded-2xl border border-dashed border-violet-300/35 bg-violet-500/5 p-4">
              <p className="text-sm text-slate-200">
                Run deterministic normalization on the selected immutable scan image.
              </p>
              <p className="mt-1 text-xs text-slate-400">
                The pipeline emits append-only artifacts and history for orientation, crop cleanup, perspective, color,
                final normalization, and thumbnail generation.
              </p>
              <button
                type="button"
                onClick={() => void runNormalization()}
                disabled={running || !selectedImageId}
                className="mt-4 rounded-2xl bg-violet-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 transition hover:bg-violet-300 disabled:opacity-45"
              >
                {running ? "Running normalization…" : "Run deterministic normalization"}
              </button>
            </div>
            {selectedImage ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Image" value={`#${selectedImage.id}`} />
                <StatCard label="Dimensions" value={selectedImage.width && selectedImage.height ? `${selectedImage.width}×${selectedImage.height}` : "—"} />
                <StatCard label="DPI" value={selectedImage.dpi_x ? `${selectedImage.dpi_x}` : "—"} />
                <StatCard label="Checksum" value={`${selectedImage.sha256_checksum.slice(0, 10)}…`} />
              </div>
            ) : null}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <PreviewCard
              title="Before"
              description="Immutable source preview"
              src={currentRun?.source_preview_data_url ?? null}
            />
            <PreviewCard
              title="After"
              description="Final normalized preview"
              src={(selectedArtifact?.preview_data_url ?? currentRun?.final_preview_data_url) ?? null}
            />
          </div>
        </div>
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Run detail</h2>
            <p className="mt-1 text-xs text-slate-400">
              Checksum lineage, issue flags, and append-only history for the selected normalization run.
            </p>
          </div>
        </div>
        {!loading && !currentRun ? (
          <div className="mt-4">
            <EmptyState
              title="No normalization run selected"
              description="Choose a scan image and run the deterministic preprocessing pipeline to inspect artifacts and lineage."
            />
          </div>
        ) : currentRun ? (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Run" value={`#${currentRun.id}`} />
              <StatCard label="Artifacts" value={String(currentRun.artifact_count)} />
              <StatCard label="Issues" value={String(currentRun.issue_count)} />
              <StatCard label="Orientation" value={currentRun.orientation_code} />
            </div>

            <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr,0.9fr]">
              <div className="space-y-4">
                <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                  <h3 className="text-sm font-semibold text-white">Artifacts</h3>
                  <div className="mt-3 space-y-2">
                    {currentRun.artifacts.map((artifact) => (
                      <button
                        key={artifact.id}
                        type="button"
                        onClick={() => void inspectArtifact(artifact.id)}
                        className="flex w-full items-center justify-between rounded-2xl border border-white/10 px-3 py-2 text-left text-xs text-slate-200 transition hover:border-violet-300/35 hover:bg-white/5"
                      >
                        <span>{artifact.artifact_type}</span>
                        <span className="font-mono text-violet-100">{artifact.artifact_checksum.slice(0, 12)}…</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                  <h3 className="text-sm font-semibold text-white">Issues</h3>
                  {currentRun.issues.length === 0 ? (
                    <p className="mt-3 text-sm text-slate-500">No deterministic normalization issues were recorded.</p>
                  ) : (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {currentRun.issues.map((issue) => (
                        <span
                          key={issue.id}
                          className="inline-flex rounded-full border border-violet-300/35 bg-violet-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-100"
                        >
                          {issue.issue_type}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                <h3 className="text-sm font-semibold text-white">Replay-safe checksum panel</h3>
                <div className="mt-3 space-y-3 text-xs text-slate-300">
                  <ChecksumRow label="Source" value={currentRun.source_sha256_checksum} />
                  {currentRun.history.map((row) => (
                    <ChecksumRow key={row.id} label={row.stage_name} value={row.to_checksum ?? row.from_checksum ?? "—"} />
                  ))}
                  <ChecksumRow label="Run checksum" value={currentRun.normalization_checksum} />
                </div>
              </div>
            </div>

            <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3">Order</th>
                    <th className="p-3">Stage</th>
                    <th className="p-3">Event</th>
                    <th className="p-3">From</th>
                    <th className="p-3">To</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {currentRun.history.map((row) => (
                    <tr key={row.id} className="align-top">
                      <td className="p-3 font-mono">{row.history_order}</td>
                      <td className="p-3">{row.stage_name}</td>
                      <td className="p-3">{row.event_type}</td>
                      <td className="p-3 font-mono text-slate-400">{row.from_checksum ? `${row.from_checksum.slice(0, 12)}…` : "—"}</td>
                      <td className="p-3 font-mono text-violet-100">{row.to_checksum ? `${row.to_checksum.slice(0, 12)}…` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15">
        <h2 className="text-sm font-semibold text-white">Recent runs for selected image</h2>
        {runList.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No prior normalization runs for this image.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {runList.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => void apiClient.getNormalizationRun(run.id).then((detail) => {
                  setCurrentRun(detail);
                  setSelectedArtifact(detail.artifacts.find((artifact) => artifact.id === detail.final_artifact_id) ?? null);
                })}
                className="flex w-full items-center justify-between rounded-2xl border border-white/10 px-4 py-3 text-left text-xs text-slate-200 transition hover:border-violet-300/35 hover:bg-white/5"
              >
                <span>
                  #{run.id} · {run.normalization_status} · {run.orientation_code}
                </span>
                <span className="font-mono text-violet-100">{run.normalization_checksum.slice(0, 12)}…</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </AppShell>
  );
}

function PreviewCard({
  title,
  description,
  src,
}: {
  title: string;
  description: string;
  src: string | null;
}): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <p className="mt-1 text-xs text-slate-400">{description}</p>
      {src ? (
        <img src={src} alt={title} className="mt-3 h-72 w-full rounded-2xl border border-white/10 object-contain bg-slate-950/50" />
      ) : (
        <p className="mt-3 text-sm text-slate-500">Preview becomes available after a run is loaded.</p>
      )}
    </div>
  );
}

function ChecksumRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-3">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 break-all font-mono text-[11px] text-white">{value}</p>
    </div>
  );
}
