import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { ComicOsMark } from "./ComicOsMark";

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
    <main className="min-h-screen text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8 lg:flex-row lg:items-center lg:gap-10 lg:px-10">
        <section className="flex-1 rounded-2xl border border-blue-200 bg-white p-8 shadow-lg shadow-blue-900/10">
          <Link
            to="/login"
            className="inline-flex items-center gap-2 rounded-full border border-patriot-red bg-patriot-red px-3 py-1 text-xs font-bold uppercase tracking-[0.24em] text-white"
          >
            <ComicOsMark size={18} />
            ComicOS
          </Link>
          <div className="mt-8 max-w-xl space-y-4">
            <h1 className="text-4xl font-semibold tracking-tight text-patriot-navy sm:text-5xl">
              Portfolio Intelligence for Comic Investors
            </h1>
            <p className="text-base leading-7 text-slate-600 sm:text-lg">
              Build a user-specific comic portfolio, track inventory, and review acquisition data from a single
              dashboard.
            </p>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {[
              ["Inventory Ledger", "Authenticated asset-level portfolio tracking"],
              ["Acquisition Insight", "All-in cost basis and ownership visibility"],
              ["Mobile Friendly", "Responsive controls for quick review on the go"],
            ].map(([heading, copy]) => (
              <div key={heading} className="rounded-xl border border-blue-100 bg-blue-50/80 p-4">
                <p className="text-sm font-semibold text-patriot-navy">{heading}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">{copy}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-8 w-full lg:mt-0 lg:max-w-md">
          <div className="rounded-2xl border border-blue-200 bg-white p-6 shadow-lg shadow-slate-200/80 sm:p-8">
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold text-patriot-navy">{title}</h2>
              <p className="text-sm leading-6 text-slate-600">{subtitle}</p>
            </div>
            <div className="mt-6">{children}</div>
            <div className="mt-6 text-sm text-slate-600">{footer}</div>
          </div>
        </section>
      </div>
    </main>
  );
}
