import type { RecommendationDecisionRead } from "../api/client";

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
}

function strategyLabel(strategy: string): string {
  return strategy.replace(/_/g, " ");
}

type Props = {
  decision: RecommendationDecisionRead;
  compact?: boolean;
};

export function RecommendationDecisionPanel({ decision, compact = false }: Props): JSX.Element {
  const foc = formatDate(decision.foc_date);
  const release = formatDate(decision.release_date);
  const primaryCover = decision.cover_recommendations[0];

  return (
    <div
      className={
        compact
          ? "mt-2 space-y-1 rounded-xl border border-cyan-500/20 bg-cyan-950/20 px-3 py-2 text-xs"
          : "mt-3 space-y-2 rounded-xl border border-cyan-500/25 bg-slate-900/80 px-4 py-3 text-sm"
      }
    >
      <p className="text-base font-semibold tracking-wide text-cyan-100">{decision.decision_headline}</p>
      {primaryCover ? (
        <p className="text-cyan-200/90">
          {decision.cover_recommendations.length > 1
            ? decision.cover_recommendations.join(" · ")
            : `${primaryCover}${primaryCover.toLowerCase().includes("recommended") ? "" : " Recommended"}`}
        </p>
      ) : null}
      <p className="text-slate-300">
        Risk: <span className="font-medium text-white">{decision.risk}</span>
      </p>
      <p className="text-slate-300">
        Strategy: <span className="font-medium text-white">{strategyLabel(decision.strategy)}</span>
      </p>
      <p className="text-slate-400">
        Expected ROI: <span className="text-slate-200">{decision.expected_roi_range}</span>
      </p>
      {decision.reason_summary.length > 0 ? (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Reason</p>
          <ul className="mt-1 list-inside list-disc text-slate-300">
            {decision.reason_summary.slice(0, 6).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {(foc || release) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
          {foc ? (
            <span>
              FOC: <span className="text-slate-200">{foc}</span>
            </span>
          ) : null}
          {release ? (
            <span>
              Release: <span className="text-slate-200">{release}</span>
            </span>
          ) : null}
        </div>
      )}
    </div>
  );
}
