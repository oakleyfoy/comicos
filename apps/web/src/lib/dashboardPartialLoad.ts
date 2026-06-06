import { ApiError } from "../api/apiError";

export const DASHBOARD_WIDGET_KEYS = [
  "inventorySummary",
  "inventoryList",
  "portfolioPerformance",
  "portfolioValue",
  "inventoryIntelSummary",
  "inventoryIntelHealth",
  "inventoryRisks",
  "inventoryAction",
  "orderArrival",
  "collectionTimeline",
  "duplicateOwnership",
  "runDetection",
  "collectionAnalyticsSummary",
  "collectionAnalyticsPublishers",
  "collectionAnalyticsQuality",
  "scanPipeline",
  "physicalIntake",
  "inventoryArrivalTracking",
] as const;

export type DashboardWidgetKey = (typeof DASHBOARD_WIDGET_KEYS)[number];

export function formatDashboardWidgetError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

/**
 * Loads dashboard widgets independently. Successful responses are returned in `data`;
 * failures are logged and recorded in `errors` without rejecting the overall load.
 */
export async function settleDashboardWidgets<K extends string>(
  widgets: Record<K, Promise<unknown>>,
): Promise<{
  data: Partial<Record<K, unknown>>;
  errors: Partial<Record<K, string>>;
}> {
  const entries = Object.entries(widgets) as [K, Promise<unknown>][];
  const settled = await Promise.allSettled(entries.map(([, promise]) => promise));
  const data: Partial<Record<K, unknown>> = {};
  const errors: Partial<Record<K, string>> = {};

  entries.forEach(([key], index) => {
    const result = settled[index];
    if (result.status === "fulfilled") {
      data[key] = result.value;
      return;
    }
    console.error(`[DashboardPage] Failed to load dashboard widget: ${key}`, result.reason);
    errors[key] = formatDashboardWidgetError(result.reason);
  });

  return { data, errors };
}
