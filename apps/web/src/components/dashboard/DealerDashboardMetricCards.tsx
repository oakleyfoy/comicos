import type { OrganizationDealerDashboardSectionSummary } from "../../api/client";
import { formatMetricValue, metricLabel, sectionLabel } from "./dealerDashboardLabels";

type Props = {
  sections: OrganizationDealerDashboardSectionSummary[];
};

export function DealerDashboardMetricCards({ sections }: Props): JSX.Element {
  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {sections.map((section) => (
        <div key={section.section_key} className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{sectionLabel(section.section_key)}</p>
          <div className="mt-4 space-y-3">
            {Object.entries(section.metrics)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([metricKey, value]) => (
                <div key={metricKey} className="flex items-baseline justify-between gap-3">
                  <p className="text-sm text-slate-300">{metricLabel(metricKey)}</p>
                  <p className="text-lg font-semibold tabular-nums text-white">{formatMetricValue(value)}</p>
                </div>
              ))}
          </div>
        </div>
      ))}
    </section>
  );
}
