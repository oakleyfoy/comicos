const METRIC_LABELS: Record<string, string> = {
  active_inventory_count: "Active inventory",
  pending_reviews_count: "Pending reviews",
  assigned_inventory_count: "Assigned inventory",
  unread_notifications_count: "Unread notifications",
  active_staff_count: "Active staff",
  storefront_public_inventory_count: "Public storefront items",
  recent_activity_count: "Recent activity",
  active_org_sessions_count: "Active org sessions",
};

const SECTION_LABELS: Record<string, string> = {
  inventory: "Inventory",
  reviews: "Reviews",
  activity: "Activity",
  storefront: "Storefront",
  notifications: "Notifications",
  security: "Security",
};

export function metricLabel(metricKey: string): string {
  return METRIC_LABELS[metricKey] ?? metricKey.replace(/_/g, " ");
}

export function sectionLabel(sectionKey: string): string {
  return SECTION_LABELS[sectionKey] ?? sectionKey.replace(/_/g, " ");
}

export function formatMetricValue(value: unknown): string {
  if (typeof value === "number") {
    return new Intl.NumberFormat("en-US").format(value);
  }
  if (value === null || value === undefined) {
    return "—";
  }
  return String(value);
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
