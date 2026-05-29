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

export function MobileAnalyticsMetricTable({ metrics }: { metrics: MobileUsageMetricResponse[] }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <h2 className="text-lg font-semibold text-white">Usage metrics</h2>
        <p className="mt-1 text-sm text-slate-400">Deterministic KPI rows from the centralized mobile analytics registry.</p>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm text-slate-300">
          <thead className="text-xs uppercase tracking-[0.16em] text-slate-500">
            <tr>
              <th className="pb-3 pr-4 font-medium">Metric</th>
              <th className="pb-3 pr-4 font-medium">Value</th>
              <th className="pb-3 pr-4 font-medium">Period</th>
              <th className="pb-3 font-medium">Generated</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={metric.id} className="border-t border-white/5">
                <td className="py-3 pr-4 font-medium text-white">{metric.metric_key}</td>
                <td className="py-3 pr-4">{formatMetricValue(metric)}</td>
                <td className="py-3 pr-4">{metric.metric_period}</td>
                <td className="py-3">{new Date(metric.generated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
