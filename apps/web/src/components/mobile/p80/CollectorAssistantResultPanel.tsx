import type { P80CollectorScanResultRead } from "../../../api/client";

function actionTone(action: string): string {
  if (action === "BUY") return "border-emerald-400/40 bg-emerald-950/50 text-emerald-100";
  if (action === "PASS") return "border-rose-400/40 bg-rose-950/50 text-rose-100";
  if (action === "GRADE") return "border-amber-400/40 bg-amber-950/50 text-amber-100";
  return "border-violet-400/40 bg-violet-950/50 text-violet-100";
}

export function CollectorAssistantResultPanel({ result }: { result: P80CollectorScanResultRead }): JSX.Element {
  const intel = result.book_intelligence;
  const book = result.identification.book;

  return (
    <div className="space-y-4">
      {book ? (
        <section className="rounded-2xl border border-slate-700/80 bg-slate-900/60 p-4">
          <h2 className="text-lg font-semibold text-white">{book.title}</h2>
          <p className="mt-1 text-sm text-slate-300">
            {book.series_name}
            {book.issue_number ? ` #${book.issue_number}` : ""}
          </p>
        </section>
      ) : null}

      <section className={`rounded-2xl border p-4 ${actionTone(result.action_card.action)}`}>
        <p className="text-[10px] uppercase tracking-wider opacity-80">Collector action</p>
        <p className="mt-1 text-3xl font-bold">{result.action_card.action}</p>
        <ul className="mt-3 space-y-1 text-sm">
          {result.action_card.reasons.map((reason) => (
            <li key={reason}>• {reason}</li>
          ))}
        </ul>
      </section>

      {result.personalization ? (
        <section className="rounded-2xl border border-sky-500/30 bg-sky-950/20 p-4 text-sm text-sky-100">
          <p className="text-[10px] uppercase tracking-wider text-sky-300">P77 personalized score</p>
          <p className="mt-1 text-lg font-semibold">
            {result.personalization.personalized_score != null
              ? result.personalization.personalized_score.toFixed(0)
              : "—"}
            {result.personalization.global_score != null ? (
              <span className="ml-2 text-sm font-normal text-sky-200/80">
                (global {result.personalization.global_score.toFixed(0)})
              </span>
            ) : null}
          </p>
          <p className="mt-1 text-xs text-sky-200/70">
            Budget {result.personalization.budget_state ?? "GREEN"}
            {result.personalization.quantity_recommendation
              ? ` · qty ${result.personalization.quantity_recommendation}`
              : ""}
          </p>
          {result.personalization.reasons.length ? (
            <ul className="mt-2 space-y-1">
              {result.personalization.reasons.slice(0, 4).map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {result.price_assessment ? (
        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4 text-sm">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">Price vs FMV</p>
          <p className="mt-2 text-white">
            Vendor ${result.price_assessment.asking_price.toFixed(2)} · FMV{" "}
            {result.price_assessment.authoritative_fmv != null
              ? `$${result.price_assessment.authoritative_fmv.toFixed(2)}`
              : "—"}
          </p>
          <p className="mt-1 text-slate-300">
            {result.price_assessment.assessment.replace("_", " ")}
            {result.price_assessment.spread_percent != null
              ? ` (${result.price_assessment.spread_percent > 0 ? "+" : ""}${result.price_assessment.spread_percent}%)`
              : ""}
          </p>
        </section>
      ) : null}

      {intel ? (
        <section className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Owned</p>
            <p className="text-lg font-semibold text-white">{intel.ownership.total_copies}</p>
            <p className="text-xs text-slate-400">
              raw {intel.ownership.raw_copies} · graded {intel.ownership.graded_copies}
            </p>
          </div>
          <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">FMV</p>
            <p className="text-lg font-semibold text-white">
              {intel.fmv.authoritative_fmv != null ? `$${intel.fmv.authoritative_fmv.toFixed(0)}` : "—"}
            </p>
            <p className="text-xs text-slate-400">{intel.fmv.liquidity_rating ?? "—"} liquidity</p>
          </div>
        </section>
      ) : null}

      {result.collection_completion ? (
        <section className="rounded-2xl border border-slate-700/80 bg-slate-900/40 p-4 text-sm text-slate-300">
          <p className="font-medium text-white">{result.collection_completion.label}</p>
          <p className="mt-1">
            {result.collection_completion.owned_issue_count} / {result.collection_completion.known_issue_count}
            {result.collection_completion.completion_percent != null
              ? ` (${result.collection_completion.completion_percent}%)`
              : ""}
          </p>
          {result.collection_completion.missing_issue_numbers.length ? (
            <p className="mt-2 text-xs text-slate-400">
              Missing: {result.collection_completion.missing_issue_numbers.slice(0, 6).join(", ")}
            </p>
          ) : null}
        </section>
      ) : null}

      {result.spec_opportunity?.detected ? (
        <section className="rounded-2xl border border-cyan-500/30 bg-cyan-950/20 p-4 text-sm text-cyan-100">
          <p className="text-[10px] uppercase tracking-wider text-cyan-300">Spec opportunity</p>
          <p className="mt-1 text-lg font-semibold">Score {result.spec_opportunity.score ?? "—"}</p>
          <ul className="mt-2 space-y-1">
            {result.spec_opportunity.signals.map((s) => (
              <li key={s}>• {s}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
