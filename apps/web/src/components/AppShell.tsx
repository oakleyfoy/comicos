import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const navLinks = [
  { label: "Dashboard", to: "/dashboard" },
  { label: "Orders", to: "/orders" },
  { label: "Imports", to: "/imports" },
  { label: "Email Imports", to: "/imports/email" },
  { label: "Import Order", to: "/orders/import" },
  { label: "Add Order", to: "/orders/new" },
  { label: "Integrations", to: "/settings/integrations" },
  { label: "Scanner presets", to: "/settings/scanner-profiles" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { isOpsAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const visibleNavLinks = isOpsAdmin
    ? [...navLinks, { label: "Operations", to: "/ops" }]
    : navLinks;

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="border-b border-white/10 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <Link
              to="/dashboard"
              className="inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200"
            >
              ComicOS
            </Link>
            <p className="hidden text-sm text-slate-500 md:block">
              Portfolio Intelligence for Comic Investors
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {visibleNavLinks.map((link) => {
              const isActive =
                location.pathname === link.to ||
                (link.to !== "/dashboard" && location.pathname.startsWith(`${link.to}/`));

              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                    isActive
                      ? "bg-cyan-400 text-slate-950"
                      : "border border-white/10 text-slate-100 hover:border-cyan-300/40 hover:bg-white/5"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-300/40 hover:bg-white/5"
            >
              Logout
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
    </main>
  );
}
