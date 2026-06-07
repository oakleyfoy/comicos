import { NavLink } from "react-router-dom";

import { patriotNavLinkActive, patriotNavLinkIdle } from "../../patriotTheme";

const links = [
  { to: "/collector-profile", label: "Profile" },
  { to: "/collector-goals", label: "Goals" },
  { to: "/collector-budget", label: "Budget" },
  { to: "/collector-recommendations", label: "Recs" },
  { to: "/collector-budget-dashboard", label: "Budget dash" },
  { to: "/collector-quantity-intelligence", label: "Quantities" },
  { to: "/collector-analytics", label: "Analytics" },
];

export function CollectorProfileNav(): JSX.Element {
  return (
    <nav className="flex flex-wrap gap-2 text-sm">
      {links.map((link) => (
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
