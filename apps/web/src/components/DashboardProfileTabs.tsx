import { Link, useLocation } from "react-router-dom";

import { DASHBOARD_HUB_LINKS, type DashboardLoadProfile } from "../lib/dashboardLoadProfile";

export function DashboardProfileTabs({ activeProfile }: { activeProfile: DashboardLoadProfile }): JSX.Element {
  const location = useLocation();

  return (
    <nav
      aria-label="Dashboard views"
      className="mt-4 inline-flex max-w-full flex-wrap gap-1 rounded-xl border border-blue-200 bg-white p-1 shadow-sm"
    >
      {DASHBOARD_HUB_LINKS.filter((item) => item.profile !== "full").map((item) => {
        const active = item.profile === activeProfile || location.pathname === item.to;
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
      <Link
        to="/dashboard/full"
        className={`rounded-lg px-2.5 py-2 text-xs font-medium transition ${
          activeProfile === "full"
            ? "bg-slate-200 text-slate-800"
            : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        }`}
      >
        Full
      </Link>
    </nav>
  );
}
