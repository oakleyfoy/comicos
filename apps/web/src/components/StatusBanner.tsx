import type { ReactNode } from "react";

export function StatusBanner({
  tone,
  children,
}: {
  tone: "error" | "success" | "info";
  children: ReactNode;
}) {
  const toneClasses = {
    error: "border-rose-400/20 bg-rose-400/10 text-rose-200",
    success: "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
    info: "border-cyan-400/20 bg-cyan-400/10 text-cyan-100",
  };

  return (
    <div className={`rounded-2xl border px-5 py-4 text-sm ${toneClasses[tone]}`}>{children}</div>
  );
}
