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
        cardClassName: "border-cyan-400/80 bg-slate-900 shadow-lg shadow-black/40",
        badgeClassName: "border-cyan-300/80 bg-cyan-700/50 text-white",
      };
    case "RELEASED_NOT_RECEIVED":
      return {
        status,
        label,
        detail,
        sortBucket,
        cardClassName: "border-amber-400/80 bg-slate-900 shadow-lg shadow-black/40",
        badgeClassName: "border-amber-300/80 bg-amber-700/50 text-white",
      };
    case "OVERDUE":
      return {
        status,
        label,
        detail,
        sortBucket,
        cardClassName: "border-rose-400/80 bg-slate-900 shadow-lg shadow-black/40",
        badgeClassName: "border-rose-300/80 bg-rose-700/50 text-white",
      };
    case "RECEIVED":
      return {
        status,
        label,
        detail,
        sortBucket,
        cardClassName: "border-emerald-400/80 bg-slate-900 shadow-lg shadow-black/40",
        badgeClassName: "border-emerald-300/80 bg-emerald-700/50 text-white",
      };
    default:
      return {
        status: "UNKNOWN",
        label,
        detail,
        sortBucket,
        cardClassName: "border-slate-500/70 bg-slate-900 shadow-lg shadow-black/40",
        badgeClassName: "border-slate-400/70 bg-slate-700/60 text-white",
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
