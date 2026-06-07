import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "../../AppShell";
import { patriotNavPillActive, patriotNavPillIdle } from "../../patriotTheme";

type Props = {
  eyebrow: string;
  title: string;
  children: ReactNode;
  headerLinks?: { to: string; label: string }[];
  subNav?: ReactNode;
  narrow?: boolean;
};

export function PatriotMobileShell({
  eyebrow,
  title,
  children,
  headerLinks,
  subNav,
  narrow = true,
}: Props): JSX.Element {
  const width = narrow ? "max-w-lg" : "max-w-5xl";

  return (
    <AppShell>
      <div className={`mx-auto overflow-hidden rounded-xl bg-blue-950 text-white ${width}`}>
        <header className="border-b border-red-700 bg-gradient-to-r from-blue-950 via-blue-900 to-red-900 px-4 py-5 sm:px-6">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-[11px] uppercase tracking-[0.2em] text-red-200">{eyebrow}</p>
              <h1 className="text-xl font-semibold">{title}</h1>
            </div>
            {headerLinks?.length ? (
              <div className="flex flex-wrap justify-end gap-2 text-sm">
                {headerLinks.map((link) => (
                  <Link
                    key={link.to}
                    to={link.to}
                    className="text-blue-100 underline-offset-2 hover:text-white hover:underline"
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
          {subNav ? <div className="mt-3">{subNav}</div> : null}
        </header>
        <main className="space-y-4 bg-blue-950 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </AppShell>
  );
}

export function PatriotMobileNav({
  links,
  pathname,
}: {
  links: { to: string; label: string }[];
  pathname: string;
}): JSX.Element {
  return (
    <nav className="flex flex-wrap gap-2 text-xs">
      {links.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className={pathname === link.to || pathname.startsWith(`${link.to}/`) ? patriotNavPillActive : patriotNavPillIdle}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}

/** White card for mobile patriot pages. */
export function PatriotMobilePanel({ children, className = "" }: { children: ReactNode; className?: string }): JSX.Element {
  return (
    <section className={`rounded-2xl border border-blue-200 bg-white p-4 text-blue-950 shadow-sm ${className}`}>
      {children}
    </section>
  );
}
