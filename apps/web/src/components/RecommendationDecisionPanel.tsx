import type { RecommendationDecisionRead, SignalMatrixRead } from "../api/client";
import { PrintingBadge } from "./PrintingBadge";
import { formatCalendarDate } from "../utils/formatCalendarDate";

function strategyLabel(strategy: string): string {
  return strategy.replace(/_/g, " ");
}

type Props = {
  decision: RecommendationDecisionRead;
  compact?: boolean;
};

function SignalChart({
  matrix,
  abbreviations,
}: {
  matrix: SignalMatrixRead;
  abbreviations: RecommendationDecisionRead["signal_abbreviations"];
}): JSX.Element {
  const defs = abbreviations?.length
    ? abbreviations
    : [
        { key: "milestone_issue" as const, label: "MS", description: "" },
        { key: "franchise_strength" as const, label: "FR", description: "" },
        { key: "ratio_variant_opportunity" as const, label: "VAR", description: "" },
        { key: "market_heat" as const, label: "HOT", description: "" },
        { key: "foc_window" as const, label: "FOC", description: "" },
      ];

  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide text-white/70">Signals</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {defs.map((def) => {
          const active = matrix[def.key];
          return (
            <span
              key={def.key}
              title={def.description || def.key}
              className={
                active
                  ? "inline-flex min-w-[2.25rem] justify-center rounded-md border border-emerald-500/50 bg-emerald-950/60 px-1.5 py-0.5 text-[10px] font-bold text-emerald-100"
                  : "inline-flex min-w-[2.25rem] justify-center rounded-md border border-white/15 bg-slate-900/80 px-1.5 py-0.5 text-[10px] font-medium text-white/35"
              }
            >
              {active ? "✓" : "·"} {def.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export function RecommendationDecisionPanel({ decision, compact = false }: Props): JSX.Element {
  const foc = formatCalendarDate(decision.foc_date);
  const release = formatCalendarDate(decision.release_date);
  const printFoc = formatCalendarDate(decision.printing_foc_date);
  const printRelease = formatCalendarDate(decision.printing_release_date);
  const isPurchase = decision.action === "BUY" || decision.action === "BUY_AGGRESSIVE";
  const filteredPlan = decision.cover_purchase_plan?.filter((row) => row.recommended_quantity > 0) ?? [];
  const plan =
    filteredPlan.length > 0
      ? filteredPlan
      : isPurchase && decision.quantity > 0
        ? decision.cover_recommendations.map((label) => ({
            cover_label: label,
            recommended_quantity: 1,
            reason_codes: [] as string[],
            reason_summary: "",
          }))
        : [];

  const metricsBlock = (
    <>
      <p className="text-white/90">
        Risk: <span className="font-medium text-white">{decision.risk}</span>
      </p>
      <p className="text-white/90">
        Strategy: <span className="font-medium text-white">{strategyLabel(decision.strategy)}</span>
      </p>
      {decision.strategy_allocation_hint ? (
        <p className="text-cyan-100/95">{decision.strategy_allocation_hint}</p>
      ) : null}
      <p className="text-white/85">
        Expected ROI: <span className="text-white">{decision.expected_roi_range}</span>
      </p>
      {decision.quantity_reasoning && decision.quantity > 2 ? (
        <div className="text-xs text-white/80">
          <p>
            Qty base {decision.quantity_reasoning.base_quantity}
            {decision.quantity_reasoning.adjustments.map((adj) => (
              <span key={adj.reason_code}>
                {" "}
                +{adj.delta} {adj.label}
              </span>
            ))}{" "}
            = {decision.quantity_reasoning.final_quantity}
          </p>
        </div>
      ) : null}
      {(foc || release || printFoc || printRelease || decision.printing_badge) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-white/80">
          <PrintingBadge badge={decision.printing_badge} />
          {foc ? (
            <span>
              Original FOC: <span className="text-white">{foc}</span>
            </span>
          ) : null}
          {release ? (
            <span>
              Original release: <span className="text-white">{release}</span>
            </span>
          ) : null}
          {printFoc ? (
            <span>
              Printing FOC: <span className="text-white">{printFoc}</span>
            </span>
          ) : null}
          {printRelease ? (
            <span>
              Printing release: <span className="text-white">{printRelease}</span>
            </span>
          ) : null}
        </div>
      )}
    </>
  );

  const buyPlanBlock = (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide text-white/70">Buy plan</p>
      {isPurchase && plan.length > 0 ? (
        <ul className="mt-1 space-y-0.5 font-mono text-sm text-white">
          {plan.map((row) => (
            <li key={row.cover_label}>
              {row.cover_label} ×{row.recommended_quantity}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-sm text-white/80">Monitor — no purchase allocation.</p>
      )}
    </div>
  );

  const topReasons = decision.top_reasons?.length
    ? decision.top_reasons
    : decision.reason_summary.slice(0, 5);

  const whyBlock =
    topReasons.length > 0 ? (
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-white/70">Why this matters</p>
        <ul className="mt-1 list-inside list-disc space-y-0.5 text-white/95">
          {topReasons.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>
    ) : null;

  const scoreBlock =
    decision.score_breakdown && decision.score_breakdown.length > 0 ? (
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-white/70">Score</p>
        <table className="mt-1 w-full text-left text-xs text-white/90">
          <tbody>
            {decision.score_breakdown.map((row) => (
              <tr key={row.label}>
                <td className="py-0.5 pr-2">{row.label}</td>
                <td className="py-0.5 text-right tabular-nums">
                  {row.not_available ? "—" : `${row.points} / ${row.max_points}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : null;

  const signalBlock =
    decision.signal_matrix && decision.signal_abbreviations ? (
      <SignalChart matrix={decision.signal_matrix} abbreviations={decision.signal_abbreviations} />
    ) : null;

  return (
    <div
      className={
        compact
          ? "mt-2 space-y-2 rounded-xl border border-cyan-500/30 bg-slate-800 px-3 py-2 text-xs text-white"
          : "mt-3 rounded-xl border border-cyan-500/30 bg-slate-800 px-4 py-3 text-sm text-white"
      }
    >
      <p className={compact ? "text-sm font-semibold text-cyan-100" : "text-lg font-semibold tracking-wide text-cyan-100"}>
        Action: {decision.decision_headline}
      </p>

      {compact ? (
        <div className="space-y-2">
          {buyPlanBlock}
          {metricsBlock}
          {whyBlock}
        </div>
      ) : (
        <>
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              {buyPlanBlock}
              {metricsBlock}
            </div>
            <div className="space-y-3">
              {signalBlock}
              {scoreBlock}
            </div>
          </div>
          {whyBlock ? <div className="mt-3">{whyBlock}</div> : null}
        </>
      )}
    </div>
  );
}
