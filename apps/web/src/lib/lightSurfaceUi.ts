/** Shared Tailwind classes for AppShell pages (light patriot-sky canvas). */

export const lightStatCard =
  "rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm";
export const lightStatCardLg = "rounded-xl border border-slate-200 bg-white p-4 shadow-sm";
export const lightStatValue = "text-lg font-semibold text-slate-900";
export const lightStatValueXl = "mt-1 text-2xl font-semibold text-slate-900";
export const lightStatLabel = "text-slate-500 text-xs uppercase tracking-wide";
export const lightStatLabelSm = "text-slate-500";

export const lightTableWrap =
  "overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm";
export const lightTable = "min-w-full text-left text-sm text-slate-800";
export const lightTableHead =
  "border-b border-slate-200 bg-slate-800 text-xs uppercase tracking-wide text-slate-200";
export const lightTableRow = "border-b border-slate-100";
export const lightTableCellPrimary = "px-4 py-2 font-medium text-slate-900";
export const lightTableCell = "px-4 py-2 text-slate-800";
export const lightTableCellMuted = "px-4 py-2 text-slate-600";
export const lightTableEmpty = "px-4 py-6 text-center text-slate-500";

export const lightSectionTitle = "text-sm font-semibold uppercase tracking-wide text-slate-600";
export const lightSectionPanel =
  "rounded-3xl border border-slate-200 bg-white p-4 shadow-sm";
export const lightSectionPanelLg =
  "rounded-3xl border border-slate-200 bg-white p-5 shadow-sm";
export const lightListItem =
  "rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800";

export const lightField =
  "rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900";
export const lightFieldLg =
  "rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900";
export const lightLabel = "text-sm text-slate-600";

export function futureReleaseActionBadge(action: string): string {
  const base =
    "inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide";
  switch (action) {
    case "PREORDER_NOW":
      return `${base} bg-rose-100 text-rose-900`;
    case "PREORDER_THIS_WEEK":
      return `${base} bg-amber-100 text-amber-900`;
    case "MISSED_FOC":
      return `${base} bg-orange-100 text-orange-900`;
    case "WATCH":
      return `${base} bg-sky-100 text-sky-900`;
    default:
      return `${base} bg-slate-100 text-slate-800`;
  }
}
