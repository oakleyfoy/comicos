import type { MarketplaceMetricResponse } from "../../../api/client";

export function MarketplaceAnalyticsMetricTable({
  metrics,
}: {
  metrics: MarketplaceMetricResponse[];
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Metric table</p>
      <h2 className="mt-1 text-base font-semibold text-white">Marketplace analytics metrics</h2>
      {metrics.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">Generate metrics to populate the analytics metric table.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-slate-950/80 text-slate-400">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Key</th>
                <th className="px-4 py-3 text-left font-medium">Period</th>
                <th className="px-4 py-3 text-left font-medium">Value</th>
                <th className="px-4 py-3 text-left font-medium">Generated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10 bg-slate-950/45 text-slate-200">
              {metrics.map((metric) => (
                <tr key={metric.id}>
                  <td className="px-4 py-3 font-medium text-white">{metric.metric_key}</td>
                  <td className="px-4 py-3">{metric.metric_period}</td>
                  <td className="px-4 py-3">
                    <pre className="whitespace-pre-wrap break-words text-xs text-slate-300">{JSON.stringify(metric.metric_value_json)}</pre>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{metric.generated_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
