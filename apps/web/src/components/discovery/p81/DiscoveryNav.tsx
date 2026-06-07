import { NavLink } from "react-router-dom";

import { patriotNavLinkActive, patriotNavLinkIdle } from "../../patriotTheme";

const links = [
  { to: "/discovery-feed", label: "Discovery feed" },
  { to: "/discovery-dashboard", label: "Dashboard" },
  { to: "/discovery-opportunities", label: "Opportunities" },
  { to: "/future-pull-list", label: "Future pull list" },
  { to: "/discovery-watchlists", label: "Watchlists" },
  { to: "/discovery-alerts", label: "Alerts" },
  { to: "/discovery-analytics", label: "Analytics" },
];

type Variant = "patriot" | "dark";

export function DiscoveryNav({ variant = "patriot" }: { variant?: Variant }): JSX.Element {
  if (variant === "dark") {
    return (
      <nav className="flex flex-wrap gap-2 text-sm">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) =>
              isActive
                ? "rounded-lg bg-amber-500/20 px-3 py-1 text-amber-200"
                : "rounded-lg border border-slate-700 px-3 py-1 text-slate-400 hover:text-slate-200"
            }
          >
            {l.label}
          </NavLink>
        ))}
      </nav>
    );
  }

  return (
    <nav className="flex flex-wrap gap-2 text-sm">
      {links.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          className={({ isActive }) => (isActive ? patriotNavLinkActive : patriotNavLinkIdle)}
        >
          {l.label}
        </NavLink>
      ))}
    </nav>
  );
}
