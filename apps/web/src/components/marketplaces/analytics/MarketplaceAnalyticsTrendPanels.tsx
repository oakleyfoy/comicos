import type { MarketplacePerformanceTrendResponse } from "../../../api/client";
import { MarketplaceAnalyticsStatusBadge } from "./MarketplaceAnalyticsStatusBadge";

export function MarketplaceAnalyticsTrendPanels({
  trends,
}: {
  trends: MarketplacePerformanceTrendResponse[];
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Trend engine</p>
          <h2 className="mt-1 text-base font-semibold text-white">Marketplace trend panels</h2>
        </div>
        <p className="text-sm text-slate-400">{trends.length} visible</p>
      </div>
      {trends.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">Generate trends to populate the analytics trend engine.</p>
      ) : (
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {trends.map((trend) => (
            <article key={trend.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{trend.trend_key}</p>
                  <p className="mt-2 break-words text-lg font-semibold text-white">{JSON.stringify(trend.trend_payload_json)}</p>
                </div>
                <MarketplaceAnalyticsStatusBadge status="trend" />
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
