import type { AiDraftOrderItem } from "../api/client";
import {
  buildMetadataReviewSummary,
  CREATOR_ROLE_LABELS,
  displayMetadataValue,
  formatCreatorBullets,
  metadataReviewSeverityClass,
  zipCreatorSlots,
} from "../pages/metadataReviewPresentation";

type MetadataReviewDraftCardProps = {
  index: number;
  item: AiDraftOrderItem;
  onLooksGood: () => void;
  onCreateAlias: () => void;
  onIgnoreWarning: () => void;
  actionsDisabled?: boolean;
};

export function MetadataReviewDraftCard({
  index,
  item,
  onLooksGood,
  onCreateAlias,
  onIgnoreWarning,
  actionsDisabled = false,
}: MetadataReviewDraftCardProps): JSX.Element {
  const summary = buildMetadataReviewSummary(item);
  const releaseWarn = summary.affectedField === "Release date" && summary.severity === "HIGH";
  const creatorWarn =
    summary.affectedField === "Writers" ||
    summary.affectedField === "Artists" ||
    summary.affectedField === "Cover artists";

  return (
    <article
      className={`rounded-2xl bg-slate-950/70 p-4 ${
        releaseWarn
          ? "border-2 border-rose-400/40 shadow-lg shadow-rose-950/20"
          : creatorWarn && summary.severity === "LOW"
            ? "border-2 border-fuchsia-400/35 shadow-lg shadow-fuchsia-950/20"
            : "border border-white/10"
      }`}
      data-testid={`metadata-review-item-${index}`}
    >
      <div
        className="rounded-2xl border border-cyan-400/25 bg-gradient-to-br from-slate-900/90 to-cyan-950/30 p-4"
        data-testid="metadata-review-required-card"
      >
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Review Required</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-slate-500">Issue</dt>
            <dd className="mt-0.5 text-slate-100">{summary.issue}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Severity</dt>
            <dd className="mt-1">
              <span
                className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-[0.12em] ring-1 ring-inset ${metadataReviewSeverityClass(summary.severity)}`}
                data-testid="metadata-review-severity"
              >
                {summary.severity}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Comic</dt>
            <dd className="mt-0.5 font-medium text-white">{summary.comic}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Affected Field</dt>
            <dd className="mt-0.5 text-slate-200">{summary.affectedField}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Detected Value</dt>
            <dd className="mt-0.5 text-slate-200">{summary.detectedValue}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-slate-500">Recommended Action</dt>
            <dd className="mt-0.5 text-cyan-50">{summary.recommendedAction}</dd>
          </div>
        </dl>
        {summary.noCorrectionNecessary ? (
          <p
            className="mt-3 rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100"
            data-testid="metadata-review-no-correction"
          >
            No correction appears necessary.
          </p>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={actionsDisabled}
          onClick={onLooksGood}
          className="rounded-2xl bg-emerald-400/90 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
          data-testid="metadata-review-looks-good"
        >
          Looks Good
        </button>
        <button
          type="button"
          disabled={actionsDisabled}
          onClick={onCreateAlias}
          className="rounded-2xl border border-fuchsia-400/35 bg-fuchsia-500/15 px-4 py-2 text-sm font-semibold text-fuchsia-100 transition hover:bg-fuchsia-500/25 disabled:cursor-not-allowed disabled:opacity-60"
          data-testid="metadata-review-create-alias"
        >
          Create Alias
        </button>
        <button
          type="button"
          disabled={actionsDisabled}
          onClick={onIgnoreWarning}
          className="rounded-2xl border border-white/15 bg-slate-900/80 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          data-testid="metadata-review-ignore-warning"
        >
          Ignore Warning
        </button>
      </div>

      <details className="mt-4 rounded-2xl border border-white/10 bg-slate-900/50 p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-200">Advanced Details</summary>
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Raw Parsed Metadata
              </p>
              <dl className="mt-3 space-y-2 text-sm text-slate-300">
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-slate-500">Publisher</dt>
                  <dd className="text-right">{displayMetadataValue(item.raw_publisher)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-slate-500">Title</dt>
                  <dd className="text-right">{displayMetadataValue(item.raw_title)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-slate-500">Release</dt>
                  <dd className="text-right">{displayMetadataValue(item.raw_release_date)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-slate-500">Issue</dt>
                  <dd className="text-right">{displayMetadataValue(item.raw_issue_number)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-slate-500">Variant</dt>
                  <dd className="text-right">{displayMetadataValue(item.raw_variant_text)}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-100">
                Canonical Metadata
              </p>
              <dl className="mt-3 space-y-2 text-sm text-slate-200">
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-cyan-100/70">Publisher</dt>
                  <dd className="text-right">{displayMetadataValue(item.canonical_publisher)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-cyan-100/70">Title</dt>
                  <dd className="text-right">{displayMetadataValue(item.canonical_title)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-cyan-100/70">Release Year</dt>
                  <dd className="text-right">
                    {item.parsed_release_year ? String(item.parsed_release_year) : "Not parsed"}
                  </dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-cyan-100/70">Exact Release Date</dt>
                  <dd className="text-right">{displayMetadataValue(item.parsed_release_date)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-cyan-100/70">Issue</dt>
                  <dd className="text-right">{displayMetadataValue(item.canonical_issue_number)}</dd>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-cyan-100/70">Variant</dt>
                  <dd className="text-right">{displayMetadataValue(item.canonical_variant_text)}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="rounded-2xl border border-fuchsia-400/25 bg-fuchsia-950/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-fuchsia-100">Creator Slots</p>
            <dl className="mt-3 space-y-3 text-sm text-slate-200">
              {(["writers", "artists", "cover_artists"] as const).map((role) => (
                <div key={role} className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
                  <dt className="shrink-0 text-fuchsia-100/75">{CREATOR_ROLE_LABELS[role]}</dt>
                  <dd className="text-right font-mono text-xs text-fuchsia-50/95 sm:text-right">
                    {formatCreatorBullets(
                      zipCreatorSlots(item, role).map(({ raw, canonical }) => ({
                        raw,
                        canonical,
                      })),
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Metadata Identity Key
            </p>
            <p className="mt-2 break-all font-mono text-xs text-slate-200">
              {item.metadata_identity_key ?? "Unavailable"}
            </p>
          </div>

          {summary.humanizedNotes.length ? (
            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Normalized warnings
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                {summary.humanizedNotes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </details>
    </article>
  );
}
