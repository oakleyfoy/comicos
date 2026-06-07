import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function CollectorEmptyState({
  title,
  description,
  actionLabel,
  actionTo,
  variant = "patriot",
}: {
  title: string;
  description: string;
  actionLabel?: string;
  actionTo?: string;
  variant?: "patriot" | "dark";
}) {
  const box =
    variant === "patriot"
      ? "rounded-xl border border-dashed border-blue-300 bg-white p-6 text-center text-blue-950"
      : "rounded-xl border border-dashed border-slate-700 bg-slate-900/50 p-6 text-center";
  const titleClass = variant === "patriot" ? "text-base font-semibold text-blue-950" : "text-base font-semibold text-slate-100";
  const descClass = variant === "patriot" ? "mx-auto mt-2 max-w-md text-sm text-blue-800/80" : "mx-auto mt-2 max-w-md text-sm text-slate-400";
  const linkClass =
    variant === "patriot"
      ? "mt-4 inline-block text-sm font-medium text-red-700 hover:underline"
      : "mt-4 inline-block text-sm text-violet-300 hover:underline";

  return (
    <div className={box}>
      <h3 className={titleClass}>{title}</h3>
      <p className={descClass}>{description}</p>
      {actionLabel && actionTo ? (
        <Link to={actionTo} className={linkClass}>
          {actionLabel}
        </Link>
      ) : null}
    </div>
  );
}
