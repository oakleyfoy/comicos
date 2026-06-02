import { Link, useLocation } from "react-router-dom";

import { DASHBOARD_HUB_LINKS, type DashboardLoadProfile } from "../lib/dashboardLoadProfile";

export function DashboardHubNav({ activeProfile }: { activeProfile: DashboardLoadProfile }): JSX.Element {
  const location = useLocation();

  return (
    <nav
      aria-label="Dashboard views"
      className="mt-6 rounded-3xl border border-cyan-400/20 bg-cyan-950/15 p-4 shadow-xl shadow-black/15"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200/80">Dashboard views</p>
      <p className="mt-1 max-w-3xl text-sm text-slate-400">
        Each view loads only its APIs so the app stays responsive. Use portfolio for daily inventory work.
      </p>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {DASHBOARD_HUB_LINKS.map((item) => {
          const active = item.profile === activeProfile || location.pathname === item.to;
          return (
            <li key={item.to}>
              <Link
                to={item.to}
                className={`block rounded-2xl border px-4 py-3 transition ${
                  active
                    ? "border-cyan-400/50 bg-cyan-400/15 text-white"
                    : "border-white/10 bg-slate-950/40 text-slate-200 hover:border-cyan-300/35 hover:bg-white/5"
                }`}
              >
                <span className="text-sm font-semibold">{item.label}</span>
                <span className="mt-1 block text-xs text-slate-400">{item.blurb}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
