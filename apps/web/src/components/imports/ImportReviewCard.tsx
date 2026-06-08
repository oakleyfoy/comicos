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
  hasCoverImage?: boolean;
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
  index: number;
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
}

const INPUT_CLASS_NAME =
  "w-full rounded-xl border border-slate-600 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-cyan-400/70";

function coverImageKey(item: ImportReviewCardItem): string {
  return [item.coverThumbnailUrl, item.coverImageUrl, item.coverName].filter(Boolean).join("|");
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

function CoverThumbnail({ item }: { item: ImportReviewCardItem }) {
  const src = item.coverThumbnailUrl || item.coverImageUrl || null;
  const alt = titleIssueLabel(item);
  if (src) {
    return (
      <img
        key={coverImageKey(item)}
        src={src}
        alt={alt}
        loading="lazy"
        className="h-full w-full object-cover"
      />
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
  index,
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
}: ImportReviewCardProps) {
  const compactCoverLabel = getCompactCoverLabel(item.coverName);

  return (
    <article className={`rounded-2xl border-2 p-4 ${cardSurfaceClassName}`}>
      <div className="flex gap-3">
        <div className="h-28 w-20 shrink-0 overflow-hidden rounded-xl border border-slate-600 bg-slate-800 sm:h-32 sm:w-24">
          <CoverThumbnail item={item} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-white">{titleIssueLabel(item)}</p>
              <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-400">
                Draft Item {index + 1}
              </p>
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

          <div className="mt-2 flex flex-wrap items-center gap-2">
            {lifecycleBadge ? (
              <p
                className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${lifecycleBadge.className}`}
              >
                {lifecycleBadge.label}
              </p>
            ) : null}
            {item.releaseDate.trim() ? (
              <p className="text-sm font-medium text-white">{item.releaseDate.trim()}</p>
            ) : null}
          </div>

          {lifecycleBadge?.detail ? (
            <p className="mt-1.5 text-sm text-slate-100">{lifecycleBadge.detail}</p>
          ) : null}
          {item.catalogReleaseSourceText ? (
            <p className="mt-1 text-sm text-slate-300">{item.catalogReleaseSourceText}</p>
          ) : null}

          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-200">
            <span>Qty {item.quantity.trim() || "1"}</span>
            <span>{formatCompactPrice(item.rawItemPrice)}</span>
            <span>{compactPublisherLabel(item.publisher)}</span>
            {compactCoverLabel ? <span className="truncate">{compactCoverLabel}</span> : null}
          </div>

          <div className="mt-3">
            <button
              type="button"
              onClick={onToggleDetails}
              className="rounded-xl border border-slate-500 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white transition hover:border-cyan-400/70 hover:bg-slate-700"
              aria-expanded={isExpanded}
            >
              {isExpanded ? "Hide Details" : "Show Details"}
            </button>
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
                value={item.releaseDate}
                onChange={(event) => onUpdate("releaseDate", event.target.value)}
                placeholder="2024, 2024-05, or 2024-05-15"
                className={INPUT_CLASS_NAME}
              />
              <p className="text-sm text-slate-400">
                Optional. Exact dates are preserved when provided; year-only values stay year-only.
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

            <label className="space-y-2">
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
              <input
                type="number"
                min="0"
                step="0.01"
                value={item.rawItemPrice}
                onChange={(event) => {
                  onUpdate("rawItemPrice", event.target.value);
                  clearItemError("rawItemPrice");
                }}
                className={INPUT_CLASS_NAME}
              />
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
