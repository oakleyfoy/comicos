import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function AuthShell({
  title,
  subtitle,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  footer: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8 lg:flex-row lg:items-center lg:gap-10 lg:px-10">
        <section className="flex-1 rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-indigo-950/70 p-8 shadow-2xl shadow-cyan-950/20">
          <Link
            to="/login"
            className="inline-flex items-center rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200"
          >
            ComicOS
          </Link>
          <div className="mt-8 max-w-xl space-y-4">
            <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              Portfolio Intelligence for Comic Investors
            </h1>
            <p className="text-base leading-7 text-slate-300 sm:text-lg">
              Build a user-specific comic portfolio, track inventory, and review acquisition data
              from a single dark-mode dashboard.
            </p>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {[
              ["Inventory Ledger", "Authenticated asset-level portfolio tracking"],
              ["Acquisition Insight", "All-in cost basis and ownership visibility"],
              ["Mobile Friendly", "Responsive controls for quick review on the go"],
            ].map(([heading, copy]) => (
              <div key={heading} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-sm font-semibold text-white">{heading}</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">{copy}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-8 w-full lg:mt-0 lg:max-w-md">
          <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-xl shadow-black/20 sm:p-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold text-white">{title}</h2>
              <p className="text-sm leading-6 text-slate-400">{subtitle}</p>
            </div>
            <div className="mt-6">{children}</div>
            <div className="mt-6 text-sm text-slate-400">{footer}</div>
          </div>
        </section>
      </div>
    </main>
  );
}
