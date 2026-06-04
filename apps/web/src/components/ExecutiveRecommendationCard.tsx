import type { ExecutiveDashboardItemRead } from "../api/client";
import { RecommendationDecisionPanel } from "./RecommendationDecisionPanel";

function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

type Props = {
  item: ExecutiveDashboardItemRead;
};

/** Card layout aligned with Top Recommendations (cross-system) page. */
export function ExecutiveRecommendationCard({ item }: Props): JSX.Element {
  const typeLabel = item.recommendation_type || item.action_type || "";
  const rank = item.recommendation_rank;
  const showRecommendationLayout =
    item.section === "TOP_RECOMMENDATIONS" ||
    item.section === "DAILY_ACTIONS" ||
    item.item_type === "cross_system_recommendation" ||
    item.item_type === "daily_action";

  if (!showRecommendationLayout) {
    return <LegacyExecutiveItemBody item={item} />;
  }

  return (
    <div className="text-white">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-wide text-white/75">
            {rank != null ? `#${rank} · ` : ""}
            {typeLabel.replace(/_/g, " ")}
            {item.due_date ? ` · Due ${item.due_date}` : ""}
          </p>
          <h4 className="text-base font-semibold leading-snug text-white">{item.title}</h4>
          {item.publisher ? <p className="text-xs text-white/70">{item.publisher}</p> : null}
        </div>
        <div className="shrink-0 text-right text-xs text-white/90">
          {item.priority_score != null ? <p>Priority {item.priority_score.toFixed(1)}</p> : null}
          {item.confidence_score != null ? <p>Confidence {item.confidence_score.toFixed(2)}</p> : null}
          {item.estimated_value != null ? <p>{money(item.estimated_value)}</p> : null}
        </div>
      </div>
      {item.decision ? (
        <div className="mt-2">
          <RecommendationDecisionPanel decision={item.decision} compact />
        </div>
      ) : null}
      {(item.source_systems.length > 0 || item.rationale) && (
        <div
          className={
            item.source_systems.length > 0 && item.rationale
              ? "mt-3 grid gap-3 sm:grid-cols-2 sm:items-start"
              : "mt-3"
          }
        >
          {item.source_systems.length > 0 ? (
            <p className="text-xs leading-relaxed text-white/90">
              <span className="font-medium text-white">Sources:</span> {item.source_systems.join(", ")}
            </p>
          ) : null}
          {item.rationale ? <p className="text-sm leading-relaxed text-white">{item.rationale}</p> : null}
        </div>
      )}
    </div>
  );
}

function LegacyExecutiveItemBody({ item }: { item: ExecutiveDashboardItemRead }): JSX.Element {
  const badge = item.action_type || item.recommendation_type || item.health_status;
  const parts: string[] = [];
  if (item.publisher) parts.push(item.publisher);
  if (item.recommendation_rank != null) parts.push(`Rank ${item.recommendation_rank}`);
  if (item.priority_score != null) parts.push(`Priority ${item.priority_score.toFixed(1)}`);
  if (item.confidence_score != null) parts.push(`Conf ${item.confidence_score.toFixed(2)}`);
  if (item.due_date) parts.push(`Due ${item.due_date}`);
  if (item.estimated_value != null) parts.push(`Est ${money(item.estimated_value)}`);

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium text-white">{item.title}</span>
        {badge ? (
          <span className="shrink-0 font-medium uppercase tracking-wide text-sky-200">{badge.replace(/_/g, " ")}</span>
        ) : null}
      </div>
      {parts.length > 0 ? <p className="mt-1 text-xs text-white">{parts.join(" · ")}</p> : null}
      {item.source_systems.length > 0 ? (
        <p className="mt-1 text-xs text-white">Sources: {item.source_systems.join(", ")}</p>
      ) : null}
      {item.rationale ? <p className="mt-1 text-xs leading-relaxed text-white">{item.rationale}</p> : null}
    </>
  );
}
