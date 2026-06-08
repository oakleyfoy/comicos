import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "./AppShell";
import { CollectorExpansionNav } from "./collector/CollectorExpansionNav";
import { CollectorErrorState } from "./CollectorErrorState";

type Props = {
  eyebrow: string;
  title: string;
  description?: string;
  error?: string | null;
  onRetry?: () => void;
  loading?: boolean;
  showExpansionNav?: boolean;
  subNav?: ReactNode;
  headerExtra?: ReactNode;
  headerActions?: ReactNode;
  maxWidthClass?: string;
  children: ReactNode;
};

export function PatriotPageLayout({
  eyebrow,
  title,
  description,
  error,
  onRetry,
  loading,
  showExpansionNav = false,
  subNav,
  headerExtra,
  headerActions,
  maxWidthClass = "max-w-5xl",
  children,
}: Props): JSX.Element {
  return (
    <AppShell>
      <div className="overflow-hidden rounded-xl bg-blue-950 text-white">
        <header className="border-b border-red-700 bg-gradient-to-r from-blue-950 via-blue-900 to-red-900 px-4 py-6">
          <div className={`mx-auto ${maxWidthClass} space-y-2`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <p className="text-[11px] uppercase tracking-[0.2em] text-red-200">{eyebrow}</p>
                <h1 className="text-2xl font-semibold">{title}</h1>
                {description ? <p className="text-sm text-blue-100">{description}</p> : null}
              </div>
              {headerActions ? <div className="shrink-0">{headerActions}</div> : null}
            </div>
            {showExpansionNav ? <CollectorExpansionNav /> : null}
            {subNav}
            {headerExtra ? <div className="text-sm text-blue-100">{headerExtra}</div> : null}
          </div>
        </header>
        <main className={`mx-auto ${maxWidthClass} space-y-4 px-4 py-6`}>
          {error ? <CollectorErrorState message={error} onRetry={onRetry} /> : null}
          {loading ? <p className="text-sm text-blue-100">Loading…</p> : null}
          {children}
        </main>
      </div>
    </AppShell>
  );
}

export function PatriotInlineLink({ to, children }: { to: string; children: ReactNode }): JSX.Element {
  return (
    <Link to={to} className="text-blue-100 underline-offset-2 hover:text-white hover:underline">
      {children}
    </Link>
  );
}

/** White content panel for patriot-themed pages. */
export function PatriotPanel({
  title,
  children,
  className = "",
  id,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  id?: string;
}): JSX.Element {
  return (
    <section
      id={id}
      className={`rounded-lg border border-blue-800 bg-white px-4 py-3 text-blue-950 shadow-sm ${className}`}
    >
      {title ? <h2 className="text-sm font-semibold uppercase tracking-wide text-red-700">{title}</h2> : null}
      <div className={title ? "mt-2 text-sm text-blue-900" : "text-sm text-blue-900"}>{children}</div>
    </section>
  );
}
