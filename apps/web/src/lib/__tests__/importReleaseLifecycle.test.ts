import { describe, expect, it } from "vitest";

import {
  importLifecyclePresentation,
  sortDraftItemsByLifecycle,
} from "../importReleaseLifecycle";

describe("importReleaseLifecycle", () => {
  it("renders preorder badge copy", () => {
    const presentation = importLifecyclePresentation({
      release_lifecycle_status: "PREORDER",
      lifecycle_display_label: "Upcoming Release",
      lifecycle_display_detail: "Releases Jun 17, 2026 · 9 days remaining",
      lifecycle_sort_bucket: 10,
      is_preorder: true,
      is_overdue: false,
      is_released_not_received: false,
      release_status: "not_released_yet",
      parsed_release_date: "2026-06-17",
      release_date: "2026-06-17",
      order_status: "preordered",
    });
    expect(presentation?.label).toBe("Upcoming Release");
    expect(presentation?.detail).toContain("9 days remaining");
  });

  it("sorts preorder items before unknown items", () => {
    const sorted = sortDraftItemsByLifecycle([
      { lifecycleSortBucket: 40, releaseDate: "2024-01-01", title: "unknown" },
      { lifecycleSortBucket: 10, releaseDate: "2026-06-17", title: "preorder" },
    ]);
    expect(sorted[0]?.title).toBe("preorder");
  });

  it("renders overdue badge label", () => {
    const presentation = importLifecyclePresentation({
      release_lifecycle_status: "OVERDUE",
      lifecycle_display_label: "Possibly Missing",
      lifecycle_display_detail: "Released May 01, 2026 · possibly missing",
      lifecycle_sort_bucket: 30,
      is_preorder: false,
      is_overdue: true,
      is_released_not_received: false,
      release_status: "released",
      parsed_release_date: "2026-05-01",
      release_date: "2026-05-01",
      order_status: "ordered",
    });
    expect(presentation?.label).toBe("Possibly Missing");
  });
});
