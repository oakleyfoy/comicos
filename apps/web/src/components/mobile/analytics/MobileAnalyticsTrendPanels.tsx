import type { MobileUsageTrendResponse } from "../../../api/client";

export function MobileAnalyticsTrendPanels({ trends }: { trends: MobileUsageTrendResponse[] }): JSX.Element {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {trends.map((trend) => {
        const points = Array.isArray(trend.trend_payload_json["points"])
          ? (trend.trend_payload_json["points"] as Array<Record<string, unknown>>)
          : [];
        return (
          <section key={trend.id} className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-white">{trend.trend_key.replace(/_/g, " ")}</h2>
                <p className="mt-1 text-sm text-slate-400">{String(trend.trend_payload_json["group"] ?? trend.trend_period)}</p>
              </div>
              <p className="text-xs text-slate-500">{new Date(trend.generated_at).toLocaleString()}</p>
            </div>
            <div className="mt-4 space-y-3">
              {points.map((point) => (
                <div key={String(point["label"])} className="flex items-center justify-between gap-3 rounded-2xl border border-white/5 bg-slate-950/45 px-3 py-2">
                  <span className="text-sm text-slate-400">{String(point["label"]).replace(/_/g, " ")}</span>
                  <span className="text-sm font-semibold text-white">{String(point["value"] ?? "0")}</span>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
