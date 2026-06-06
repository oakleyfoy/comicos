import { Link, useLocation } from "react-router-dom";

const links = [
  { to: "/sell-queue", label: "Sell queue" },
  { to: "/listing-drafts", label: "Listing drafts" },
  { to: "/listings", label: "Listings" },
  { to: "/selling-analytics", label: "Selling analytics" },
  { to: "/bundle-opportunities", label: "Bundles" },
];

export function SellWorkflowNav(): JSX.Element {
  const location = useLocation();
  return (
    <nav className="flex flex-wrap gap-3 text-sm">
      {links.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className={
            location.pathname === link.to
              ? "font-semibold text-amber-200 underline underline-offset-4"
              : "text-slate-400 hover:text-slate-200"
          }
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
