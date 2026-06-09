import { useEffect, useRef, useState } from "react";

import { apiClient } from "../../api/client";
import { formatCalendarDateWithYear, formatCalendarDateUsShort, normalizeCalendarDateInput } from "../../utils/formatCalendarDate";
import { normalizeMoneyInput } from "../../utils/moneyInput";
import { importCoverExceptionBadge, formatImportCoverSourceLabel, resolveImportLineCoverUrl } from "../../utils/importCoverPresentation";

interface ImportReviewCardItem {
  publisher: string;
  title: string;
  releaseDate: string;
  releaseStatus: "" | "released" | "not_released_yet" | "unknown";
  orderStatus: "" | "ordered" | "preordered" | "shipped" | "received" | "cancelled";
  issueNumber: string;
  coverName: string;
  printing: string;
  ratio: string;
  variantType: string;
  coverArtist: string;
  quantity: string;
  rawItemPrice: string;
  catalogReleaseSourceText?: string;
  coverImageUrl?: string;
  coverThumbnailUrl?: string;
  coverUrl?: string | null;
  retailerCoverUrl?: string | null;
  retailerProductUrl?: string | null;
  retailerOrderNumber?: string | null;
  retailerItemStatus?: string | null;
  retailerLookupStatus?: string | null;
  retailerLookupScore?: number | null;
  retailerLookupRejectedReason?: string | null;
  hasCoverImage?: boolean;
  coverResolutionDebug?: Record<string, unknown> | null;
  coverSource?: "RETAILER" | "LOCG" | "EXTERNAL_CATALOG" | "USER_UPLOAD" | null;
  coverConfidence?: number | null;
  variantConfidence?: number | null;
  coverVerifiedBy?: "SYSTEM" | "USER" | null;
  importLineCoverImageId?: number | null;
}

interface ImportReviewCardFieldErrors {
  publisher?: string;
  title?: string;
  issueNumber?: string;
  quantity?: string;
  rawItemPrice?: string;
}

type ImportReviewCardEditableField =
  | "publisher"
  | "title"
  | "releaseDate"
  | "releaseStatus"
  | "orderStatus"
  | "issueNumber"
  | "coverName"
  | "printing"
  | "ratio"
  | "variantType"
  | "coverArtist"
  | "quantity"
  | "rawItemPrice";

interface LifecycleBadgePresentation {
  label: string;
  detail: string | null;
  className: string;
}

interface ImportReviewCardProps {
  item: ImportReviewCardItem;
  isExpanded: boolean;
  canRemove: boolean;
  isSubmitting: boolean;
  itemError?: ImportReviewCardFieldErrors;
  lifecycleBadge: LifecycleBadgePresentation | null;
  cardSurfaceClassName: string;
  onToggleDetails: () => void;
  onRemove: () => void;
  onUpdate: (field: ImportReviewCardEditableField, value: string) => void;
  clearItemError: (field: keyof ImportReviewCardFieldErrors) => void;
  canScanCover: boolean;
  scanCoverBusy: boolean;
  onScanCoverSelected: (file: File) => void;
  coverSourceLabel?: string | null;
  coverExceptionBadge?: string | null;
  onWrongCoverSearch?: () => void;
}

const INPUT_CLASS_NAME =
  "w-full rounded-xl border border-slate-600 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-cyan-400/70";

function formatCoverResolutionDebugLine(debug: Record<string, unknown> | null | undefined): string | null {
  if (!debug || typeof debug !== "object") {
    return null;
  }
  const outcome = typeof debug.outcome === "string" ? debug.outcome : "unknown";
  const reason = typeof debug.reason === "string" ? debug.reason : null;
  const hydrateAttempted = debug.locg_hydrate_attempted;
  const hydrated = debug.locg_hydrated;
  const parts = [`Cover debug: ${outcome}`];
  if (reason) {
    parts.push(reason);
  }
  if (hydrateAttempted === true || hydrateAttempted === false) {
    parts.push(`LOCG hydrate attempted=${String(hydrateAttempted)}`);
  }
  if (hydrated === true || hydrated === false) {
    parts.push(`hydrated=${String(hydrated)}`);
  }
  const hydrateReason =
    typeof debug.locg_hydrate_no_match_reason === "string"
      ? debug.locg_hydrate_no_match_reason
      : null;
  if (hydrateReason) {
    parts.push(hydrateReason);
  }
  const externalIssueId = debug.external_issue_id;
  if (typeof externalIssueId === "number") {
    parts.push(`external_issue_id=${externalIssueId}`);
  }
  const variantLabel = debug.matched_variant_cover_label;
  if (typeof variantLabel === "string" && variantLabel.trim()) {
    parts.push(`variant=${variantLabel.trim()}`);
  }
  const requestedLetter = debug.requested_cover_letter;
  const matchedLetter = debug.matched_variant_letter;
  if (typeof requestedLetter === "string" && typeof matchedLetter === "string") {
    parts.push(`letter ${requestedLetter}→${matchedLetter}`);
  }
  return parts.join(" · ");
}

function coverImageKey(item: ImportReviewCardItem): string {
  return [item.issueNumber, item.coverThumbnailUrl, item.coverImageUrl, item.coverName]
    .filter(Boolean)
    .join("|");
}

function formatCompactPrice(value: string): string {
  const parsed = Number(value);
  if (Number.isFinite(parsed)) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(parsed);
  }
  return value.trim() || "$0.00";
}

function titleIssueLabel(item: ImportReviewCardItem): string {
  const title = item.title.trim() || "Untitled item";
  const issue = item.issueNumber.trim();
  return issue ? `${title} #${issue}` : title;
}

function compactPublisherLabel(publisher: string): string {
  return publisher.trim() || "Publisher pending";
}

export function getCompactCoverLabel(coverName: string | null | undefined): string | null {
  const raw = coverName?.trim();
  if (!raw) {
    return null;
  }
  const labelMatch = raw.match(/\b(Cover\s+[A-Z0-9]+)\b/i);
  const label = labelMatch ? labelMatch[1].replace(/\s+/g, " ").trim() : null;
  let working = raw.replace(/\b(Cover\s+[A-Z0-9]+)\b/i, " ");
  working = working.replace(/\b(?:regular|variant|wraparound|connecting|incentive|virgin|foil|card stock|edition)\b/gi, " ");
  working = working.replace(/\bcover\b/gi, " ");
  working = working.replace(/&/g, " ");
  working = working.replace(/\s+/g, " ").trim();
  const artistMatch = working.match(/[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2}/);
  const artist = artistMatch?.[0]?.trim() || null;
  if (label && artist) {
    return `${label} • ${artist}`;
  }
  if (label) {
    return label;
  }
  return artist || raw;
}

function isDirectCoverUrl(url: string): boolean {
  return /^https?:\/\//i.test(url.trim());
}

function coverFetchPath(url: string): string {
  const trimmed = url.trim();
  if (trimmed.startsWith("/")) {
    return trimmed;
  }
  return `/${trimmed}`;
}

function CoverThumbnail({ item }: { item: ImportReviewCardItem }) {
  const rawSrc = resolveImportLineCoverUrl({
    coverUrl: item.coverUrl,
    coverThumbnailUrl: item.coverThumbnailUrl,
    coverImageUrl: item.coverImageUrl,
    retailerCoverUrl: item.retailerCoverUrl,
  });
  const retailerLink = item.retailerProductUrl?.trim() || null;
  const alt = titleIssueLabel(item);
  const [displaySrc, setDisplaySrc] = useState<string | null>(
    rawSrc && isDirectCoverUrl(rawSrc) ? rawSrc : null,
  );

  useEffect(() => {
    if (!rawSrc) {
      setDisplaySrc(null);
      return undefined;
    }
    if (isDirectCoverUrl(rawSrc)) {
      setDisplaySrc(rawSrc);
      return undefined;
    }

    let cancelled = false;
    let objectUrl: string | null = null;

    void apiClient
      .fetchCoverImageBlob(coverFetchPath(rawSrc))
      .then((blob) => {
        if (cancelled) {
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setDisplaySrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) {
          setDisplaySrc(null);
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [rawSrc]);

  if (displaySrc) {
    const image = (
      <img
        key={coverImageKey(item)}
        src={displaySrc}
        alt={alt}
        loading="lazy"
        className="h-full w-full object-cover"
      />
    );
    return retailerLink ? (
      <a href={retailerLink} target="_blank" rel="noreferrer" className="block h-full w-full">
        {image}
      </a>
    ) : (
      image
    );
  }
  if (rawSrc) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-800 text-[10px] font-medium uppercase tracking-wide text-slate-400">
        Loading…
      </div>
    );
  }
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-slate-800 text-center">
      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
        COMICOS
      </span>
      <span className="mt-2 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">
        NO COVER
      </span>
    </div>
  );
}

export function ImportReviewCard({
  item,
  isExpanded,
  canRemove,
  isSubmitting,
  itemError,
  lifecycleBadge,
  cardSurfaceClassName,
  onToggleDetails,
  onRemove,
  onUpdate,
  clearItemError,
  canScanCover,
  scanCoverBusy,
  onScanCoverSelected,
  coverSourceLabel,
  coverExceptionBadge,
  onWrongCoverSearch,
}: ImportReviewCardProps) {
  const compactCoverLabel = getCompactCoverLabel(item.coverName);
  const scanCoverInputRef = useRef<HTMLInputElement>(null);
  const releaseDateLabel =
    formatCalendarDateWithYear(item.releaseDate) ?? item.releaseDate.trim();
  const coverDebugLine = formatCoverResolutionDebugLine(item.coverResolutionDebug);
  const resolvedCoverSourceLabel =
    coverSourceLabel ?? formatImportCoverSourceLabel(item.coverSource ?? null, null);
  const resolvedExceptionBadge =
    coverExceptionBadge ??
    importCoverExceptionBadge({
      hasCoverImage: item.hasCoverImage,
      coverConfidence: item.coverConfidence,
      variantConfidence: item.variantConfidence,
    });
  const retailerProductUrl = item.retailerProductUrl?.trim() || null;

  return (
    <article className={`rounded-2xl border-2 p-4 ${cardSurfaceClassName}`}>
      <div className="flex gap-3">
        <div className="h-28 w-20 shrink-0 overflow-hidden rounded-xl border border-slate-600 bg-slate-800 sm:h-32 sm:w-24">
          <CoverThumbnail item={item} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                {retailerProductUrl ? (
                  <a
                    href={retailerProductUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate text-base font-semibold text-white underline decoration-cyan-300/30 underline-offset-2 hover:text-cyan-100"
                  >
                    {titleIssueLabel(item)}
                  </a>
                ) : (
                  <p className="truncate text-base font-semibold text-white">{titleIssueLabel(item)}</p>
                )}
                {lifecycleBadge ? (
                  <span
                    className={`inline-flex shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${lifecycleBadge.className}`}
                  >
                    {lifecycleBadge.label}
                  </span>
                ) : null}
              </div>
            </div>
            {canRemove ? (
              <button
                type="button"
                disabled={isSubmitting}
                onClick={onRemove}
                className="shrink-0 rounded-xl border border-rose-400/50 bg-rose-950 px-2.5 py-1 text-xs font-semibold text-rose-100 transition hover:bg-rose-900"
              >
                Remove
              </button>
            ) : null}
          </div>

          {item.releaseDate.trim() ? (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-white">{releaseDateLabel}</p>
            </div>
          ) : null}

          {lifecycleBadge?.detail ? (
            <p className="mt-1.5 text-sm text-slate-100">{lifecycleBadge.detail}</p>
          ) : null}
          {item.catalogReleaseSourceText ? (
            <p className="mt-1 text-sm text-slate-300">{item.catalogReleaseSourceText}</p>
          ) : null}
          {resolvedCoverSourceLabel ? (
            <p className="mt-1 text-sm text-cyan-100/90">{resolvedCoverSourceLabel}</p>
          ) : null}
          {retailerProductUrl && item.coverSource === "RETAILER" ? (
            <p className="mt-1 text-sm text-cyan-100/90">
              {item.retailerOrderNumber
                ? "Cover from connected retailer order item"
                : "Cover from retailer product match"}
            </p>
          ) : null}
          {item.retailerItemStatus ? (
            <p className="mt-1 text-sm text-slate-300">Retailer status: {item.retailerItemStatus}</p>
          ) : null}
          {item.retailerLookupStatus === "possible_match" ? (
            <p className="mt-1 text-sm text-amber-100/90">Possible retailer match needs review</p>
          ) : null}
          {resolvedExceptionBadge ? (
            <span className="mt-2 inline-flex rounded-full border border-amber-400/40 bg-amber-500/15 px-2.5 py-0.5 text-xs font-semibold text-amber-100">
              {resolvedExceptionBadge}
            </span>
          ) : null}
          {coverDebugLine ? (
            <p className="mt-1 font-mono text-[11px] leading-snug text-amber-200/70">{coverDebugLine}</p>
          ) : null}

          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-200">
            <span>Qty {item.quantity.trim() || "1"}</span>
            <span>{formatCompactPrice(item.rawItemPrice)}</span>
            <span>{compactPublisherLabel(item.publisher)}</span>
            {compactCoverLabel ? <span className="truncate">{compactCoverLabel}</span> : null}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onToggleDetails}
              className="rounded-xl border border-slate-500 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white transition hover:border-cyan-400/70 hover:bg-slate-700"
              aria-expanded={isExpanded}
            >
              {isExpanded ? "Hide Details" : "Show Details"}
            </button>
            <input
              ref={scanCoverInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif"
              className="hidden"
              onChange={(event) => {
                const picked = event.target.files?.[0];
                event.target.value = "";
                if (picked) {
                  onScanCoverSelected(picked);
                }
              }}
            />
            <button
              type="button"
              disabled={!canScanCover || scanCoverBusy || isSubmitting}
              title={
                canScanCover
                  ? "Upload a reference scan for this line only"
                  : "Save a draft first to attach cover scans"
              }
              onClick={() => scanCoverInputRef.current?.click()}
              className="rounded-xl border border-cyan-400/40 bg-cyan-950/80 px-3 py-1.5 text-xs font-semibold text-cyan-100 transition hover:border-cyan-300/70 hover:bg-cyan-900/80 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {scanCoverBusy ? "Uploading scan…" : "Scan cover"}
            </button>
            {canScanCover || onWrongCoverSearch ? (
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => scanCoverInputRef.current?.click()}
                className="rounded-xl border border-slate-500 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-100 transition hover:border-amber-400/50 hover:bg-slate-700 disabled:opacity-50"
              >
                Wrong cover? Replace
              </button>
            ) : null}
            {onWrongCoverSearch ? (
              <button
                type="button"
                disabled={isSubmitting}
                onClick={onWrongCoverSearch}
                className="rounded-xl border border-slate-500 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-100 transition hover:border-cyan-400/50 hover:bg-slate-700 disabled:opacity-50"
              >
                Search catalog
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {isExpanded ? (
        <div className="mt-4 border-t border-slate-600 pt-4">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-200">Publisher</span>
              <input
                value={item.publisher}
                onChange={(event) => {
                  onUpdate("publisher", event.target.value);
                  clearItemError("publisher");
                }}
                className={INPUT_CLASS_NAME}
              />
              {itemError?.publisher ? (
                <p className="text-sm text-rose-300">{itemError.publisher}</p>
              ) : !item.publisher.trim() ? (
                <p className="text-sm text-slate-400">
                  Leave blank only when unclear. Saving the draft lets the server infer obvious publishers.
                </p>
              ) : null}
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Title</span>
              <input
                value={item.title}
                onChange={(event) => {
                  onUpdate("title", event.target.value);
                  clearItemError("title");
                }}
                className={INPUT_CLASS_NAME}
              />
              {itemError?.title ? <p className="text-sm text-rose-300">{itemError.title}</p> : null}
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Release Date</span>
              <input
                value={formatCalendarDateUsShort(item.releaseDate)}
                onChange={(event) => onUpdate("releaseDate", event.target.value)}
                onBlur={(event) => {
                  onUpdate("releaseDate", normalizeCalendarDateInput(event.target.value));
                }}
                placeholder="6/17/2026"
                className={INPUT_CLASS_NAME}
              />
              <p className="text-sm text-slate-400">
                Optional. Use M/D/YYYY for full dates; year-only values stay year-only.
              </p>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Release Status</span>
              <select
                value={item.releaseStatus}
                onChange={(event) => onUpdate("releaseStatus", event.target.value)}
                className={INPUT_CLASS_NAME}
              >
                <option value="">Auto from release date</option>
                <option value="not_released_yet">Preorder / Upcoming Release</option>
                <option value="released">Released</option>
                <option value="unknown">Unknown</option>
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Order Status</span>
              <select
                value={item.orderStatus}
                onChange={(event) => onUpdate("orderStatus", event.target.value)}
                className={INPUT_CLASS_NAME}
              >
                <option value="">Auto from release / receipt</option>
                <option value="ordered">Ordered</option>
                <option value="preordered">Preordered</option>
                <option value="shipped">Shipped</option>
                <option value="received">Received</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Issue Number</span>
              <input
                value={item.issueNumber}
                onChange={(event) => {
                  onUpdate("issueNumber", event.target.value);
                  clearItemError("issueNumber");
                }}
                className={INPUT_CLASS_NAME}
              />
              {itemError?.issueNumber ? (
                <p className="text-sm text-rose-300">{itemError.issueNumber}</p>
              ) : null}
            </label>

            <label className="space-y-2 md:col-span-2">
              <span className="text-sm font-medium text-slate-300">Cover Name</span>
              <input
                value={item.coverName}
                onChange={(event) => onUpdate("coverName", event.target.value)}
                className={INPUT_CLASS_NAME}
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Printing</span>
              <input
                value={item.printing}
                onChange={(event) => onUpdate("printing", event.target.value)}
                className={INPUT_CLASS_NAME}
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Ratio</span>
              <input
                value={item.ratio}
                onChange={(event) => onUpdate("ratio", event.target.value)}
                className={INPUT_CLASS_NAME}
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Variant Type</span>
              <input
                value={item.variantType}
                onChange={(event) => onUpdate("variantType", event.target.value)}
                className={INPUT_CLASS_NAME}
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Cover Artist</span>
              <input
                value={item.coverArtist}
                onChange={(event) => onUpdate("coverArtist", event.target.value)}
                className={INPUT_CLASS_NAME}
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Quantity</span>
              <input
                type="number"
                min="1"
                step="1"
                value={item.quantity}
                onChange={(event) => {
                  onUpdate("quantity", event.target.value);
                  clearItemError("quantity");
                }}
                className={INPUT_CLASS_NAME}
              />
              {itemError?.quantity ? (
                <p className="text-sm text-rose-300">{itemError.quantity}</p>
              ) : null}
            </label>

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Raw Item Price</span>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                  $
                </span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={item.rawItemPrice}
                  onChange={(event) => {
                    onUpdate("rawItemPrice", event.target.value);
                    clearItemError("rawItemPrice");
                  }}
                  onBlur={() => {
                    const trimmed = item.rawItemPrice.trim();
                    if (!trimmed) {
                      onUpdate("rawItemPrice", "");
                      return;
                    }
                    onUpdate("rawItemPrice", normalizeMoneyInput(item.rawItemPrice));
                  }}
                  className={`${INPUT_CLASS_NAME} pl-7`}
                />
              </div>
              {itemError?.rawItemPrice ? (
                <p className="text-sm text-rose-300">{itemError.rawItemPrice}</p>
              ) : null}
            </label>
          </div>
        </div>
      ) : null}
    </article>
  );
}
