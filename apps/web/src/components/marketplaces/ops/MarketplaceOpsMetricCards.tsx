import type { MarketplaceOpsMetricResponse } from "../../../api/client";
import { MarketplaceOpsStatusBadge } from "./MarketplaceOpsStatusBadge";

export function MarketplaceOpsMetricCards({
  metrics,
  summary,
}: {
  metrics: MarketplaceOpsMetricResponse[];
  summary: Record<string, unknown>;
}): JSX.Element {
  const accountsSummary = (summary["accounts"] ?? {}) as Record<string, unknown>;
  const listingsSummary = (summary["listings"] ?? {}) as Record<string, unknown>;
  const syncSummary = (summary["sync"] ?? {}) as Record<string, unknown>;
  const ordersSummary = (summary["orders"] ?? {}) as Record<string, unknown>;
  const pricingSummary = (summary["pricing"] ?? {}) as Record<string, unknown>;
  const eventsSummary = (summary["events"] ?? {}) as Record<string, unknown>;
  const liveSalesSummary = (summary["live_sales"] ?? {}) as Record<string, unknown>;
  const fallbackCards = [
    { label: "Connected accounts", value: String((accountsSummary.connected ?? 0) as number) },
    { label: "Ready listings", value: String((listingsSummary.ready ?? 0) as number) },
    { label: "Open sync conflicts", value: String((syncSummary.open_conflicts ?? 0) as number) },
    { label: "Imported orders", value: String((ordersSummary.imported ?? 0) as number) },
    { label: "Pending recommendations", value: String((pricingSummary.pending_recommendations ?? 0) as number) },
    { label: "Unprocessed events", value: String((eventsSummary.unprocessed_events ?? 0) as number) },
    { label: "Live-sale sessions", value: String((liveSalesSummary.active_sessions ?? 0) as number) },
  ];

  const renderedMetrics =
    metrics.length > 0
      ? metrics.map((metric) => ({
          label: metric.metric_key.split("_").join(" "),
          value: JSON.stringify(metric.metric_value_json),
          status: metric.metric_period,
        }))
      : fallbackCards.map((card) => ({ ...card, status: "summary" }));

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Metrics</p>
          <h2 className="mt-1 text-base font-semibold text-white">Marketplace metric cards</h2>
        </div>
        <p className="text-sm text-slate-400">{renderedMetrics.length} visible</p>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {renderedMetrics.map((metric) => (
          <article key={`${metric.label}-${metric.value}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{metric.label}</p>
                <p className="mt-2 break-words text-lg font-semibold text-white">{metric.value}</p>
              </div>
              <MarketplaceOpsStatusBadge status={metric.status} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
