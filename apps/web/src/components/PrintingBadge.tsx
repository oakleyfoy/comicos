export type PrintingBadgeRead = {
  label: string;
  kind: string;
  printing_number?: number | null;
};

type Props = {
  badge: PrintingBadgeRead | null | undefined;
  className?: string;
};

export function PrintingBadge({ badge, className = "" }: Props): JSX.Element | null {
  if (!badge?.label) return null;
  return (
    <span
      className={`inline-flex items-center rounded-md border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-100 ${className}`}
      title={badge.kind.replace(/_/g, " ")}
    >
      {badge.label}
    </span>
  );
}
