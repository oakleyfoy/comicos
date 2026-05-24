import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type CoverImageRead,
  type HighResReviewRequestCreatePayload,
  type HighResReviewRequestDetail,
  type HighResReviewRequestReason,
  type HighResReviewRequestSummary,
} from "../api/client";
import { StatusBanner } from "./StatusBanner";

const REASONS: HighResReviewRequestReason[] = [
  "low_quality_scan",
  "failed_ocr",
  "poor_match_confidence",
  "valuable_review_candidate",
  "manual_review",
  "rescan_required",
];

function shortSha(hex: string | null | undefined): string {
  if (!hex || hex.length < 12) {
    return "—";
  }
  return `${hex.slice(0, 6)}…${hex.slice(-6)}`;
}

async function hydrateCoverSideBySide(
  source: CoverImageRead | null,
  hr: CoverImageRead | null,
): Promise<[string | null, string | null]> {
  const pickPath = (c: CoverImageRead | null) =>
    c?.medium_fetch_path ?? c?.thumbnail_fetch_path ?? c?.fetch_path ?? null;

  const load = async (read: CoverImageRead | null) => {
    const path = pickPath(read);
    if (!path) {
      return null;
    }
    const blob = await apiClient.fetchCoverImageBlob(path);
    return URL.createObjectURL(blob);
  };
  return Promise.all([load(source), load(hr)]) as Promise<[string | null, string | null]>;
}

export function HighResReviewInventorySection(props: { inventoryCopyId: number }) {
  const { inventoryCopyId } = props;
  const [requests, setRequests] = useState<HighResReviewRequestSummary[]>([]);
  const [selection, setSelection] = useState<HighResReviewRequestDetail | null>(null);
  const [leftBlobUrl, setLeftBlobUrl] = useState<string | null>(null);
  const [rightBlobUrl, setRightBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const [riskTypeDraft, setRiskTypeDraft] = useState("");
  const [createReason, setCreateReason] = useState<HighResReviewRequestReason>("manual_review");

  const createPayload = useMemo<HighResReviewRequestCreatePayload>(() => {
    const base: HighResReviewRequestCreatePayload = {
      inventory_copy_id: inventoryCopyId,
      request_reason: createReason,
      priority: "medium",
    };
    const trimmedRisk = riskTypeDraft.trim();
    if (trimmedRisk) {
      base.source_inventory_risk_type = trimmedRisk.slice(0, 80);
    }
    return base;
  }, [inventoryCopyId, createReason, riskTypeDraft]);

  const refreshList = useCallback(async () => {
    setError(null);
    try {
      const lst = await apiClient.listHighResReviewRequests({ inventory_copy_id: inventoryCopyId, limit: 50 });
      setRequests(lst.requests);

    } catch (err) {
      setRequests([]);
      setError(err instanceof ApiError ? err.message : "Unable to load high-resolution review requests.");
    }
  }, [inventoryCopyId]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  const selectRow = useCallback(async (id: number) => {
    setBusyKey(`sel-${id}`);
    setError(null);
    try {
      const detail = await apiClient.getHighResReviewRequest(id);
      setSelection(detail);
    } catch (err) {
      setSelection(null);
      setError(err instanceof ApiError ? err.message : "Unable to load queued review payload.");
    } finally {
      setBusyKey(null);
    }
  }, []);

  useEffect(() => {
    let leftRevoke: string | null = null;
    let rightRevoke: string | null = null;
    let cancelled = false;

    if (!selection) {
      setLeftBlobUrl(null);
      setRightBlobUrl(null);
      return () => undefined;
    }

    void (async () => {
      const [l, r] = await hydrateCoverSideBySide(selection.source_cover_scan, selection.review_high_res_scan);
      if (cancelled) {
        if (l) URL.revokeObjectURL(l);
        if (r) URL.revokeObjectURL(r);
        return;
      }
      leftRevoke = l;
      rightRevoke = r;
      setLeftBlobUrl(l);
      setRightBlobUrl(r);
    })();

    return () => {
      cancelled = true;
      if (leftRevoke) URL.revokeObjectURL(leftRevoke);
      if (rightRevoke) URL.revokeObjectURL(rightRevoke);
      setLeftBlobUrl(null);
      setRightBlobUrl(null);
    };
  }, [selection]);

  async function submitCreate(): Promise<void> {
    setBusyKey("create");
    setError(null);
    try {
      const created = await apiClient.createHighResReviewRequest(createPayload);
      await refreshList();
      await selectRow(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create escalation.");
    } finally {
      setBusyKey(null);
    }
  }

  async function attachSelected(fileList: FileList | null): Promise<void> {
    if (!selection || !fileList?.length) {
      return;
    }
    setBusyKey(`attach-${selection.id}`);
    setError(null);
    try {
      const next = await apiClient.attachHighResReviewScan(selection.id, fileList[0], fileList[0].name);
      setSelection(next);
      await refreshList();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to ingest Epson-facing scan safely.");
    } finally {
      setBusyKey(null);
    }
  }

  async function cancelSelected(): Promise<void> {
    if (!selection) {
      return;
    }
    setBusyKey(`cxl-${selection.id}`);
    setError(null);
    try {
      const next = await apiClient.cancelHighResReviewRequest(selection.id);
      setSelection(next);
      await refreshList();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to cancel escalation.");
    } finally {
      setBusyKey(null);
    }
  }

  async function completeSelected(): Promise<void> {
    if (!selection) {
      return;
    }
    setBusyKey(`done-${selection.id}`);
    setError(null);
    try {
      const next = await apiClient.completeHighResReviewRequest(selection.id);
      setSelection(next);
      await refreshList();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to mark review complete.");
    } finally {
      setBusyKey(null);
    }
  }

  const copyStatusChips = useMemo(() => {
    const acc: Partial<Record<string, number>> = {};
    for (const row of requests) {
      acc[row.status] = (acc[row.status] ?? 0) + 1;
    }
    const entries = Object.entries(acc).sort(([a], [b]) => a.localeCompare(b));
    if (!entries.length) return null;
    return (
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-200">
        {entries.map(([key, ct]) => (
          <span
            key={key}
            className="rounded-full border border-fuchsia-300/35 bg-fuchsia-500/15 px-2 py-1 font-mono capitalize"
          >
            {key.replace(/_/g, " ")} · {ct}
          </span>
        ))}
      </div>
    );
  }, [requests]);

  return (
    <section className="mt-8 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/12 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-fuchsia-200/85">High-resolution review (Epson / flatbed)</p>
          <p className="mt-2 max-w-3xl text-sm text-slate-300">
            Deterministic escalation lane for better OCR previews. Bulk scans stay untouched; high-res attaches as separate cover rows
            and never swaps primary covers unless you explicitly use the primary workflow elsewhere on this screen.
          </p>
          {copyStatusChips}
        </div>
      </div>

      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Queue new request</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col text-xs font-semibold text-slate-300">
            Reason
            <select
              className="mt-1 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white"
              value={createReason}
              onChange={(e) => setCreateReason(e.target.value as HighResReviewRequestReason)}
            >
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-xs font-semibold text-slate-300 sm:col-span-2">
            Optional inventory-risk hint <span className="font-normal text-slate-500">(audit text only)</span>
            <input
              type="text"
              value={riskTypeDraft}
              onChange={(e) => setRiskTypeDraft(e.target.value)}
              placeholder="needs_scan …"
              className="mt-1 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white"
            />
          </label>
          <button
            type="button"
            disabled={busyKey === "create"}
            onClick={() => void submitCreate()}
            className="self-end rounded-2xl border border-fuchsia-300/55 bg-fuchsia-500/20 px-4 py-2 text-sm font-semibold text-fuchsia-50 transition hover:border-fuchsia-200/85 disabled:opacity-40"
          >
            {busyKey === "create" ? "Opening…" : "Create escalation"}
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/55">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
              <tr>
                <th className="p-3">Req</th>
                <th className="p-3">Status</th>
                <th className="p-3">Reason</th>
                <th className="p-3">Coverage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {requests.length === 0 ? (
                <tr>
                  <td className="p-4 text-slate-500" colSpan={4}>
                    No requests for this copy yet.
                  </td>
                </tr>
              ) : (
                requests.map((row) => (
                  <tr key={row.id} className={selection?.id === row.id ? "bg-white/5" : undefined}>
                    <td className="p-3 font-mono text-[11px] text-white">
                      <button
                        type="button"
                        className="text-left text-cyan-200 underline-offset-4 hover:underline"
                        disabled={busyKey?.startsWith("sel")}
                        onClick={() => void selectRow(row.id)}
                      >
                        #{row.id}
                      </button>
                    </td>
                    <td className="p-3 capitalize">{row.status.replace(/_/g, " ")}</td>
                    <td className="p-3">{row.request_reason.replace(/_/g, " ")}</td>
                    <td className="p-3 font-mono text-[11px] text-slate-400">
                      src {row.source_cover_image_id ?? "—"} · hi {row.high_res_cover_image_id ?? "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-xs text-slate-200">
          {!selection ? (
            <p className="text-slate-500">Pick a queued request for comparison + Epson ingest tooling.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
                <p className="font-mono text-sm text-white">Request #{selection.id}</p>
                <p className="capitalize text-slate-400">{selection.status.replace(/_/g, " ")}</p>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <figure className="rounded-xl border border-white/10 bg-slate-950/70 p-2">
                  <figcaption className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Bulk / baseline</figcaption>
                  {leftBlobUrl ? (
                    <img src={leftBlobUrl} alt="baseline cover preview" className="mt-2 max-h-64 w-full rounded-lg object-contain" />
                  ) : selection.source_cover_scan ? (
                    <p className="mt-2 text-slate-500">Hydrating deterministic preview…</p>
                  ) : (
                    <p className="mt-2 text-slate-500">No explicit baseline cover anchored on request.</p>
                  )}
                  <p className="mt-2 font-mono text-[10px] text-slate-500">
                    {shortSha(selection.source_cover_scan?.sha256_hash)}
                  </p>
                </figure>
                <figure className="rounded-xl border border-fuchsia-300/35 bg-fuchsia-950/20 p-2">
                  <figcaption className="text-[10px] uppercase tracking-[0.14em] text-fuchsia-200/85">High-res preferred review</figcaption>
                  {rightBlobUrl ? (
                    <img src={rightBlobUrl} alt="high resolution scan preview" className="mt-2 max-h-64 w-full rounded-lg object-contain" />
                  ) : selection.review_high_res_scan ? (
                    <p className="mt-2 text-slate-500">Hydrating Epson scan preview…</p>
                  ) : (
                    <p className="mt-2 text-slate-400">Awaiting deterministic Epson ingestion while pending.</p>
                  )}
                  <p className="mt-2 font-mono text-[10px] text-slate-500">{shortSha(selection.review_high_res_scan?.sha256_hash)}</p>
                </figure>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <label className="inline-flex cursor-pointer items-center rounded-2xl border border-white/15 px-3 py-2 text-[11px] font-semibold text-slate-100 transition hover:border-fuchsia-300/55">
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    disabled={busyKey?.startsWith("attach") || selection.status !== "pending"}
                    className="hidden"
                    onChange={(e) => void attachSelected(e.target.files)}
                  />
                  Attach Epson scan
                </label>
                <button
                  type="button"
                  disabled={
                    busyKey?.startsWith("done") ||
                    !(selection.status === "linked" || selection.status === "scanned") ||
                    !selection.high_res_cover_image_id
                  }
                  onClick={() => void completeSelected()}
                  className="rounded-2xl border border-emerald-300/55 bg-emerald-500/10 px-3 py-2 text-[11px] font-semibold text-emerald-100 disabled:opacity-40"
                >
                  Mark review complete
                </button>
                <button
                  type="button"
                  disabled={busyKey?.startsWith("cxl") || selection.status === "review_complete" || selection.status === "cancelled"}
                  onClick={() => void cancelSelected()}
                  className="rounded-2xl border border-white/15 px-3 py-2 text-[11px] font-semibold text-slate-200 disabled:opacity-40"
                >
                  Cancel request
                </button>
              </div>
              <p className="mt-3 text-[11px] text-slate-500">
                Session audit: #{selection.attach_scan_session_id ?? "—"} · item #{selection.attach_scan_session_item_id ?? "—"}
              </p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
