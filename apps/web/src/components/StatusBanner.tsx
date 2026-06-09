import type { ReactNode } from "react";

export function StatusBanner({
  tone,
  children,
  emphasis = "default",
}: {
  tone: "error" | "success" | "info" | "warning";
  children: ReactNode;
  emphasis?: "default" | "prominent";
}) {
  const toneClasses = {
    error: "border-red-300 bg-red-50 text-red-900",
    success: "border-emerald-300 bg-emerald-50 text-emerald-900",
    info: "border-blue-300 bg-blue-50 text-blue-900",
    warning: "border-amber-300 bg-amber-50 text-amber-950",
  };

  const prominentToneClasses = {
    error: "border-red-500 bg-red-100 text-red-950",
    success: "border-emerald-500 bg-emerald-100 text-emerald-950",
    info: "border-blue-500 bg-blue-100 text-blue-950",
    warning: "border-amber-500 bg-amber-100 text-amber-950",
  };

  const isProminent = emphasis === "prominent";

  return (
    <div
      className={`${
        isProminent
          ? `rounded-2xl border-2 px-6 py-5 text-lg font-semibold shadow-md ${prominentToneClasses[tone]}`
          : `rounded-xl border px-5 py-4 text-sm ${toneClasses[tone]}`
      }`}
      role={isProminent ? "status" : undefined}
      aria-live={isProminent ? "polite" : undefined}
    >
      {children}
    </div>
  );
}
