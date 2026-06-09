import { NavLink, useLocation } from "react-router-dom";

import { patriotNavLinkActive, patriotNavLinkIdle } from "../patriotTheme";

const LINKS: { to: string; label: string; activePaths?: string[] }[] = [
  { to: "/collector-command-center", label: "Command Center" },
  { to: "/receiving", label: "Receive Comics" },
  {
    to: "/buy-opportunities",
    label: "Buy Opportunities",
    activePaths: ["/buy-opportunities", "/marketplace-opportunities"],
  },
  { to: "/marketplace-acquisition-dashboard", label: "Acquisition Dashboard" },
  { to: "/collection-valuation-dashboard", label: "Valuation Dashboard" },
  { to: "/notifications", label: "Notifications" },
  { to: "/daily-briefing", label: "Daily Briefing" },
  { to: "/weekly-briefing", label: "Weekly Briefing" },
];

/** Red / white / blue sub-nav for collector expansion pages (on patriot header). */
export function CollectorExpansionNav(): JSX.Element {
  const location = useLocation();
  return (
    <nav className="flex flex-wrap gap-2 text-sm">
      {LINKS.map((link) => {
        const active = link.activePaths
          ? link.activePaths.some(
              (p) => location.pathname === p || location.pathname.startsWith(`${p}/`),
            )
          : location.pathname === link.to || location.pathname.startsWith(`${link.to}/`);
        return (
          <NavLink
            key={link.to}
            to={link.to}
            className={active ? patriotNavLinkActive : patriotNavLinkIdle}
          >
            {link.label}
          </NavLink>
        );
      })}
    </nav>
  );
}
