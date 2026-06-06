import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function CollectorEmptyState({
  title,
  description,
  actionLabel,
  actionTo,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  actionTo?: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/50 p-6 text-center">
      <h3 className="text-base font-semibold text-slate-100">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">{description}</p>
      {actionLabel && actionTo ? (
        <Link to={actionTo} className="mt-4 inline-block text-sm text-violet-300 hover:underline">
          {actionLabel}
        </Link>
      ) : null}
    </div>
  );
}
