import { Link, useLocation } from "react-router-dom";

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
  const location = useLocation();
  return (
    <nav className="flex flex-wrap gap-3 text-sm">
      {links.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className={
            location.pathname === link.to
              ? "font-semibold text-sky-200 underline underline-offset-4"
              : "text-slate-400 hover:text-slate-200"
          }
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
