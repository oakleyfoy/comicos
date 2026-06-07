import { NavLink } from "react-router-dom";

import { patriotNavLinkActive, patriotNavLinkIdle } from "../../patriotTheme";

const links = [
  { to: "/sell-queue", label: "Sell queue" },
  { to: "/listing-drafts", label: "Listing drafts" },
  { to: "/listings", label: "Listings" },
  { to: "/selling-analytics", label: "Selling analytics" },
  { to: "/bundle-opportunities", label: "Bundles" },
];

type Variant = "patriot" | "dark";

export function SellWorkflowNav({ variant = "patriot" }: { variant?: Variant }): JSX.Element {
  if (variant === "dark") {
    return (
      <nav className="flex flex-wrap gap-3 text-sm">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              isActive
                ? "font-semibold text-amber-200 underline underline-offset-4"
                : "text-slate-400 hover:text-slate-200"
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    );
  }

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
