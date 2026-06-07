import { NavLink, useLocation } from "react-router-dom";

import { patriotNavLinkActive, patriotNavLinkIdle } from "../patriotTheme";

const LINKS = [
  { to: "/buy-opportunities", label: "Buy Opportunities" },
  { to: "/marketplace-monitoring", label: "Marketplace Monitoring" },
  { to: "/marketplace-command-center", label: "Marketplace Command Center" },
] as const;

export function BuyMarketplaceNav(): JSX.Element {
  const location = useLocation();
  return (
    <nav className="flex flex-wrap gap-2 text-sm" aria-label="Buy marketplace">
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
