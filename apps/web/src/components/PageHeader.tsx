import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="rounded-2xl border border-blue-200 bg-white p-6 shadow-md shadow-blue-900/5 ring-1 ring-slate-100">
      <div className="border-l-4 border-patriot-red pl-4">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-patriot-blue">
              {eyebrow}
            </span>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-patriot-navy sm:text-4xl">{title}</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 sm:text-base">{description}</p>
            </div>
          </div>

          {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
        </div>
      </div>
    </header>
  );
}
