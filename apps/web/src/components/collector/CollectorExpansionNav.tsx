import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/collector-command-center", label: "Command Center" },
  { to: "/marketplace-opportunities", label: "Marketplace Deals" },
  { to: "/marketplace-acquisition-dashboard", label: "Acquisition Dashboard" },
  { to: "/collection-valuation-dashboard", label: "Valuation Dashboard" },
  { to: "/notifications", label: "Notifications" },
  { to: "/daily-briefing", label: "Daily Briefing" },
  { to: "/weekly-briefing", label: "Weekly Briefing" },
];

export function CollectorExpansionNav(): JSX.Element {
  return (
    <nav className="flex flex-wrap gap-2 text-sm">
      {LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) =>
            isActive ? "rounded bg-violet-700/40 px-2 py-1 text-violet-100" : "rounded px-2 py-1 text-slate-400 hover:text-white"
          }
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
