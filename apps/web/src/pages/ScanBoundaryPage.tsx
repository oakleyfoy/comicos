import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanBoundaryRunDetail,
  type ScanImageSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanBoundaryPage() {
  const [images, setImages] = useState<ScanImageSummaryRead[]>([]);
  const [selectedImageId, setSelectedImageId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanBoundaryRunDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      return;
    }
    let ignore = false;
    void (async () => {
      const resp = await apiClient.listScanBoundaryRuns({ scan_image_id: selectedImageId, limit: 1, offset: 0 });
      if (ignore || !resp.items[0]) {
        if (!ignore) setRun(null);
        return;
      }
      const detail = await apiClient.getScanBoundaryRun(resp.items[0].id);
      if (!ignore) setRun(detail);
    })();
    return () => {
      ignore = true;
    };
  }, [selectedImageId]);

  const geometry = useMemo(() => run?.geometry ?? {}, [run]);

  async function submitRun(): Promise<void> {
    if (!selectedImageId) return;
    setRunning(true);
    setError(null);
    try {
      const detail = await apiClient.runScanBoundaryMapping({ scan_image_id: selectedImageId });
      setRun(detail);
    } catch (runErr) {
      setError(runErr instanceof ApiError ? runErr.message : "Boundary mapping failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-03"
        title="Scan boundary mapping"
        description="Deterministic cover-area detection for normalized comic scans."
        actions={
          <Link to="/scan-normalization" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
            Normalization
          </Link>
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
              Normalized scan image
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
              {running ? "Running boundary mapping…" : "Run boundary mapping"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.boundary_status}</span> · confidence{" "}
                <span className="font-semibold text-white">{run.confidence_score ?? "—"}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 xl:grid-cols-3">
            <PreviewCard title="Normalized source" src={run?.source_preview_data_url ?? null} />
            <PreviewCard title="Boundary overlay" src={run?.boundary_overlay_preview_data_url ?? null} />
            <PreviewCard title="Cover box preview" src={run?.cover_box_preview_data_url ?? null} />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState title="No boundary run loaded" description="Select a scan image and run boundary mapping to inspect geometry and lineage." />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Geometry">
              <dl className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                <Item label="x_min" value={String(geometry.x_min ?? "—")} />
                <Item label="y_min" value={String(geometry.y_min ?? "—")} />
                <Item label="x_max" value={String(geometry.x_max ?? "—")} />
                <Item label="y_max" value={String(geometry.y_max ?? "—")} />
                <Item label="aspect_ratio" value={String(geometry.aspect_ratio ?? "—")} />
                <Item label="angle_degrees" value={String(geometry.angle_degrees ?? "—")} />
                <Item label="cover_coverage_ratio" value={String(geometry.cover_coverage_ratio ?? "—")} />
                <Item label="cover_area_px" value={String(geometry.cover_area_px ?? "—")} />
              </dl>
            </Panel>
            <Panel title="Issues">
              {run.issues.length === 0 ? (
                <p className="text-sm text-slate-500">No boundary issues recorded.</p>
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
            <Panel title="Checksum lineage">
              <ChecksumRow label="Original scan" value={run.original_scan_checksum ?? "—"} />
              <ChecksumRow label="Normalized source" value={run.normalized_source_checksum ?? "—"} />
              <ChecksumRow label="Boundary run" value={run.boundary_checksum} />
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
