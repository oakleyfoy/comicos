import { type Dispatch, type SetStateAction, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type ScanBatchUploadPayload, type ScanIngestionBatchRead, type ScanIngestionSourceType } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const SOURCE_OPTIONS: ScanIngestionSourceType[] = ["EPSON", "FUJITSU", "MOBILE", "ZIP_IMPORT", "MANUAL_UPLOAD"];

export function ScanIngestionPage() {
  const [sourceType, setSourceType] = useState<ScanIngestionSourceType>("MANUAL_UPLOAD");
  const [scannerMake, setScannerMake] = useState("");
  const [scannerModel, setScannerModel] = useState("");
  const [scannerProfile, setScannerProfile] = useState("");
  const [colorMode, setColorMode] = useState("color");
  const [files, setFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<Array<{ key: string; url: string }>>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batch, setBatch] = useState<ScanIngestionBatchRead | null>(null);
  const [recentBatchIds, setRecentBatchIds] = useState<number[]>([]);

  useEffect(() => {
    const next = files
      .filter((file) => file.type.startsWith("image/"))
      .slice(0, 4)
      .map((file) => ({ key: `${file.name}-${file.size}-${file.lastModified}`, url: URL.createObjectURL(file) }));
    setPreviewUrls(next);
    return () => {
      next.forEach((row) => URL.revokeObjectURL(row.url));
    };
  }, [files]);

  useEffect(() => {
    let ignore = false;
    void apiClient
      .listScanBatches({ limit: 10, offset: 0 })
      .then((resp) => {
        if (!ignore) setRecentBatchIds(resp.items.map((row) => row.id));
      })
      .catch(() => undefined);
    return () => {
      ignore = true;
    };
  }, []);

  const duplicateWarning = useMemo(() => {
    if (!batch || batch.duplicate_count === 0) return null;
    return `${batch.duplicate_count} uploaded image${batch.duplicate_count === 1 ? "" : "s"} matched an existing checksum.`;
  }, [batch]);

  async function submitUpload(): Promise<void> {
    if (files.length === 0) {
      setError("Choose at least one image or ZIP file.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const inferredUploadSource = files.some((file) => file.name.toLowerCase().endsWith(".zip")) ? "zip_upload" : "drag_drop";
      const payload: ScanBatchUploadPayload = {
        source_type: sourceType,
        upload_source: inferredUploadSource,
        scanner_make: scannerMake || undefined,
        scanner_model: scannerModel || undefined,
        scanner_profile: scannerProfile || undefined,
        color_mode: colorMode || undefined,
        normalized_dpi: 300,
        create_thumbnail: true,
        create_normalized_variant: true,
      };
      const created = await apiClient.uploadScanBatch(payload, files);
      setBatch(created);
      setRecentBatchIds((current) => [created.id, ...current.filter((id) => id !== created.id)].slice(0, 10));
    } catch (uploadErr) {
      setBatch(null);
      setError(uploadErr instanceof ApiError ? uploadErr.message : "Scan upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-01"
        title="Scan ingestion"
        description="Deterministic visual intake only: immutable originals, DPI normalization variants, duplicate checks, and append-only registration."
        actions={
          <>
            <Link
              to="/dashboard"
              className="inline-flex rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300/35 hover:bg-white/5"
            >
              Dashboard
            </Link>
            <Link
              to="/ops#scan-ingestion-ops"
              className="inline-flex rounded-2xl border border-cyan-300/35 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-500/10"
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
      {duplicateWarning ? (
        <div className="mt-4">
          <StatusBanner tone="warning">{duplicateWarning}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15">
        <div className="grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <label className="text-xs font-semibold text-slate-300">
                Source type
                <select
                  value={sourceType}
                  onChange={(event) => setSourceType(event.target.value as ScanIngestionSourceType)}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  {SOURCE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs font-semibold text-slate-300">
                Scanner make
                <input
                  value={scannerMake}
                  onChange={(event) => setScannerMake(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                Scanner model
                <input
                  value={scannerModel}
                  onChange={(event) => setScannerModel(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
              </label>
              <label className="text-xs font-semibold text-slate-300">
                Color mode
                <input
                  value={colorMode}
                  onChange={(event) => setColorMode(event.target.value)}
                  className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
              </label>
            </div>
            <label className="block text-xs font-semibold text-slate-300">
              Scanner profile label
              <input
                value={scannerProfile}
                onChange={(event) => setScannerProfile(event.target.value)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              />
            </label>
            <div className="rounded-2xl border border-dashed border-cyan-300/35 bg-cyan-500/5 p-4">
              <p className="text-sm text-slate-200">Drag/drop images or stage ZIP imports through the file picker below.</p>
              <p className="mt-1 text-xs text-slate-400">
                Originals are stored immutably; derivatives are registered separately and never overwrite the source file.
              </p>
              <input
                type="file"
                multiple
                accept="image/*,.zip"
                className="mt-3 text-xs text-slate-300 file:rounded-lg file:border-0 file:bg-cyan-400/90 file:px-3 file:py-2 file:text-[11px] file:font-semibold file:text-slate-950"
                onChange={(event) => setFiles(event.target.files ? Array.from(event.target.files) : [])}
              />
            </div>
            <button
              type="button"
              onClick={() => void submitUpload()}
              disabled={uploading || files.length === 0}
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 transition hover:bg-cyan-300 disabled:opacity-45"
            >
              {uploading ? `Uploading ${files.length} file${files.length === 1 ? "" : "s"}…` : "Register deterministic scan batch"}
            </button>
          </div>

          <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <h2 className="text-sm font-semibold text-white">Preview</h2>
            {previewUrls.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No image previews staged yet.</p>
            ) : (
              <div className="mt-3 grid grid-cols-2 gap-3">
                {previewUrls.map((preview) => (
                  <img
                    key={preview.key}
                    src={preview.url}
                    alt="Scan preview"
                    className="h-32 w-full rounded-2xl border border-white/10 object-cover"
                  />
                ))}
              </div>
            )}
            <div className="mt-4 space-y-2 text-xs text-slate-400">
              {files.map((file) => (
                <div key={`${file.name}-${file.size}-${file.lastModified}`} className="flex items-center justify-between gap-3">
                  <span className="truncate">{file.name}</span>
                  <span>{Math.ceil(file.size / 1024)} KB</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Latest batch detail</h2>
            <p className="mt-1 text-xs text-slate-400">
              Stable ordering is fixed by filename + checksum before registration; duplicates are preserved as linked audit rows.
            </p>
          </div>
          {recentBatchIds.length ? (
            <p className="text-xs text-slate-500">Recent batches: {recentBatchIds.map((id) => `#${id}`).join(", ")}</p>
          ) : null}
        </div>
        {!batch ? (
          <div className="mt-4">
            <EmptyState
              title="No scan batch loaded yet"
              description="Upload a set of files to inspect immutable originals, variants, and append-only events."
            />
          </div>
        ) : (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Batch</p>
                <p className="mt-2 text-2xl font-semibold text-white">#{batch.id}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Images</p>
                <p className="mt-2 text-2xl font-semibold text-white">{batch.image_count}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Failures</p>
                <p className="mt-2 text-2xl font-semibold text-white">{batch.failed_count}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Duplicates</p>
                <p className="mt-2 text-2xl font-semibold text-white">{batch.duplicate_count}</p>
              </div>
            </div>
            <div className="mt-5 overflow-auto rounded-2xl border border-white/10 bg-slate-950/50">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                  <tr>
                    <th className="p-3">Seq</th>
                    <th className="p-3">Filename</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Dimensions</th>
                    <th className="p-3">Duplicate</th>
                    <th className="p-3">Variants</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 text-slate-200">
                  {batch.images.map((row) => (
                    <tr key={row.id} className="align-top">
                      <td className="p-3 font-mono">{row.sequence_index}</td>
                      <td className="p-3">{row.original_filename}</td>
                      <td className="p-3">{row.processing_status}</td>
                      <td className="p-3 font-mono">
                        {row.width && row.height ? `${row.width}×${row.height}` : "—"}
                      </td>
                      <td className="p-3">{row.is_duplicate ? `#${row.duplicate_of_scan_image_id}` : "—"}</td>
                      <td className="p-3">
                        <button
                          type="button"
                          onClick={() => void apiClient.getScanImage(row.id).then(setBatchImageDetailGuard(setBatch, batch.id))}
                          className="rounded-xl border border-white/10 px-2 py-1 text-[10px] font-semibold text-slate-100 transition hover:border-cyan-300/35 hover:bg-white/5"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </AppShell>
  );
}

function setBatchImageDetailGuard(
  setBatch: Dispatch<SetStateAction<ScanIngestionBatchRead | null>>,
  batchId: number,
) {
  return (scanImage: Awaited<ReturnType<typeof apiClient.getScanImage>>) => {
    setBatch((current) => {
      if (!current || current.id !== batchId) return current;
      return {
        ...current,
        images: current.images.map((row) =>
          row.id === scanImage.id
            ? {
                ...row,
                ...scanImage,
              }
            : row,
        ),
      };
    });
  };
}
