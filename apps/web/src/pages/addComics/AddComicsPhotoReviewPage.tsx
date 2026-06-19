import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  confirmPhotoImportSession,
  fetchDetectionCropObjectUrl,
  getPhotoImportDetectionCandidates,
  listPhotoImportDetections,
  PhotoImportApiError,
  rejectPhotoImportDetection,
  selectPhotoImportCandidate,
  type PhotoImportCandidate,
  type PhotoImportDetectedBook,
} from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

function cropUrl(det: PhotoImportDetectedBook): string | null {
  if (det.crop_image_url) return apiUrl(det.crop_image_url);
  if (!det.crop_path) return null;
  if (det.crop_path.startsWith("http")) return det.crop_path;
  return apiUrl(det.crop_path);
}

function displayUrl(det: PhotoImportDetectedBook, cropObjectUrls: Record<number, string>): string | null {
  if (det.display_image_url) return det.display_image_url;
  if (cropObjectUrls[det.id]) return cropObjectUrls[det.id];
  return cropUrl(det);
}

function displayIssueNumber(det: PhotoImportDetectedBook): string {
  const n = det.ai_issue_number?.trim();
  return n ? n : "Unknown";
}

function hasNumericIssue(det: PhotoImportDetectedBook): boolean {
  return Boolean(det.ai_issue_number?.trim());
}

function detectionListErrorMessage(err: unknown): string {
  if (err instanceof PhotoImportApiError) {
    if (err.status === 401) return "Please log in again to review detections.";
    if (err.status === 403) return "This photo session belongs to another user.";
    return err.message;
  }
  return err instanceof Error ? err.message : "Could not load detections";
}

export function AddComicsPhotoReviewPage(): JSX.Element {
  const { token = "" } = useParams();
  const [detections, setDetections] = useState<PhotoImportDetectedBook[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "failed">("loading");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [candidateMap, setCandidateMap] = useState<Record<number, PhotoImportCandidate[]>>({});
  const [cropObjectUrls, setCropObjectUrls] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const rows = await listPhotoImportDetections(token);
      setDetections(rows);
      setLoadState("ready");
      setError(null);
    } catch (err) {
      setLoadState((prev) => (prev === "ready" ? "ready" : "failed"));
      setError(detectionListErrorMessage(err));
    }
  }, [token]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    const loadCrops = async () => {
      const next: Record<number, string> = {};
      await Promise.all(
        detections.map(async (det) => {
          if (!det.crop_image_url && !det.crop_path) return;
          const url = await fetchDetectionCropObjectUrl(det.id);
          if (url && !cancelled) next[det.id] = url;
        }),
      );
      if (!cancelled) {
        setCropObjectUrls((prev) => {
          for (const url of Object.values(prev)) URL.revokeObjectURL(url);
          return next;
        });
      }
    };
    void loadCrops();
    return () => {
      cancelled = true;
    };
  }, [detections]);

  useEffect(
    () => () => {
      for (const url of Object.values(cropObjectUrls)) URL.revokeObjectURL(url);
    },
    [cropObjectUrls],
  );

  const loadCandidates = async (detectionId: number) => {
    try {
      const res = await getPhotoImportDetectionCandidates(detectionId);
      setCandidateMap((prev) => ({ ...prev, [detectionId]: res.candidates }));
      setExpanded(detectionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load candidates");
    }
  };

  const active = detections.filter((d) => d.status !== "rejected" && d.status !== "confirmed");

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const confirmIds = async (ids: number[]) => {
    if (!token || ids.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const items = ids
        .map((id) => {
          const det = detections.find((d) => d.id === id);
          if (!det?.can_confirm || !det.selected_catalog_issue_id) return null;
          return { detected_book_id: id, catalog_issue_id: det.selected_catalog_issue_id, quantity: 1 };
        })
        .filter(Boolean) as { detected_book_id: number; catalog_issue_id: number; quantity: number }[];
      if (items.length === 0) {
        setError("Select a catalog match for each book before confirming.");
        return;
      }
      await confirmPhotoImportSession(token, items);
      await load();
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed");
    } finally {
      setBusy(false);
    }
  };

  const confirmHighConfidence = () => {
    const ids = active.filter((d) => d.can_confirm).map((d) => d.id);
    void confirmIds(ids);
  };

  const onSelectCandidate = async (detectionId: number, candidateId: number) => {
    setBusy(true);
    try {
      await selectPhotoImportCandidate(detectionId, candidateId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Select failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-4 py-10">
        <Link to="/add-comics/photo" className="text-sm text-blue-700 hover:underline">
          ← Phone Photo session
        </Link>
        <h1 className="mt-4 text-2xl font-semibold text-slate-900">Review detected books</h1>
        {loadState === "loading" ? (
          <p className="mt-3 text-sm text-slate-600" aria-live="polite">
            Loading detections…
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || !active.some((d) => d.can_confirm)}
            onClick={() => void confirmHighConfidence()}
            className="rounded-lg bg-emerald-700 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Confirm all high confidence
          </button>
          <button
            type="button"
            disabled={busy || selected.size === 0}
            onClick={() => void confirmIds([...selected])}
            className="rounded-lg bg-blue-700 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Confirm selected
          </button>
        </div>
        <ul className="mt-6 space-y-4">
          {active.map((det) => {
            const best = det.best_candidate;
            const uploadedThumb = cropObjectUrls[det.id] ?? cropUrl(det);
            const heroThumb = displayUrl(det, cropObjectUrls);
            const candidates = candidateMap[det.id] ?? [];
            const showPicker = expanded === det.id;
            return (
              <li key={det.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start gap-6">
                  <div className="flex min-w-[10rem] flex-col gap-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your photo</p>
                    {heroThumb ? (
                      <img
                        src={heroThumb}
                        alt=""
                        className="max-h-64 w-auto max-w-[12rem] shrink-0 rounded object-contain ring-1 ring-slate-200"
                      />
                    ) : (
                      <p className="text-xs text-slate-400">No crop preview</p>
                    )}
                  </div>
                  {best?.cover_url && det.status !== "confirmed" ? (
                    <div className="flex min-w-[10rem] flex-col gap-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Catalog cover</p>
                      <img
                        src={best.cover_url}
                        alt=""
                        className="max-h-64 w-auto max-w-[12rem] shrink-0 rounded object-contain ring-1 ring-emerald-200"
                      />
                    </div>
                  ) : null}
                  <label className="flex min-w-[12rem] flex-1 items-start gap-2">
                    <input type="checkbox" checked={selected.has(det.id)} onChange={() => toggle(det.id)} />
                    <span className="text-sm font-medium text-slate-800">Include in bulk confirm</span>
                  </label>
                </div>
                <dl className="mt-3 grid gap-1 text-sm text-slate-700 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs uppercase text-slate-400">Publisher</dt>
                    <dd>{det.ai_publisher || det.ai_visible_publisher_text || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-400">Series</dt>
                    <dd>{det.ai_series || det.ai_visible_title_text || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-400">Issue #</dt>
                    <dd>{displayIssueNumber(det)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-400">AI confidence</dt>
                    <dd>{Math.round((det.ai_confidence ?? 0) * 100)}%</dd>
                  </div>
                  {det.ai_visible_title_text ? (
                    <div className="sm:col-span-2">
                      <dt className="text-xs uppercase text-slate-400">Visible title text</dt>
                      <dd>{det.ai_visible_title_text}</dd>
                    </div>
                  ) : null}
                  {det.ai_subtitle_guess ? (
                    <div className="sm:col-span-2">
                      <dt className="text-xs uppercase text-slate-400">Subtitle</dt>
                      <dd>{det.ai_subtitle_guess}</dd>
                    </div>
                  ) : null}
                  {!hasNumericIssue(det) && det.ai_visible_issue_text ? (
                    <div className="sm:col-span-2">
                      <dt className="text-xs uppercase text-slate-400">Visible text</dt>
                      <dd>{det.ai_visible_issue_text}</dd>
                    </div>
                  ) : null}
                  {hasNumericIssue(det) && det.ai_visible_issue_text ? (
                    <div>
                      <dt className="text-xs uppercase text-slate-400">Visible issue text</dt>
                      <dd>{det.ai_visible_issue_text}</dd>
                    </div>
                  ) : null}
                  {det.ai_uncertainty_reason ? (
                    <div className="sm:col-span-2">
                      <dt className="text-xs uppercase text-slate-400">Uncertainty</dt>
                      <dd className="text-amber-800">{det.ai_uncertainty_reason}</dd>
                    </div>
                  ) : null}
                </dl>
                <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested matches</p>
                  {best ? (
                    <>
                      <p className="mt-1 text-slate-800">
                        {best.publisher} · {best.series} #{best.issue_number}{" "}
                        <span className="text-slate-500">({Math.round(best.match_score)} score)</span>
                      </p>
                      {det.review_status === "needs_selection" ? (
                        <p className="mt-1 font-medium text-amber-800">Needs selection — choose the correct issue</p>
                      ) : null}
                    </>
                  ) : (
                    <p className="mt-1 font-medium text-amber-800">Needs match</p>
                  )}
                  {best?.match_reason ? <p className="mt-1 text-xs text-slate-500">{best.match_reason}</p> : null}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {det.can_confirm ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void confirmIds([det.id])}
                      className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      Confirm
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void loadCandidates(det.id)}
                      className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white"
                    >
                      {!hasNumericIssue(det)
                        ? "Select correct issue"
                        : det.candidate_count > 0
                          ? "Select match"
                          : "Find match"}
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void rejectPhotoImportDetection(det.id).then(() => load())}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium"
                  >
                    Reject
                  </button>
                  {det.candidate_count > 1 ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => (showPicker ? setExpanded(null) : void loadCandidates(det.id))}
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium"
                    >
                      {showPicker ? "Hide alternatives" : "Show alternatives"}
                    </button>
                  ) : null}
                </div>
                {showPicker && candidates.length > 0 ? (
                  <ul className="mt-4 space-y-2 border-t border-slate-100 pt-3">
                    {uploadedThumb ? (
                      <li className="mb-3 flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                        <img
                          src={uploadedThumb}
                          alt=""
                          className="max-h-40 w-auto max-w-[9rem] rounded object-contain"
                        />
                        <span>Your crop — compare to candidate covers below</span>
                      </li>
                    ) : null}
                    {candidates.slice(0, 10).map((c) => (
                      <li
                        key={c.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 px-3 py-2"
                      >
                        <div className="flex items-center gap-3 text-sm">
                          {c.thumbnail_url || c.cover_url ? (
                            <img
                              src={c.thumbnail_url || c.cover_url || ""}
                              alt=""
                              className="h-14 w-10 rounded object-cover"
                            />
                          ) : null}
                          <div>
                            <p className="font-medium text-slate-800">
                              {c.publisher} · {c.series} #{c.issue_number}
                            </p>
                            <p className="text-xs text-slate-500">
                              Score {Math.round(c.final_score ?? c.match_score)}
                              {c.visual_match_label ? ` · ${c.visual_match_label}` : ""}
                              {c.release_date ? ` · ${c.release_date}` : ""}
                            </p>
                            {c.cover_similarity_score != null || c.fingerprint_score != null ? (
                              <p className="text-xs text-indigo-700">
                                {c.cover_similarity_score != null ? `Cover ${Math.round(c.cover_similarity_score)}` : ""}
                                {c.cover_similarity_score != null && c.fingerprint_score != null ? " · " : ""}
                                {c.fingerprint_score != null ? `Fingerprint ${Math.round(c.fingerprint_score)}` : ""}
                              </p>
                            ) : null}
                            {c.match_reason ? <p className="text-xs text-slate-500">{c.match_reason}</p> : null}
                          </div>
                        </div>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void onSelectCandidate(det.id, c.id)}
                          className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white"
                        >
                          Select
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
        {loadState === "ready" && active.length === 0 ? (
          <p className="mt-6 text-sm text-slate-500">No pending detections.</p>
        ) : null}
      </div>
    </AppShell>
  );
}
