import type { AiDraftOrderItem } from "../api/client";

export type ImportReleaseLifecycleStatus =
  | "PREORDER"
  | "RELEASED_NOT_RECEIVED"
  | "RECEIVED"
  | "OVERDUE"
  | "UNKNOWN";

export interface ImportLifecyclePresentation {
  status: ImportReleaseLifecycleStatus;
  label: string;
  detail: string;
  sortBucket: number;
  cardClassName: string;
  badgeClassName: string;
}

const DEFAULT_BUCKET = 40;

export function lifecycleSortBucket(item: AiDraftOrderItem): number {
  return item.lifecycle_sort_bucket ?? DEFAULT_BUCKET;
}

export function sortDraftItemsByLifecycle<T extends { lifecycleSortBucket?: number; releaseDate?: string }>(
  items: T[],
): T[] {
  return [...items].sort((left, right) => {
    const bucketDelta = (left.lifecycleSortBucket ?? DEFAULT_BUCKET) - (right.lifecycleSortBucket ?? DEFAULT_BUCKET);
    if (bucketDelta !== 0) {
      return bucketDelta;
    }
    const leftDate = left.releaseDate?.trim() || "9999-99-99";
    const rightDate = right.releaseDate?.trim() || "9999-99-99";
    return leftDate.localeCompare(rightDate);
  });
}

export function importLifecyclePresentation(
  item: Pick<
    AiDraftOrderItem,
    | "release_lifecycle_status"
    | "lifecycle_display_label"
    | "lifecycle_display_detail"
    | "lifecycle_sort_bucket"
    | "is_preorder"
    | "is_overdue"
    | "is_released_not_received"
    | "release_status"
    | "parsed_release_date"
    | "release_date"
    | "order_status"
  >,
): ImportLifecyclePresentation | null {
  const status = item.release_lifecycle_status;
  if (!status) {
    return null;
  }

  const label = item.lifecycle_display_label ?? status;
  const detail = item.lifecycle_display_detail ?? "";
  const sortBucket = item.lifecycle_sort_bucket ?? DEFAULT_BUCKET;

  switch (status) {
    case "PREORDER":
      return {
        status,
        label,
        detail,
        sortBucket,
        cardClassName: "border-cyan-400/35 bg-cyan-950/40 shadow-cyan-950/20",
        badgeClassName: "border-cyan-400/30 bg-cyan-500/15 text-cyan-100",
      };
    case "RELEASED_NOT_RECEIVED":
      return {
        status,
        label,
        detail,
        sortBucket,
        cardClassName: "border-amber-400/35 bg-amber-950/30 shadow-amber-950/15",
        badgeClassName: "border-amber-400/30 bg-amber-500/15 text-amber-100",
      };
    case "OVERDUE":
      return {
        status,
        label,
        detail,
        sortBucket,
        cardClassName: "border-rose-400/35 bg-rose-950/35 shadow-rose-950/20",
        badgeClassName: "border-rose-400/30 bg-rose-500/15 text-rose-100",
      };
    case "RECEIVED":
      return {
        status,
        label,
        detail,
        sortBucket,
        cardClassName: "border-emerald-400/35 bg-emerald-950/30 shadow-emerald-950/15",
        badgeClassName: "border-emerald-400/30 bg-emerald-500/15 text-emerald-100",
      };
    default:
      return {
        status: "UNKNOWN",
        label,
        detail,
        sortBucket,
        cardClassName: "border-white/10 bg-slate-900/70 shadow-black/20",
        badgeClassName: "border-slate-400/25 bg-slate-500/10 text-slate-200",
      };
  }
}

export function effectiveReleaseStatusForForm(
  item: Pick<AiDraftOrderItem, "release_status" | "release_lifecycle_status" | "is_preorder">,
): "" | "released" | "not_released_yet" | "unknown" {
  if (item.release_lifecycle_status === "PREORDER" || item.is_preorder) {
    return "not_released_yet";
  }
  if (item.release_status === "released" || item.release_status === "not_released_yet" || item.release_status === "unknown") {
    return item.release_status;
  }
  return "";
}
