import { Link, useLocation } from "react-router-dom";



import { DASHBOARD_HUB_LINKS, type DashboardLoadProfile } from "../lib/dashboardLoadProfile";



export function DashboardProfileTabs({ activeProfile }: { activeProfile: DashboardLoadProfile }): JSX.Element {

  const location = useLocation();



  return (

    <nav

      aria-label="Dashboard views"

      className="mt-4 inline-flex max-w-full flex-wrap gap-1 rounded-2xl border border-white/10 bg-slate-950/50 p-1"

    >

      {DASHBOARD_HUB_LINKS.filter((item) => item.profile !== "full").map((item) => {

        const active = item.profile === activeProfile || location.pathname === item.to;

        return (

          <Link

            key={item.to}

            to={item.to}

            className={`rounded-xl px-3 py-2 text-sm font-medium transition ${

              active

                ? "bg-cyan-400/20 text-cyan-50 shadow-sm"

                : "text-slate-400 hover:bg-white/5 hover:text-slate-100"

            }`}

          >

            {item.label}

          </Link>

        );

      })}

      <Link

        to="/dashboard/full"

        className={`rounded-xl px-2.5 py-2 text-xs font-medium transition ${

          activeProfile === "full"

            ? "bg-white/10 text-slate-200"

            : "text-slate-600 hover:bg-white/5 hover:text-slate-400"

        }`}

      >

        Full

      </Link>

    </nav>

  );

}

