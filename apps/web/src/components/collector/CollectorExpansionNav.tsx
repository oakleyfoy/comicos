import { NavLink } from "react-router-dom";

import { patriotNavLinkActive, patriotNavLinkIdle } from "../patriotTheme";

const LINKS = [
  { to: "/collector-command-center", label: "Command Center" },
  { to: "/marketplace-opportunities", label: "Marketplace Deals" },
  { to: "/marketplace-acquisition-dashboard", label: "Acquisition Dashboard" },
  { to: "/collection-valuation-dashboard", label: "Valuation Dashboard" },
  { to: "/notifications", label: "Notifications" },
  { to: "/daily-briefing", label: "Daily Briefing" },
  { to: "/weekly-briefing", label: "Weekly Briefing" },
];

/** Red / white / blue sub-nav for collector expansion pages (on patriot header). */
export function CollectorExpansionNav(): JSX.Element {
  return (
    <nav className="flex flex-wrap gap-2 text-sm">
      {LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) => (isActive ? patriotNavLinkActive : patriotNavLinkIdle)}
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}
