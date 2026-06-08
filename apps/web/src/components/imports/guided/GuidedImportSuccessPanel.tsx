import { Link } from "react-router-dom";

import type { GuidedImportSummaryRead } from "../../../api/client";

type Props = {
  booksAdded: number;
  summary: GuidedImportSummaryRead;
};

export function GuidedImportSuccessPanel({ booksAdded, summary }: Props): JSX.Element {
  return (
    <section className="mt-8 space-y-6 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-6" data-testid="guided-import-success">
      <div>
        <p className="text-emerald-300">✅ Import complete</p>
        <h2 className="mt-1 text-2xl font-semibold text-white">{booksAdded} books added</h2>
      </div>
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Added to collection</h3>
        <ul className="mt-2 space-y-1 text-sm text-slate-200">
          <li>Estimated value: ${summary.value_tracked.toFixed(2)}</li>
          <li>Series discovered: {summary.new_series_count}</li>
          <li>Publishers: {summary.publisher_count}</li>
        </ul>
      </div>
      <div>
        <h3 className="text-sm font-semibold text-white">Recommended next actions</h3>
        <ul className="mt-3 space-y-2 text-sm">
          <li>
            <Link className="text-emerald-300 underline" to="/dashboard/collection">
              1. View inventory
            </Link>
          </li>
          <li>
            <Link className="text-emerald-300 underline" to="/pull-lists">
              2. Create pull list
            </Link>
          </li>
          <li>
            <Link className="text-emerald-300 underline" to="/collector-recommendations">
              3. Review recommendations
            </Link>
          </li>
          <li>
            <Link className="text-emerald-300 underline" to="/collector-budget">
              Set buying budget
            </Link>
          </li>
        </ul>
      </div>
      <Link to="/collector-home" className="inline-block rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-950">
        Back to collector home
      </Link>
    </section>
  );
}
