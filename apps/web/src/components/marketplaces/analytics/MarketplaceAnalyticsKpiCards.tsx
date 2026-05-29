import type { MarketplaceMetricResponse } from "../../../api/client";
import { MarketplaceAnalyticsStatusBadge } from "./MarketplaceAnalyticsStatusBadge";

export function MarketplaceAnalyticsKpiCards({
  metrics,
  summary,
}: {
  metrics: MarketplaceMetricResponse[];
  summary: Record<string, unknown>;
}): JSX.Element {
  const sections = [
    ["accounts", "Accounts"],
    ["listings", "Listings"],
    ["orders", "Orders"],
    ["transactions", "Transactions"],
    ["pricing", "Pricing"],
    ["events", "Events"],
    ["live_sales", "Live sales"],
    ["shopify", "Shopify"],
  ] as const;

  const cards =
    metrics.length > 0
      ? metrics.map((metric) => ({
          label: metric.metric_key.split("_").join(" "),
          value: JSON.stringify(metric.metric_value_json),
          status: metric.metric_period,
        }))
      : sections.map(([key, label]) => ({
          label,
          value: JSON.stringify(summary[key] ?? {}),
          status: "summary",
        }));

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">KPI registry</p>
          <h2 className="mt-1 text-base font-semibold text-white">Marketplace KPI cards</h2>
        </div>
        <p className="text-sm text-slate-400">{cards.length} visible</p>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <article key={`${card.label}-${card.value}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{card.label}</p>
                <p className="mt-2 break-words text-lg font-semibold text-white">{card.value}</p>
              </div>
              <MarketplaceAnalyticsStatusBadge status={card.status} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
