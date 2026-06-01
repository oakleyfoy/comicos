import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/apiError";
import { formatDashboardWidgetError, settleDashboardWidgets } from "../dashboardPartialLoad";

describe("settleDashboardWidgets", () => {
  it("isolates failures so inventory widgets still resolve when portfolio fails", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { data, errors } = await settleDashboardWidgets({
      inventorySummary: Promise.resolve({ total_copies: 13 }),
      inventoryList: Promise.resolve({ total: 13, items: [{ inventory_copy_id: 1 }] }),
      portfolioPerformance: Promise.reject(new ApiError("Portfolio unavailable", 503)),
      collectionAnalyticsSummary: Promise.resolve({ total_copies: 13 }),
    });

    expect(data.inventorySummary).toEqual({ total_copies: 13 });
    expect(data.inventoryList).toEqual({ total: 13, items: [{ inventory_copy_id: 1 }] });
    expect(data.collectionAnalyticsSummary).toEqual({ total_copies: 13 });
    expect(data.portfolioPerformance).toBeUndefined();
    expect(errors.portfolioPerformance).toBe("Portfolio unavailable");
    expect(errors.inventorySummary).toBeUndefined();
    expect(errors.inventoryList).toBeUndefined();
    expect(consoleSpy).toHaveBeenCalledWith(
      "[DashboardPage] Failed to load dashboard widget: portfolioPerformance",
      expect.any(ApiError),
    );

    consoleSpy.mockRestore();
  });

  it("records 401 widget failures without rejecting the batch", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { data, errors } = await settleDashboardWidgets({
      inventorySummary: Promise.resolve({ total_copies: 5 }),
      scanPipeline: Promise.reject(new ApiError("Authentication required", 401)),
    });

    expect(data.inventorySummary).toEqual({ total_copies: 5 });
    expect(errors.scanPipeline).toBe("Authentication required");

    consoleSpy.mockRestore();
  });
});

describe("formatDashboardWidgetError", () => {
  it("maps ApiError and generic errors", () => {
    expect(formatDashboardWidgetError(new ApiError("Not found", 404))).toBe("Not found");
    expect(formatDashboardWidgetError(new Error("Network"))).toBe("Network");
    expect(formatDashboardWidgetError(null)).toBe("Request failed");
  });
});
