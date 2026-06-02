import type { ReactNode } from "react";

export function StatusBanner({
  tone,
  children,
}: {
  tone: "error" | "success" | "info" | "warning";
  children: ReactNode;
}) {
  const toneClasses = {
    error: "border-red-300 bg-red-50 text-red-900",
    success: "border-emerald-300 bg-emerald-50 text-emerald-900",
    info: "border-blue-300 bg-blue-50 text-blue-900",
    warning: "border-amber-300 bg-amber-50 text-amber-950",
  };

  return (
    <div className={`rounded-xl border px-5 py-4 text-sm ${toneClasses[tone]}`}>{children}</div>
  );
}
