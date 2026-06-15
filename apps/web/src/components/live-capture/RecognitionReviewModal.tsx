import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type ReceivingSessionDetailRead,
  type ReceivingSessionItemRead,
  type RecognitionCatalogCandidateRead,
} from "../../api/client";
import { CandidateIssueCard } from "./CandidateIssueCard";
import { CatalogCandidateSearch } from "./CatalogCandidateSearch";
import { recognitionSourceSentence } from "./recognitionTrustCopy";

export type RecognitionReviewCloseAction = "accept" | "cancel";

interface RecognitionReviewModalProps {
  open: boolean;
  sessionId: number;
  item: ReceivingSessionItemRead;
  capturedFrameUrl?: string | null;
  onSessionUpdate: (session: ReceivingSessionDetailRead) => void;
  onClose: (action: RecognitionReviewCloseAction) => void;
}

type ReviewMode = "summary" | "candidates" | "search";

interface MatchedPreview {
  series: string | null;
  issueNumber: string | null;
  variant: string | null;
  publisher: string | null;
  releaseDate: string | null;
  coverImageUrl: string | null;
  catalogIssueId: number | null;
  winningSource: string | null;
}

function readString(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  return null;
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function friendlyBucket(bucket: string | undefined): string {
  switch (bucket) {
    case "VERIFIED":
      return "ComicOS is confident about this match.";
    case "REVIEW":
      return "ComicOS is not fully sure.";
    case "UNKNOWN":
      return "ComicOS could not identify this cover.";
    default:
      return "Review this match.";
  }
}

function friendlySource(
  source: string | null,
  snapshot?: Record<string, unknown>,
): string | null {
  const visual = typeof snapshot?.visual_match_strength === "string" ? snapshot.visual_match_strength : null;
  const guidance = typeof snapshot?.recognition_guidance === "string" ? snapshot.recognition_guidance : null;
  return recognitionSourceSentence(source, visual, guidance);
}

function buildMatchedPreview(item: ReceivingSessionItemRead): MatchedPreview {
  const snapshot =
    item.user_corrected && item.corrected_recognition_snapshot_json
      ? item.corrected_recognition_snapshot_json
      : (item.recognition_snapshot_json ?? {});
  const snap = (snapshot ?? {}) as Record<string, unknown>;
  return {
    series: readString(snap.series),
    issueNumber: readString(snap.issue_number),
    variant: readString(snap.variant),
    publisher: readString(snap.publisher),
    releaseDate: readString(snap.release_date),
    coverImageUrl: readString(snap.cover_image_url),
    catalogIssueId: readNumber(snap.catalog_issue_id) ?? item.corrected_catalog_issue_id ?? null,
    winningSource: readString(snap.winning_source),
  };
}

export function RecognitionReviewModal({
  open,
  sessionId,
  item,
  capturedFrameUrl,
  onSessionUpdate,
  onClose,
}: RecognitionReviewModalProps): JSX.Element | null {
  const [localItem, setLocalItem] = useState<ReceivingSessionItemRead>(item);
  const [mode, setMode] = useState<ReviewMode>("summary");
  const [previewCandidate, setPreviewCandidate] = useState<RecognitionCatalogCandidateRead | null>(null);
  const [nearbyCards, setNearbyCards] = useState<RecognitionCatalogCandidateRead[]>([]);
  const [loadingNearby, setLoadingNearby] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    setLocalItem(item);
    setErrorMsg(null);
  }, [item]);

  useEffect(() => {
    setMode("summary");
    setPreviewCandidate(null);
    setNearbyCards([]);
    setErrorMsg(null);
  }, [item.id]);

  const matched = useMemo(() => buildMatchedPreview(localItem), [localItem]);
  const recognitionSnapshot = useMemo(
    () => (localItem.recognition_snapshot_json ?? {}) as Record<string, unknown>,
    [localItem],
  );
  const hasMatch = Boolean(matched.series || matched.catalogIssueId);
  const confidence = localItem.recognition_confidence;
  const confidenceLabel = confidence != null ? `${Math.round(confidence * 100)}%` : "—";

  async function loadNearby(): Promise<void> {
    setLoadingNearby(true);
    setErrorMsg(null);
    try {
      const query = matched.catalogIssueId
        ? { catalog_issue_id: matched.catalogIssueId, limit: 24 }
        : { q: [matched.series, matched.issueNumber, matched.publisher].filter(Boolean).join(" "), limit: 24 };
      const cards = await apiClient.listRecognitionCatalogCandidates(query);
      setNearbyCards(cards);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Could not load candidates.");
      setNearbyCards([]);
    } finally {
      setLoadingNearby(false);
    }
  }

  function openCandidates(): void {
    setMode("candidates");
    setPreviewCandidate(null);
    void loadNearby();
  }

  function openSearch(): void {
    setMode("search");
    setPreviewCandidate(null);
  }

  async function handleAcceptMatch(): Promise<void> {
    setBusy(true);
    setErrorMsg(null);
    try {
      const response = await apiClient.confirmReceivingSessionItem(sessionId, {
        item_id: localItem.id,
        decision: "confirm",
        selected_candidate_index: localItem.selected_candidate_index ?? 0,
      });
      onSessionUpdate(response.session);
      onClose("accept");
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Could not accept this match.");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmSelected(): Promise<void> {
    if (!previewCandidate) {
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    try {
      const response = await apiClient.correctReceivingSessionItem(sessionId, localItem.id, {
        catalog_issue_id: previewCandidate.catalog_issue_id,
        reason: "wrong_issue_number",
      });
      onSessionUpdate(response.session);
      setLocalItem(response.item);
      setPreviewCandidate(null);
      setMode("summary");
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : "Could not apply the correction.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Review Recognition Match"
      data-testid="recognition-review-modal"
    >
      <div className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-slate-700 bg-slate-900 text-slate-100 shadow-2xl">
        <header className="border-b border-slate-800 px-6 py-4">
          <h2 className="text-xl font-semibold">Review Recognition Match</h2>
          <p className="text-sm text-slate-400">ComicOS thinks this is:</p>
        </header>

        <div className="grid flex-1 gap-4 overflow-y-auto px-6 py-5 lg:grid-cols-2">
          <section className="space-y-2">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Captured frame</p>
            <div className="aspect-[3/4] w-full overflow-hidden rounded-2xl border border-slate-800 bg-slate-950">
              {capturedFrameUrl ? (
                <img src={capturedFrameUrl} alt="Captured frame" className="h-full w-full object-contain" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
                  What the camera saw
                </div>
              )}
            </div>
          </section>

          <section className="space-y-3">
            {mode === "summary" ? (
              <>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Matched issue</p>
                {hasMatch ? (
                  <div className="space-y-3">
                    <div className="aspect-[2/3] w-40 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950">
                      {matched.coverImageUrl ? (
                        <img src={matched.coverImageUrl} alt="Matched cover" className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">
                          No cover
                        </div>
                      )}
                    </div>
                    <div className="space-y-1">
                      <p className="text-lg font-semibold" data-testid="review-matched-title">
                        {matched.series ?? "Unknown"} #{matched.issueNumber ?? "?"}
                      </p>
                      {matched.variant ? <p className="text-sm text-slate-300">{matched.variant}</p> : null}
                      <p className="text-sm text-slate-400">{matched.publisher ?? "Unknown publisher"}</p>
                      {matched.releaseDate ? (
                        <p className="text-sm text-slate-400">Released {matched.releaseDate}</p>
                      ) : null}
                      <p className="text-sm text-slate-300">{friendlyBucket(localItem.recognition_bucket)}</p>
                      <p className="text-sm text-slate-400">Confidence {confidenceLabel}</p>
                      {friendlySource(matched.winningSource, recognitionSnapshot) ? (
                        <p className="text-sm text-slate-400">{friendlySource(matched.winningSource, recognitionSnapshot)}</p>
                      ) : null}
                      <p className="text-[11px] text-slate-600" data-testid="review-debug-row">
                        Source {matched.winningSource ?? "none"}
                        {matched.catalogIssueId != null ? ` · Catalog issue ${matched.catalogIssueId}` : ""}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
                    No confident match found.
                  </p>
                )}
              </>
            ) : null}

            {mode === "candidates" ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Choose a different issue</p>
                  <button type="button" onClick={() => setMode("summary")} className="text-xs text-slate-400 hover:text-white">
                    Back
                  </button>
                </div>
                {loadingNearby ? <p className="text-sm text-slate-400">Loading candidates…</p> : null}
                {!loadingNearby && nearbyCards.length === 0 ? (
                  <p className="text-sm text-slate-400">No nearby issues. Try Search Catalog.</p>
                ) : null}
                <div className="grid max-h-[40vh] grid-cols-2 gap-3 overflow-y-auto sm:grid-cols-3">
                  {nearbyCards.map((candidate) => (
                    <CandidateIssueCard
                      key={candidate.catalog_issue_id}
                      candidate={candidate}
                      selected={previewCandidate?.catalog_issue_id === candidate.catalog_issue_id}
                      onSelect={setPreviewCandidate}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            {mode === "search" ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Search catalog</p>
                  <button type="button" onClick={() => setMode("summary")} className="text-xs text-slate-400 hover:text-white">
                    Back
                  </button>
                </div>
                <CatalogCandidateSearch
                  selectedCatalogIssueId={previewCandidate?.catalog_issue_id ?? null}
                  onSelect={setPreviewCandidate}
                  initialQuery={[matched.series, matched.issueNumber].filter(Boolean).join(" ")}
                />
              </div>
            ) : null}

            {previewCandidate ? (
              <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/5 p-3" data-testid="review-preview-selection">
                <p className="text-sm text-slate-300">
                  Selected: <span className="font-semibold text-white">{previewCandidate.series} #{previewCandidate.issue_number}</span>
                </p>
              </div>
            ) : null}
          </section>
        </div>

        {errorMsg ? <p className="px-6 text-sm text-rose-300">{errorMsg}</p> : null}

        <footer className="flex flex-wrap gap-2 border-t border-slate-800 px-6 py-4">
          {mode === "summary" ? (
            <>
              <button
                type="button"
                data-testid="review-accept-match"
                onClick={() => void handleAcceptMatch()}
                disabled={busy || !hasMatch}
                className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                Accept Match
              </button>
              <button
                type="button"
                data-testid="review-choose-different"
                onClick={openCandidates}
                disabled={busy}
                className="rounded-full border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 disabled:opacity-50"
              >
                Choose Different Issue
              </button>
              <button
                type="button"
                data-testid="review-search-catalog"
                onClick={openSearch}
                disabled={busy}
                className={`rounded-full px-4 py-2 text-sm font-semibold disabled:opacity-50 ${
                  hasMatch ? "border border-slate-600 text-slate-100" : "bg-emerald-500 text-slate-950"
                }`}
              >
                Search Catalog
              </button>
              <button
                type="button"
                data-testid="review-cancel"
                onClick={() => onClose("cancel")}
                disabled={busy}
                className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 disabled:opacity-50"
              >
                Cancel / Rescan
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                data-testid="review-confirm-selected"
                onClick={() => void handleConfirmSelected()}
                disabled={busy || !previewCandidate}
                className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                Confirm Selected Issue
              </button>
              {mode === "candidates" ? (
                <button
                  type="button"
                  data-testid="review-search-catalog"
                  onClick={openSearch}
                  disabled={busy}
                  className="rounded-full border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 disabled:opacity-50"
                >
                  Search Catalog
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => onClose("cancel")}
                disabled={busy}
                className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 disabled:opacity-50"
              >
                Cancel / Rescan
              </button>
            </>
          )}
        </footer>
      </div>
    </div>
  );
}
