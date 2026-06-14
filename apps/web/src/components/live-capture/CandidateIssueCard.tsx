import type { RecognitionCatalogCandidateRead } from "../../api/client";

interface CandidateIssueCardProps {
  candidate: RecognitionCatalogCandidateRead;
  selected?: boolean;
  onSelect?: (candidate: RecognitionCatalogCandidateRead) => void;
}

function friendlySource(source: string | undefined): string | null {
  switch (source) {
    case "catalog_image_fingerprint":
      return "Matched by cover image";
    case "catalog_nearby":
      return "Same series";
    case "catalog_search":
      return "Catalog search";
    case "user_correction":
      return "Your correction";
    default:
      return source ? source.replace(/_/g, " ") : null;
  }
}

export function CandidateIssueCard({ candidate, selected = false, onSelect }: CandidateIssueCardProps): JSX.Element {
  const confidenceLabel = candidate.confidence > 0 ? `${Math.round(candidate.confidence * 100)}%` : null;
  const sourceLabel = friendlySource(candidate.source);
  return (
    <button
      type="button"
      data-testid={`candidate-card-${candidate.catalog_issue_id}`}
      aria-pressed={selected}
      onClick={() => onSelect?.(candidate)}
      className={`flex w-full flex-col gap-2 rounded-2xl border p-3 text-left transition ${
        selected
          ? "border-emerald-400 bg-emerald-500/10 ring-2 ring-emerald-400"
          : "border-slate-700 bg-slate-950/60 hover:border-slate-500"
      }`}
    >
      <div className="aspect-[2/3] w-full overflow-hidden rounded-xl bg-slate-800">
        {candidate.cover_image_url ? (
          <img
            src={candidate.cover_image_url}
            alt={`${candidate.series} #${candidate.issue_number}`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">No cover</div>
        )}
      </div>
      <div>
        <p className="text-sm font-semibold text-white">
          {candidate.series} #{candidate.issue_number}
        </p>
        <p className="text-xs text-slate-400">{candidate.publisher ?? "Unknown publisher"}</p>
        {confidenceLabel || sourceLabel ? (
          <p className="mt-1 text-[11px] text-slate-500">
            {confidenceLabel ? `${confidenceLabel}` : null}
            {confidenceLabel && sourceLabel ? " · " : null}
            {sourceLabel}
          </p>
        ) : null}
      </div>
    </button>
  );
}
