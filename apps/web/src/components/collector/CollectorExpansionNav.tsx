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

type NavVariant = "dark" | "patriot";

export function CollectorExpansionNav({ variant = "dark" }: { variant?: NavVariant }): JSX.Element {
  const activeClass =
    variant === "patriot"
      ? "rounded bg-red-700 px-2 py-1 font-medium text-white shadow-sm"
      : "rounded bg-violet-700/40 px-2 py-1 text-violet-100";
  const idleClass =
    variant === "patriot"
      ? "rounded px-2 py-1 text-blue-100 hover:bg-white/10 hover:text-white"
      : "rounded px-2 py-1 text-slate-400 hover:text-white";

  return (
    <nav className="flex flex-wrap gap-2 text-sm">
      {LINKS.map((link) => (
        <NavLink key={link.to} to={link.to} className={({ isActive }) => (isActive ? activeClass : idleClass)}>
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
