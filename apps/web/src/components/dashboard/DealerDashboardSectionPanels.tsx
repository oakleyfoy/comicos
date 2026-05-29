import { Link } from "react-router-dom";

import type { OrganizationDealerDashboardSectionSummary } from "../../api/client";
import { formatMetricValue, metricLabel, sectionLabel } from "./dealerDashboardLabels";

type Props = {
  organizationId: number;
  sections: OrganizationDealerDashboardSectionSummary[];
};

function sectionLinks(organizationId: number, sectionKey: string): { label: string; to: string } | null {
  switch (sectionKey) {
    case "inventory":
      return { label: "Shared inventory", to: `/organizations/${organizationId}/inventory` };
    case "reviews":
      return { label: "Team reviews", to: `/organizations/${organizationId}/reviews` };
    case "activity":
      return { label: "Activity feed", to: `/organizations/${organizationId}/activity` };
    case "storefront":
      return { label: "Storefront settings", to: `/organizations/${organizationId}/storefront` };
    default:
      return null;
  }
}

export function DealerDashboardSectionPanels({ organizationId, sections }: Props): JSX.Element {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {sections.map((section) => {
        const link = sectionLinks(organizationId, section.section_key);
        return (
          <section key={section.section_key} className="rounded-3xl border border-white/10 bg-slate-950/35 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-200/70">Operational summary</p>
                <h3 className="mt-1 text-base font-semibold text-white">{sectionLabel(section.section_key)}</h3>
              </div>
              {link ? (
                <Link to={link.to} className="text-xs font-semibold text-cyan-200 hover:text-cyan-100">
                  {link.label} →
                </Link>
              ) : null}
            </div>
            <dl className="mt-4 grid gap-2">
              {Object.entries(section.metrics)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([metricKey, value]) => (
                  <div key={metricKey} className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-slate-900/50 px-3 py-2">
                    <dt className="text-sm text-slate-400">{metricLabel(metricKey)}</dt>
                    <dd className="text-sm font-semibold tabular-nums text-white">{formatMetricValue(value)}</dd>
                  </div>
                ))}
            </dl>
          </section>
        );
      })}
    </div>
  );
}
