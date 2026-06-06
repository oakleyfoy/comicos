import type { ReactNode } from "react";

export function CollectorErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  children,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-red-900/50 bg-red-950/30 p-4 text-sm text-red-100">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 text-red-200/90">{message}</p>
      {onRetry ? (
        <button type="button" className="mt-3 text-violet-300 hover:underline" onClick={onRetry}>
          Try again
        </button>
      ) : null}
      {children}
    </div>
  );
}
