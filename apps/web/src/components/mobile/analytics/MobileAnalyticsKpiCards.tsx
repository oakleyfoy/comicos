import type { MobileUsageMetricResponse } from "../../../api/client";

function formatMetricValue(metric: MobileUsageMetricResponse): string {
  if ("amount" in metric.metric_value_json) {
    return `${metric.metric_value_json["amount"] ?? "0.00"} ${metric.metric_value_json["currency"] ?? "USD"}`.trim();
  }
  if ("rate" in metric.metric_value_json) {
    return `${metric.metric_value_json["rate"] ?? "0.00"}%`;
  }
  if ("count" in metric.metric_value_json) {
    return String(metric.metric_value_json["count"] ?? 0);
  }
  return JSON.stringify(metric.metric_value_json);
}

const FEATURED_KPIS = [
  "registered_devices",
  "active_sessions",
  "successful_lookup_rate",
  "completed_quick_sales",
  "average_quick_sale_value",
  "denied_mobile_access_attempts",
];

export function MobileAnalyticsKpiCards({ metrics }: { metrics: MobileUsageMetricResponse[] }): JSX.Element {
  const featured = metrics.filter((metric) => FEATURED_KPIS.includes(metric.metric_key));

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {featured.map((metric) => (
        <div key={metric.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{metric.metric_key.replace(/_/g, " ")}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{formatMetricValue(metric)}</p>
          <p className="mt-1 text-xs text-slate-500">{metric.metric_period}</p>
        </div>
      ))}
    </div>
  );
}
