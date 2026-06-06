import type { P80MobileScanResultRead } from "../../../api/client";

function confidenceClass(level: string): string {
  if (level === "HIGH") return "bg-emerald-500/15 text-emerald-200 border-emerald-400/30";
  if (level === "MEDIUM") return "bg-amber-500/15 text-amber-100 border-amber-400/30";
  return "bg-rose-500/15 text-rose-100 border-rose-400/30";
}

export function MobileScanResultPanel({ result }: { result: P80MobileScanResultRead }): JSX.Element {
  const intel = result.book_intelligence;
  const book = result.identification.book;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${confidenceClass(result.identification.confidence)}`}>
          {result.identification.confidence} confidence
        </span>
        {result.identification.requires_manual_review ? (
          <span className="text-xs text-amber-200">Manual review recommended</span>
        ) : null}
      </div>

      {book ? (
        <section className="rounded-2xl border border-slate-700/80 bg-slate-900/60 p-4">
          <h2 className="text-lg font-semibold text-white">{book.title}</h2>
          <p className="mt-1 text-sm text-slate-300">
            {book.series_name}
            {book.issue_number ? ` #${book.issue_number}` : ""}
          </p>
          {book.variant_description ? <p className="text-sm text-slate-400">{book.variant_description}</p> : null}
          {book.publisher ? <p className="text-xs text-slate-500">{book.publisher}</p> : null}
        </section>
      ) : null}

      {intel ? (
        <>
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Owned</p>
              <p className="text-lg font-semibold text-white">{intel.ownership.owned ? "Yes" : "No"}</p>
            </div>
            <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Copies</p>
              <p className="text-lg font-semibold text-white">{intel.ownership.total_copies}</p>
            </div>
            <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">FMV</p>
              <p className="text-lg font-semibold text-white">
                {intel.fmv.authoritative_fmv != null ? `$${intel.fmv.authoritative_fmv.toFixed(2)}` : "—"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Liquidity</p>
              <p className="text-lg font-semibold text-white">{intel.fmv.liquidity_rating ?? "—"}</p>
            </div>
          </section>

          <section className="rounded-2xl border border-violet-500/30 bg-violet-950/30 p-4">
            <p className="text-[10px] uppercase tracking-wider text-violet-300">Primary action</p>
            <p className="mt-1 text-2xl font-bold text-white">{intel.action_card.action}</p>
            <ul className="mt-3 space-y-1 text-sm text-violet-100/90">
              {intel.action_card.reasons.map((reason) => (
                <li key={reason}>• {reason}</li>
              ))}
            </ul>
          </section>

          <section className="rounded-2xl border border-slate-700/80 bg-slate-900/40 p-4 text-sm text-slate-300">
            <p>
              <span className="text-slate-500">Recommendation:</span> {intel.recommendation.recommendation ?? "—"}
            </p>
            <p className="mt-2">
              <span className="text-slate-500">Grading:</span> {intel.grading.grade_recommendation ?? "—"}
              {intel.grading.expected_grade ? ` (expected ${intel.grading.expected_grade})` : ""}
            </p>
            <p className="mt-2">
              <span className="text-slate-500">Storage:</span>{" "}
              {intel.storage.locations.length
                ? intel.storage.locations.map((loc) => loc.location_path_text).join("; ")
                : "Not assigned"}
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
