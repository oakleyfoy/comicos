import { useMemo, useState, type ChangeEvent, type DragEvent, type ReactNode } from "react";

import { ApiError, apiClient, type RecognitionCandidateRead, type RecognitionIdentifyRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

type UploadRecord = {
  id: string;
  file: File;
  previewUrl: string;
  status: "pending" | "success" | "error";
  result?: RecognitionIdentifyRead;
  error?: string;
};

function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatConfidence(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

function candidateKey(candidate: RecognitionCandidateRead, index: number): string {
  return `${candidate.series}-${candidate.issue_number}-${candidate.source ?? "catalog"}-${index}`;
}

function uploadIdFor(file: File): string {
  const suffix = `${file.name}-${file.size}-${file.lastModified}`;
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${crypto.randomUUID()}-${suffix}`;
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}-${suffix}`;
}

function createPreviewUrl(file: File): string {
  if (typeof URL !== "undefined" && typeof URL.createObjectURL === "function") {
    return URL.createObjectURL(file);
  }
  return "";
}

export function RecognitionTestPage(): JSX.Element {
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [selectedUploadId, setSelectedUploadId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);

  const selectedUpload = useMemo(
    () => uploads.find((row) => row.id === selectedUploadId) ?? uploads[0] ?? null,
    [selectedUploadId, uploads],
  );

  const bucketCounts = useMemo(() => {
    return uploads.reduce(
      (acc, upload) => {
        const bucket = upload.result?.bucket;
        if (bucket) {
          acc[bucket] += 1;
        }
        return acc;
      },
      { VERIFIED: 0, REVIEW: 0, UNKNOWN: 0 },
    );
  }, [uploads]);

  async function runIdentification(file: File, id: string): Promise<void> {
    try {
      const result = await apiClient.identifyComicFromImage(file);
      setUploads((current) =>
        current.map((row) =>
          row.id === id
            ? {
                ...row,
                status: "success",
                result,
                error: undefined,
              }
            : row,
        ),
      );
      if (!selectedUploadId) {
        setSelectedUploadId(id);
      }
    } catch (err) {
      setUploads((current) =>
        current.map((row) =>
          row.id === id
            ? {
                ...row,
                status: "error",
                error: err instanceof ApiError ? err.message : "Unable to identify image.",
              }
            : row,
        ),
      );
    }
  }

  async function handleFiles(files: FileList | File[]): Promise<void> {
    const next = Array.from(files).filter((file) => file.type.startsWith("image/"));
    if (!next.length) return;
    setBusy(true);
    setError(null);
    const newUploads: UploadRecord[] = next.map((file) => {
      const id = uploadIdFor(file);
      return {
        id,
        file,
        previewUrl: createPreviewUrl(file),
        status: "pending",
      };
    });
    setUploads((current) => [...newUploads, ...current]);
    if (!selectedUploadId && newUploads[0]) {
      setSelectedUploadId(newUploads[0].id);
    }
    try {
      await Promise.all(newUploads.map((row) => runIdentification(row.file, row.id)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process uploads.");
    } finally {
      setBusy(false);
    }
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>): void {
    const files = event.target.files;
    if (files) {
      void handleFiles(files);
    }
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setDragActive(false);
    if (event.dataTransfer.files.length > 0) {
      void handleFiles(event.dataTransfer.files);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P95-01"
        title="Recognition Test"
        description="Internal upload harness for comic cover identification. Image in, identified comic out."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <StatCard label="Images uploaded" value={String(uploads.length)} />
        <StatCard label="Verified" value={String(bucketCounts.VERIFIED)} />
        <StatCard label="Review / Unknown" value={`${bucketCounts.REVIEW} / ${bucketCounts.UNKNOWN}`} />
      </section>

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-950/75 p-5 shadow-sm">
        <div
          onDragEnter={() => setDragActive(true)}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={`rounded-3xl border border-dashed px-6 py-10 text-center transition ${
            dragActive ? "border-teal-400/60 bg-teal-400/10" : "border-white/15 bg-slate-900/40"
          }`}
        >
          <p className="text-sm font-semibold text-slate-100">Drop comic cover images here</p>
          <p className="mt-1 text-xs text-slate-400">Upload one or more images to run recognition immediately.</p>
          <label className="mt-4 inline-flex cursor-pointer rounded-2xl bg-teal-400 px-4 py-2 text-sm font-semibold text-slate-950">
            Select files
            <input type="file" accept="image/*" multiple className="hidden" onChange={handleInputChange} />
          </label>
          {busy ? <p className="mt-3 text-xs text-slate-400">Identifying images…</p> : null}
        </div>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-[0.8fr,1.2fr]">
        <div className="rounded-3xl border border-white/10 bg-slate-950/75 p-5">
          <h2 className="text-sm font-semibold text-white">Uploads</h2>
          <div className="mt-4 space-y-3">
            {!uploads.length ? <p className="text-sm text-slate-500">No uploads yet.</p> : null}
            {uploads.map((upload) => {
              const active = selectedUpload?.id === upload.id;
              return (
                <button
                  key={upload.id}
                  type="button"
                  onClick={() => setSelectedUploadId(upload.id)}
                  className={`w-full rounded-2xl border p-3 text-left transition ${
                    active ? "border-teal-400/50 bg-teal-400/10" : "border-white/10 bg-slate-900/50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{upload.file.name}</p>
                      <p className="text-xs text-slate-400">{upload.status.toUpperCase()}</p>
                    </div>
                    <span className="rounded-full border border-white/10 px-2 py-1 text-[11px] text-slate-300">
                      {upload.result?.bucket ?? "PENDING"}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-slate-950/75 p-5">
          <h2 className="text-sm font-semibold text-white">Recognition Result</h2>
          {!selectedUpload ? (
            <p className="mt-4 text-sm text-slate-500">Select an upload to inspect its result.</p>
          ) : (
            <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr,1.1fr]">
              <div className="space-y-4">
                <img
                  src={selectedUpload.previewUrl}
                  alt={selectedUpload.file.name}
                  className="w-full rounded-2xl border border-white/10 object-cover"
                />
                <dl className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                  <Info label="Confidence" value={formatConfidence(selectedUpload.result?.confidence)} />
                  <Info label="Bucket" value={selectedUpload.result?.bucket ?? "PENDING"} />
                  <Info label="Series" value={selectedUpload.result?.series ?? "—"} />
                  <Info label="Issue" value={selectedUpload.result?.issue_number ?? "—"} />
                  <Info label="Variant" value={selectedUpload.result?.variant ?? "—"} />
                  <Info label="Publisher" value={selectedUpload.result?.publisher ?? "—"} />
                  <Info label="Release" value={formatDate(selectedUpload.result?.release_date)} />
                  <Info label="Candidates" value={String(selectedUpload.result?.candidate_count ?? 0)} />
                </dl>
                {selectedUpload.error ? <StatusBanner tone="error">{selectedUpload.error}</StatusBanner> : null}
              </div>

              <div className="space-y-4">
                <Panel title="Identified book">
                  {selectedUpload.result ? (
                    <div className="space-y-2">
                      <p className="text-lg font-semibold text-white">
                        {selectedUpload.result.series ?? "Unknown"}{" "}
                        {selectedUpload.result.issue_number ? `#${selectedUpload.result.issue_number}` : ""}
                      </p>
                      <p className="text-sm text-slate-300">
                        {selectedUpload.result.publisher ?? "Unknown publisher"} ·{" "}
                        {selectedUpload.result.variant ?? "No variant"} · {selectedUpload.result.bucket}
                      </p>
                      {selectedUpload.result.cover_image_url ? (
                        <a
                          href={selectedUpload.result.cover_image_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-block text-sm text-teal-300 underline"
                        >
                          Cover image URL
                        </a>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">The upload is still pending.</p>
                  )}
                </Panel>

                <Panel title="Alternate candidates">
                  {!selectedUpload.result?.candidates.length ? (
                    <p className="text-sm text-slate-500">No alternate candidates yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {selectedUpload.result.candidates.map((candidate, index) => (
                        <div
                          key={candidateKey(candidate, index)}
                          className="rounded-2xl border border-white/10 bg-slate-900/60 p-3 text-sm text-slate-200"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-semibold text-white">
                              {candidate.series} #{candidate.issue_number}
                            </span>
                            <span>{formatConfidence(candidate.confidence)}</span>
                          </div>
                          <p className="mt-1 text-xs text-slate-400">
                            {candidate.publisher ?? "Unknown publisher"} · {candidate.variant ?? "No variant"} ·{" "}
                            {formatDate(candidate.release_date)}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>
              </div>
            </div>
          )}
        </div>
      </section>
    </AppShell>
  );
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/75 p-5">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-4">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-white">{value}</p>
    </div>
  );
}

