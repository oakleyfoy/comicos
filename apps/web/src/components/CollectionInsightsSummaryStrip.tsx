import type { CollectionAnalyticsSummary } from "../api/client";

import { LoadingState } from "./LoadingState";

function Stat({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="flex flex-col gap-0.5 border-l border-blue-200 pl-4 first:border-l-0 first:pl-0">
      <p className="text-[11px] font-medium text-slate-500">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-patriot-navy">{value}</p>
    </div>
  );
}

export function CollectionInsightsSummaryStrip(props: {
  loading: boolean;
  summary: CollectionAnalyticsSummary | null;
  error: string | null;
}): JSX.Element | null {
  const { loading, summary, error } = props;

  if (error) {
    return (
      <section className="mt-5 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
        {error}
      </section>
    );
  }

  if (loading && !summary) {
    return (
      <div className="mt-5">
        <LoadingState
          title="Loading collection analytics"
          description="Coverage, scan backlog, and ownership mix for your library."
        />
      </div>
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <section
      className="mt-5 rounded-xl border border-blue-200 bg-white px-5 py-4 shadow-sm"
      aria-label="Collection snapshot"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-patriot-navy">Collection snapshot</h2>
        <p className="text-xs text-slate-500">As of {summary.generated_as_of_date}</p>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total copies" value={summary.total_copies} />
        <Stat label="In hand" value={summary.in_hand_copies} />
        <Stat label="Preordered" value={summary.preorder_copies} />
        <Stat label="Graded / raw" value={`${summary.graded_copies} / ${summary.raw_copies}`} />
        <Stat label="Unscanned" value={summary.unscanned_primary_copies} />
        <Stat label="Needs review" value={summary.unresolved_review_copies} />
        <Stat label="Canonical linked" value={summary.canonical_linked_copies} />
        <Stat label="Not in hand" value={Math.max(0, summary.total_copies - summary.in_hand_copies)} />
      </div>
    </section>
  );
}
