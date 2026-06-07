import { Link, useLocation } from "react-router-dom";

import type { DashboardLoadProfile } from "../lib/dashboardLoadProfile";

const PORTFOLIO_WORKSPACE_TABS = [
  { label: "Holdings", to: "/dashboard" },
  { label: "Insights", to: "/dashboard/collection" },
  { label: "Gaps", to: "/collection-gaps" },
  { label: "Performance", to: "/portfolio-analytics" },
] as const;

function isTabActive(pathname: string, to: string, activeProfile: DashboardLoadProfile): boolean {
  if (to === "/dashboard") {
    return pathname === "/dashboard" && activeProfile === "portfolio";
  }
  if (to === "/dashboard/collection") {
    return pathname === "/dashboard/collection" || activeProfile === "collection";
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function DashboardProfileTabs({ activeProfile }: { activeProfile: DashboardLoadProfile }): JSX.Element {
  const location = useLocation();

  return (
    <nav
      aria-label="Portfolio views"
      className="mt-4 inline-flex max-w-full flex-wrap gap-1 rounded-xl border border-blue-200 bg-white p-1 shadow-sm"
    >
      {PORTFOLIO_WORKSPACE_TABS.map((item) => {
        const active = isTabActive(location.pathname, item.to, activeProfile);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
              active
                ? "bg-patriot-blue text-white shadow-sm"
                : "text-slate-600 hover:bg-blue-50 hover:text-patriot-navy"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
      {activeProfile === "market" || activeProfile === "grading" || activeProfile === "dealer" ? (
        <span className="rounded-lg px-2.5 py-2 text-xs font-medium text-slate-500">
          {activeProfile === "market" ? "Market & FMV view" : `${activeProfile} view`}
        </span>
      ) : null}
      <Link
        to="/dashboard/full"
        className={`ml-auto rounded-lg px-2.5 py-2 text-xs font-medium transition ${
          activeProfile === "full"
            ? "bg-slate-200 text-slate-800"
            : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        }`}
      >
        Full workspace
      </Link>
    </nav>
  );
}
