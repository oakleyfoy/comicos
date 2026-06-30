import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import QRCode from "qrcode";

import {
  acceptIntakeItem,
  addAllHighConfidence,
  addIntakeItemToInventory,
  chooseIntakeItemIssue,
  getIntakeReview,
  importAndAcceptIntakeItem,
  intakeImageUrl,
  rejectIntakeItem,
  requeueIntakeItem,
  searchCatalogIssues,
  type IntakeCatalogSearchResult,
  type IntakeCounts,
  type IntakeItem,
  type IntakeReview,
  uploadIntakeFullCoverPhoto,
} from "../../api/intake";

const COUNT_CARDS: {
  key: keyof IntakeCounts;
  label: string;
  border: string;
  value: string;
}[] = [
  { key: "scanned", label: "Scanned", border: "border-l-slate-500", value: "text-slate-50" },
  { key: "queued", label: "Queued", border: "border-l-violet-400", value: "text-violet-200" },
  { key: "processing", label: "Processing", border: "border-l-amber-400", value: "text-amber-100" },
  { key: "auto_matched", label: "Auto matched", border: "border-l-teal-400", value: "text-teal-100" },
  { key: "ready_for_review", label: "Ready for review", border: "border-l-sky-400", value: "text-sky-100" },
  { key: "needs_review", label: "Needs review", border: "border-l-orange-400", value: "text-orange-100" },
  {
    key: "needs_full_cover_photo",
    label: "Full cover",
    border: "border-l-fuchsia-400",
    value: "text-fuchsia-100",
  },
  {
    key: "added_to_inventory",
    label: "Added to inventory",
    border: "border-l-emerald-400",
    value: "text-emerald-100",
  },
  { key: "failed", label: "Failed", border: "border-l-rose-400", value: "text-rose-100" },
];

function intakeBarcode(item: IntakeItem): string {
  const br = item.barcode_read;
  const fromRead =
    br && typeof br.reconstructed_full === "string" && br.reconstructed_full.length >= 12
      ? br.reconstructed_full
      : "";
  return item.normalized_barcode || fromRead || item.raw_barcode || "";
}

function isLocalCatalogBarcodeMatch(item: IntakeItem): boolean {
  return (
    item.status === "auto_matched" &&
    (item.match_source === "catalog_upc" || item.match_source === "learned_barcode") &&
    Boolean(item.selected_catalog_issue_id)
  );
}

function isVerifiedLocalBarcodeMatch(item: IntakeItem): boolean {
  return isLocalCatalogBarcodeMatch(item);
}

function intakeBarcodeGap(item: IntakeItem): Record<string, unknown> | null {
  const gap = item.barcode_read?.barcode_gap;
  return gap && typeof gap === "object" ? (gap as Record<string, unknown>) : null;
}

type IntakeReviewCandidateRow = {
  series?: string | null;
  title?: string | null;
  issue_number?: string | null;
  publisher?: string | null;
  confidence?: number;
  source?: string;
  cover_url?: string | null;
  import_ready?: boolean;
};

function intakeNeedsFullCoverPhoto(item: IntakeItem): boolean {
  if (item.status === "needs_full_cover_photo") return true;
  return item.barcode_read?.needs_full_cover_photo === true;
}

/**
 * A device can take the cover photo *here* only if it actually has a camera the
 * browser can reach (phones/tablets). On a desktop, the file input ignores
 * `capture` and just opens a file picker, so we hand off to the phone via QR.
 */
function isDirectCameraCaptureDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  const mobileUa = /Mobi|Android|iPhone|iPad|iPod|Tablet/i.test(ua);
  const coarsePointer =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(pointer: coarse)").matches;
  return mobileUa || coarsePointer;
}

const FRONTEND_BUILD_SHA =
  typeof __BUILD_SHA__ === "string" ? __BUILD_SHA__ : "unknown";
const FRONTEND_BUILD_TIME =
  typeof __BUILD_TIME__ === "string" ? __BUILD_TIME__ : "unknown";
const FRONTEND_BUILD_SHA_SHORT = FRONTEND_BUILD_SHA.slice(0, 8);

const FULL_COVER_PROMPT =
  "Barcode was read, but no barcode record exists in GCD or your catalog. Take a full front-cover photo to identify by cover art.";

function FullCoverPhotoActions({
  itemId,
  busy,
  onTakePhoto,
  onUploadPhoto,
}: {
  itemId: number;
  busy: boolean;
  onTakePhoto: () => void;
  onUploadPhoto: () => void;
}) {
  return (
    <>
      <button
        type="button"
        disabled={busy}
        data-testid={`full-cover-camera-${itemId}`}
        onClick={onTakePhoto}
        className="rounded-lg bg-fuchsia-700 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
      >
        Take Full Cover Photo
      </button>
      <button
        type="button"
        disabled={busy}
        data-testid={`full-cover-upload-${itemId}`}
        onClick={onUploadPhoto}
        className="rounded-lg border border-fuchsia-500/60 px-3 py-1.5 text-xs font-medium text-fuchsia-100 disabled:opacity-50"
      >
        Upload Existing Photo
      </button>
    </>
  );
}

function intakeFingerprintReviewCandidates(item: IntakeItem): IntakeReviewCandidateRow[] {
  if (intakeNeedsFullCoverPhoto(item)) return [];
  const gap = intakeBarcodeGap(item);
  const tops = gap?.needs_review_top_candidates;
  if (Array.isArray(tops)) {
    return tops.slice(0, 3).filter((row): row is IntakeReviewCandidateRow => row && typeof row === "object");
  }
  return item.candidates
    .filter((c) => c.source === "fingerprint")
    .slice(0, 3)
    .map((c) => ({
      series: c.series,
      issue_number: c.issue_number,
      publisher: c.publisher,
      confidence: c.score / 100,
      source: "fingerprint",
      cover_url: c.cover_url,
    }));
}

function intakeComicvineReviewCandidate(item: IntakeItem): IntakeReviewCandidateRow | null {
  const gap = intakeBarcodeGap(item);
  const cv = gap?.comicvine_review_candidate;
  if (!cv || typeof cv !== "object") return null;
  return cv as IntakeReviewCandidateRow;
}

function intakeRecoveryHintSeries(item: IntakeItem): string {
  const gap = intakeBarcodeGap(item);
  const rh = gap?.recovery_hints;
  if (rh && typeof rh === "object") {
    const fromRh = typeof (rh as Record<string, unknown>).series === "string"
      ? String((rh as Record<string, unknown>).series).trim()
      : typeof (rh as Record<string, unknown>).ocr_title === "string"
        ? String((rh as Record<string, unknown>).ocr_title).trim()
        : "";
    if (fromRh) return fromRh;
  }
  return "";
}

function intakeRecoveryHintIssueNumber(item: IntakeItem): string {
  const gap = intakeBarcodeGap(item);
  const rh = gap?.recovery_hints;
  if (rh && typeof rh === "object") {
    const num = (rh as Record<string, unknown>).issue_number ?? (rh as Record<string, unknown>).ocr_issue_number;
    if (typeof num === "string" && num.trim()) return num.trim();
  }
  return "";
}

function intakeHeadline(item: IntakeItem): string {
  const gap = intakeBarcodeGap(item);
  const gapSeries = typeof gap?.gcd_series === "string" ? gap.gcd_series.trim() : "";
  const gapNum = typeof gap?.gcd_issue_number === "string" ? gap.gcd_issue_number.trim() : "";
  const hintSeries = intakeRecoveryHintSeries(item);
  const hintNum = intakeRecoveryHintIssueNumber(item);
  const gapAuthoritative =
    gap?.action === "auto_import_available" ||
    (typeof gap?.gcd_match_count === "number" && gap.gcd_match_count === 1);
  const fpTop = intakeFingerprintReviewCandidates(item)[0];
  const seriesFromFp =
    typeof fpTop?.series === "string"
      ? fpTop.series.trim()
      : typeof fpTop?.title === "string"
        ? fpTop.title.trim()
        : "";
  const numFromFp = typeof fpTop?.issue_number === "string" ? fpTop.issue_number.trim() : "";
  const series = gapAuthoritative
    ? gapSeries || item.matched_series?.trim() || seriesFromFp || hintSeries
    : item.matched_series?.trim() || gapSeries || seriesFromFp || hintSeries;
  const num = gapAuthoritative
    ? gapNum || item.matched_issue_number?.trim() || numFromFp || hintNum
    : item.matched_issue_number?.trim() || gapNum || numFromFp || hintNum;
  if (series) {
    return [series, num ? `#${num.replace(/^#/, "")}` : null].filter(Boolean).join(" ");
  }
  if (num) {
    const pub =
      item.matched_publisher?.trim() ||
      (typeof gap?.gcd_publisher === "string" ? gap.gcd_publisher.trim() : "");
    return pub ? `${pub} #${num.replace(/^#/, "")}` : `#${num.replace(/^#/, "")}`;
  }
  return "Unidentified";
}

function intakeSubtitle(item: IntakeItem): string {
  const parts: string[] = [];
  const gap = intakeBarcodeGap(item);
  const pub =
    item.matched_publisher?.trim() ||
    (typeof gap?.gcd_publisher === "string" ? gap.gcd_publisher.trim() : "");
  if (pub) parts.push(pub);
  if (item.matched_year?.trim()) parts.push(item.matched_year.trim());
  return parts.join(" · ");
}

function intakeInfoMessage(item: IntakeItem): Array<{ tone: "success" | "info" | "warn"; text: string }> {
  const lines: Array<{ tone: "success" | "info" | "warn"; text: string }> = [];
  if (isVerifiedLocalBarcodeMatch(item)) {
    lines.push({ tone: "success", text: "Barcode verified against local catalog." });
    const note = item.reason?.trim();
    if (note && /printed supplement OCR/i.test(note)) {
      lines.push({ tone: "info", text: note });
    }
    if (note && /Cover fingerprint favors another issue/i.test(note)) {
      lines.push({ tone: "info", text: note });
    }
    return lines;
  }
  if (item.status === "auto_matched" && item.match_source === "learned_barcode") {
    lines.push({ tone: "success", text: "Barcode linked to your catalog for future scans." });
  }
  return lines;
}

function intakeUserReason(item: IntakeItem): string | null {
  if (isVerifiedLocalBarcodeMatch(item)) {
    return null;
  }
  const raw = item.reason?.trim();
  if (!raw) return null;
  if (/printed supplement OCR/i.test(raw)) {
    return null;
  }
  if (/Cover fingerprint favors another issue/i.test(raw)) {
    return null;
  }
  if (/Cover fingerprint strongly suggests/i.test(raw) && item.status === "auto_matched") {
    return null;
  }
  if (raw.startsWith("Match failed validation: ")) {
    const detail = raw.slice("Match failed validation: ".length);
    if (/expects dc/i.test(detail) && /unknown/i.test(detail)) {
      return "We read the barcode but couldn’t tie it to a catalog record yet. Use Import & Accept or pick the issue.";
    }
    if (/encodes issue #/i.test(detail)) {
      return "Barcode issue number doesn’t match the catalog hit — pick the correct issue.";
    }
    return detail;
  }
  if (raw.startsWith("No catalog or ComicVine match")) {
    return "No match in catalog yet — import from ComicVine or search manually.";
  }
  if (raw.startsWith("Not in your catalog yet") && raw.includes("GCD match found")) {
    return raw;
  }
  if (raw.startsWith("Not in your catalog yet") && raw.includes("ready to auto-import from GCD")) {
    return raw;
  }
  if (raw.startsWith("Not in your catalog yet")) {
    return raw;
  }
  if (raw.includes("5-digit supplement")) {
    return "Couldn’t read the full barcode — rescan with the supplement visible.";
  }
  if (raw.startsWith("Barcode match needs cover confirmation")) {
    return "Barcode matched but cover didn’t confirm — review or pick the issue.";
  }
  return raw;
}

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  processing: "Processing",
  auto_matched: "Auto matched",
  ready_for_review: "Ready for review",
  needs_review: "Needs review",
  needs_full_cover_photo: "Full cover photo",
  added_to_inventory: "Added to inventory",
  rejected: "Rejected",
  failed: "Failed",
};

function StatusBadge({ status }: { status: string }): JSX.Element {
  const tone =
    status === "auto_matched" || status === "added_to_inventory"
      ? "bg-emerald-600/25 text-emerald-200"
      : status === "ready_for_review"
        ? "bg-sky-600/25 text-sky-200"
        : status === "needs_review"
          ? "bg-orange-600/25 text-orange-200"
          : status === "needs_full_cover_photo"
            ? "bg-fuchsia-600/25 text-fuchsia-200"
            : status === "failed" || status === "rejected"
            ? "bg-rose-600/25 text-rose-200"
            : "bg-slate-700/50 text-slate-300";
  const label =
    status === "auto_matched" ? "Ready to add" : (STATUS_LABEL[status] ?? status);
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${tone}`}>
      {label}
    </span>
  );
}

export function IntakeReviewPage(): JSX.Element {
  const { token = "" } = useParams();
  const [review, setReview] = useState<IntakeReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [pickerItem, setPickerItem] = useState<IntakeItem | null>(null);
  const [pickerQuery, setPickerQuery] = useState("");
  const [pickerResults, setPickerResults] = useState<IntakeCatalogSearchResult[]>([]);
  const [pickerBusy, setPickerBusy] = useState(false);
  const fullCoverCameraInputRef = useRef<HTMLInputElement | null>(null);
  const fullCoverUploadInputRef = useRef<HTMLInputElement | null>(null);
  const [fullCoverItemId, setFullCoverItemId] = useState<number | null>(null);
  const [handoffItemId, setHandoffItemId] = useState<number | null>(null);
  const [handoffQr, setHandoffQr] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const handoffUrl =
    handoffItemId != null && token
      ? `${window.location.origin}/intake/full-cover/${token}/${handoffItemId}`
      : null;

  useEffect(() => {
    if (!handoffUrl) {
      setHandoffQr(null);
      return;
    }
    let active = true;
    void QRCode.toDataURL(handoffUrl, { width: 240, margin: 1 })
      .then((url) => {
        if (active) setHandoffQr(url);
      })
      .catch(() => {
        if (active) setHandoffQr(null);
      });
    return () => {
      active = false;
    };
  }, [handoffUrl]);

  const onTakeFullCoverPhoto = (itemId: number) => {
    setFullCoverItemId(itemId);
    if (isDirectCameraCaptureDevice()) {
      // Phone/tablet: open the native camera right here.
      fullCoverCameraInputRef.current?.click();
    } else {
      // Desktop: hand off to the phone via QR/link.
      setHandoffItemId(itemId);
    }
  };

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getIntakeReview(token);
      setReview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load review");
    }
  }, [token]);

  useEffect(() => {
    // Deployment marker so we can confirm in the field which frontend build is live.
    console.info(
      `[ComicOS] intake-review build sha=${FRONTEND_BUILD_SHA} built=${FRONTEND_BUILD_TIME}`,
    );
  }, []);

  useEffect(() => {
    void load();
    pollRef.current = window.setInterval(() => void load(), 2000);
    return () => {
      if (pollRef.current != null) window.clearInterval(pollRef.current);
    };
  }, [load]);

  const applyItem = (updated: IntakeItem) => {
    setReview((prev) =>
      prev ? { ...prev, items: prev.items.map((it) => (it.id === updated.id ? updated : it)) } : prev,
    );
  };

  const runAction = async (id: number, fn: () => Promise<IntakeItem>) => {
    setBusyId(id);
    setError(null);
    try {
      applyItem(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyId(null);
      void load();
    }
  };

  const onAddAll = async () => {
    setError(null);
    try {
      const result = await addAllHighConfidence(token);
      await load();
      if (result.skipped?.length) {
        const msg =
          result.added > 0
            ? `Added ${result.added}; ${result.skipped.length} skipped: ${result.skipped[0]}`
            : result.skipped.join(" ");
        setError(msg);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add all failed");
    }
  };

  const openPicker = (item: IntakeItem) => {
    setPickerItem(item);
    setPickerQuery(item.matched_series ?? "");
    setPickerResults([]);
  };

  const runPickerSearch = async () => {
    if (!pickerQuery.trim()) return;
    setPickerBusy(true);
    setError(null);
    try {
      const data = await searchCatalogIssues(
        pickerQuery,
        pickerItem?.matched_issue_number ?? undefined,
      );
      setPickerResults(data.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setPickerBusy(false);
    }
  };

  const choosePickerResult = async (catalogIssueId: number) => {
    if (!pickerItem) return;
    const itemId = pickerItem.id;
    setPickerBusy(true);
    setError(null);
    try {
      applyItem(await chooseIntakeItemIssue(itemId, catalogIssueId));
      setPickerItem(null);
      setPickerResults([]);
      void load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not choose issue");
    } finally {
      setPickerBusy(false);
    }
  };

  const counts = review?.counts;
  const items = review?.items ?? [];

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <header className="mx-auto mb-5 max-w-3xl">
        <h1 className="text-xl font-semibold text-white">Intake Review</h1>
        <p className="mt-1 text-sm text-slate-300">
          Books identify in the background — review and add to inventory while scanning continues.
        </p>
      </header>

      {counts ? (
        <div className="mx-auto mb-5 grid max-w-3xl grid-cols-2 gap-2.5 sm:grid-cols-4" data-testid="intake-counts">
          {COUNT_CARDS.map((card) => (
            <div
              key={card.key}
              className={`rounded-xl border border-slate-800 bg-slate-900/90 px-3 py-3 text-center shadow-sm shadow-black/20 border-l-4 ${card.border}`}
            >
              <div className={`text-2xl font-bold tabular-nums ${card.value}`} data-testid={`count-${card.key}`}>
                {counts[card.key]}
              </div>
              <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {card.label}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="mx-auto mb-4 flex max-w-3xl items-center justify-between gap-3">
        <span className="text-sm font-medium text-slate-300">{items.length} items</span>
        <button
          type="button"
          onClick={() => void onAddAll()}
          disabled={!counts || counts.auto_matched === 0}
          className="rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950 shadow-sm shadow-emerald-950/30 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500 disabled:shadow-none"
        >
          Add all high-confidence ({counts?.auto_matched ?? 0})
        </button>
      </div>

      {error ? (
        <p className="mx-auto mb-3 max-w-3xl rounded-lg bg-rose-600/20 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <div className="mx-auto max-w-3xl space-y-3">
        {items.map((item) => {
          const busy = busyId === item.id;
          const canConfirm = item.selected_catalog_issue_id != null;
          const localMatch = isLocalCatalogBarcodeMatch(item);
          const reviewable =
            item.status === "ready_for_review" ||
            item.status === "needs_review" ||
            item.status === "needs_full_cover_photo" ||
            item.status === "auto_matched";
          const needsFullCover = intakeNeedsFullCoverPhoto(item);
          const gap = intakeBarcodeGap(item);
          const gapAutoImport =
            gap?.action === "auto_import_available" || gap?.ready_to_auto_import === true;
          const fpCandidates = intakeFingerprintReviewCandidates(item);
          const cvReview = intakeComicvineReviewCandidate(item);
          const canImport =
            !needsFullCover &&
            !canConfirm &&
            reviewable &&
            item.status !== "auto_matched" &&
            (item.matched_series != null || item.normalized_barcode != null || gapAutoImport);
          return (
            <article key={item.id} className="flex gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
              <img
                src={intakeImageUrl(item)}
                alt="scan"
                className="h-24 w-20 shrink-0 rounded-lg object-cover"
                loading="lazy"
              />
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <StatusBadge status={item.status} />
                </div>
                <p className="text-base font-semibold text-slate-50">{intakeHeadline(item)}</p>
                {intakeSubtitle(item) ? (
                  <p className="text-sm text-slate-400">{intakeSubtitle(item)}</p>
                ) : null}
                {intakeBarcode(item) ? (
                  <p className="mt-1 font-mono text-xs text-slate-500">{intakeBarcode(item)}</p>
                ) : null}
                {intakeInfoMessage(item).map((info) => (
                  <p
                    key={info.text}
                    className={`mt-2 text-sm ${
                      info.tone === "success"
                        ? "text-sky-200"
                        : info.tone === "info"
                          ? "text-slate-400"
                          : "text-orange-200/90"
                    }`}
                  >
                    {info.text}
                  </p>
                ))}
                {!localMatch &&
                item.barcode_read?.supplement_disagreement &&
                item.barcode_read.decoded_supplement !== item.barcode_read.final_supplement ? (
                  <p className="mt-1 text-xs text-amber-300/90">
                    Barcode and printed supplement disagree — confirm before adding.
                  </p>
                ) : null}
                {gapAutoImport && !canConfirm ? (
                  <p className="mt-2 text-sm text-indigo-200/90">
                    {cvReview?.import_ready
                      ? "ComicVine candidate — use Import & Accept to add to your catalog."
                      : "GCD barcode match — use Import & Accept to add to your catalog."}
                  </p>
                ) : null}
                {fpCandidates.length > 0 ? (
                  <ul className="mt-2 space-y-1.5" data-testid={`fp-candidates-${item.id}`}>
                    {fpCandidates.map((row, idx) => (
                      <li
                        key={`${row.series}-${row.issue_number}-${idx}`}
                        className="rounded-md border border-slate-700/80 bg-slate-950/40 px-2 py-1.5 text-xs text-slate-300"
                      >
                        <span className="font-semibold text-slate-100">
                          {row.series || row.title || "Series unknown"}
                          {row.issue_number ? ` #${String(row.issue_number).replace(/^#/, "")}` : ""}
                        </span>
                        {row.publisher ? <span className="text-slate-400"> · {row.publisher}</span> : null}
                        {row.confidence != null ? (
                          <span className="text-slate-500">
                            {" "}
                            · {(Number(row.confidence) * 100).toFixed(0)}% · Fingerprint
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {cvReview && !gapAutoImport ? (
                  <p className="mt-2 text-sm text-violet-200/90" data-testid={`cv-candidate-${item.id}`}>
                    ComicVine candidate: {cvReview.series ?? cvReview.title} #{cvReview.issue_number ?? "?"} — Import
                    &amp; Accept when ready.
                  </p>
                ) : null}
                {needsFullCover ? (
                  <p
                    className="mt-2 text-sm text-fuchsia-200/90"
                    data-testid={`full-cover-prompt-${item.id}`}
                  >
                    {FULL_COVER_PROMPT}
                  </p>
                ) : null}
                {intakeUserReason(item) && !needsFullCover ? (
                  <p className="mt-2 text-sm text-orange-200/90">{intakeUserReason(item)}</p>
                ) : null}
                {item.error ? <p className="mt-1 text-sm text-rose-300/90">{item.error}</p> : null}

                {item.status !== "added_to_inventory" && item.status !== "rejected" ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {item.status === "ready_for_review" && canConfirm ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void runAction(item.id, () => acceptIntakeItem(item.id))}
                        className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                      >
                        Accept match
                      </button>
                    ) : null}
                    {canImport ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void runAction(item.id, () => importAndAcceptIntakeItem(item.id))}
                        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                      >
                        Import &amp; Accept
                      </button>
                    ) : null}
                    {reviewable ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => openPicker(item)}
                        className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                      >
                        Choose different issue
                      </button>
                    ) : null}
                    {canConfirm ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void runAction(item.id, () => addIntakeItemToInventory(item.id))}
                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50 ${
                          localMatch ? "bg-emerald-500 text-slate-950" : "bg-sky-700"
                        }`}
                      >
                        Add to inventory
                      </button>
                    ) : null}
                    {needsFullCover ? (
                      <FullCoverPhotoActions
                        itemId={item.id}
                        busy={busy}
                        onTakePhoto={() => onTakeFullCoverPhoto(item.id)}
                        onUploadPhoto={() => {
                          setFullCoverItemId(item.id);
                          fullCoverUploadInputRef.current?.click();
                        }}
                      />
                    ) : null}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void runAction(item.id, () => requeueIntakeItem(item.id))}
                      className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                    >
                      Rescan
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void runAction(item.id, () => rejectIntakeItem(item.id))}
                      className="rounded-lg border border-rose-600/60 px-3 py-1.5 text-xs font-medium text-rose-200 disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
              </div>
            </article>
          );
        })}
        {items.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-600 bg-slate-900/40 py-10 text-center text-sm text-slate-400">
            No scans yet. Start scanning on your phone — items appear here as they process.
          </p>
        ) : null}
      </div>

      <input
        ref={fullCoverCameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        data-testid="full-cover-camera-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          const id = fullCoverItemId;
          e.target.value = "";
          if (!file || id == null) return;
          void runAction(id, () => uploadIntakeFullCoverPhoto(id, file));
        }}
      />
      <input
        ref={fullCoverUploadInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        data-testid="full-cover-upload-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          const id = fullCoverItemId;
          e.target.value = "";
          if (!file || id == null) return;
          void runAction(id, () => uploadIntakeFullCoverPhoto(id, file));
        }}
      />

      {handoffItemId != null && handoffUrl ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div
            className="w-full max-w-sm rounded-2xl border border-fuchsia-500/40 bg-slate-900 p-5 text-center"
            data-testid="full-cover-handoff-modal"
          >
            <h3 className="text-base font-semibold text-fuchsia-100">
              Take the cover photo on your phone
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              Scan this code with your phone camera. It opens the camera, you snap the cover,
              and this screen refreshes automatically.
            </p>
            {handoffQr ? (
              <img
                src={handoffQr}
                alt="Scan to open the camera on your phone"
                className="mx-auto mt-4 h-48 w-48 rounded-lg bg-white p-2"
                data-testid="full-cover-handoff-qr"
              />
            ) : (
              <div className="mx-auto mt-4 h-48 w-48 animate-pulse rounded-lg bg-slate-800" />
            )}
            <a
              href={handoffUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-4 block break-all rounded-lg border border-slate-700 px-3 py-2 text-[11px] text-sky-300"
            >
              {handoffUrl}
            </a>
            <div className="mt-4 flex justify-center gap-2">
              <button
                type="button"
                className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium"
                onClick={() => {
                  void navigator.clipboard?.writeText(handoffUrl).catch(() => undefined);
                }}
              >
                Copy link
              </button>
              <button
                type="button"
                className="rounded-lg border border-fuchsia-500/60 px-3 py-1.5 text-xs font-medium text-fuchsia-100"
                onClick={() => {
                  setFullCoverItemId(handoffItemId);
                  fullCoverUploadInputRef.current?.click();
                  setHandoffItemId(null);
                }}
              >
                Upload a file instead
              </button>
              <button
                type="button"
                className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-semibold"
                onClick={() => setHandoffItemId(null)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <footer
        className="mx-auto mt-8 max-w-3xl text-center text-[10px] text-slate-600"
        data-testid="frontend-build-marker"
      >
        build {FRONTEND_BUILD_SHA_SHORT} · {FRONTEND_BUILD_TIME}
      </footer>

      {pickerItem ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4">
          <div className="mt-10 w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">Choose different issue</h2>
              <button
                type="button"
                onClick={() => setPickerItem(null)}
                className="rounded-lg border border-slate-600 px-2 py-1 text-xs"
              >
                Close
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void runPickerSearch();
              }}
              className="mb-3 flex gap-2"
            >
              <input
                value={pickerQuery}
                onChange={(e) => setPickerQuery(e.target.value)}
                placeholder="Search series, e.g. Superman"
                className="flex-1 rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm"
                aria-label="Catalog search"
              />
              <button
                type="submit"
                disabled={pickerBusy}
                className="rounded-lg bg-sky-700 px-3 py-2 text-sm font-semibold disabled:opacity-50"
              >
                Search
              </button>
            </form>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {pickerResults.map((res) => (
                <button
                  key={res.catalog_issue_id}
                  type="button"
                  disabled={pickerBusy}
                  onClick={() => void choosePickerResult(res.catalog_issue_id)}
                  className="flex w-full items-center gap-3 rounded-lg border border-slate-700 bg-slate-800/50 p-2 text-left hover:border-sky-500 disabled:opacity-50"
                >
                  {res.cover_url ? (
                    <img src={res.cover_url} alt="" className="h-14 w-10 rounded object-cover" loading="lazy" />
                  ) : (
                    <div className="h-14 w-10 rounded bg-slate-700" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {[res.series, res.issue_number ? `#${res.issue_number}` : null].filter(Boolean).join(" ") ||
                        "Untitled"}
                    </p>
                    <p className="truncate text-xs text-slate-500">{res.publisher || ""}</p>
                  </div>
                </button>
              ))}
              {pickerResults.length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-500">
                  {pickerBusy ? "Searching…" : "Search the catalog to pick the correct issue."}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
