import { NavLink, useLocation } from "react-router-dom";

import { patriotNavLinkActive, patriotNavLinkIdle } from "../patriotTheme";

const LINKS = [
  { to: "/sell-command-center", label: "Sell Command Center" },
  { to: "/sell-candidates", label: "Sell Candidates" },
  { to: "/market-pricing", label: "Market Pricing" },
  { to: "/listing-drafts", label: "Listing Drafts" },
  { to: "/listing-management", label: "Listing Management" },
] as const;

export function SellCommandCenterNav(): JSX.Element {
  const location = useLocation();
  return (
    <nav className="flex flex-wrap gap-2 text-sm" aria-label="Sell workflow">
      {LINKS.map((link) => {
        const active =
          location.pathname === link.to || location.pathname.startsWith(`${link.to}/`);
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
