import type { MobileOpsMetricResponse } from "../../../api/client";

function formatMetricValue(metric: MobileOpsMetricResponse): string {
  if (typeof metric.metric_value_json["count"] === "number") {
    return String(metric.metric_value_json["count"]);
  }
  if (typeof metric.metric_value_json["amount"] === "string") {
    const currency = typeof metric.metric_value_json["currency"] === "string" ? metric.metric_value_json["currency"] : "USD";
    return `${currency} ${metric.metric_value_json["amount"]}`;
  }
  if (typeof metric.metric_value_json["status"] === "string") {
    return String(metric.metric_value_json["status"]);
  }
  return "n/a";
}

export function MobileOpsMetricCards({ metrics }: { metrics: MobileOpsMetricResponse[] }): JSX.Element {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div key={metric.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{metric.metric_key.replace(/_/g, " ")}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{formatMetricValue(metric)}</p>
          <p className="mt-1 text-xs text-slate-500">{metric.metric_period}</p>
        </div>
      ))}
    </div>
  );
}
