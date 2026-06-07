import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P84CollectorNotificationRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function CollectorNotificationDashboardPage(): JSX.Element {
  const [unread, setUnread] = useState<P84CollectorNotificationRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const body = await apiClient.listCollectorNotifications({ refresh: true });
        setUnread(body.items.filter((i) => i.status === "UNREAD"));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load notifications.");
        setUnread([]);
      }
    })();
  }, []);

  return (
    <PatriotPageLayout
      eyebrow="P84"
      title="Notification dashboard"
      showExpansionNav
      error={error}
      maxWidthClass="max-w-3xl"
    >
      <PatriotPanel>
        <Link to="/notifications" className="font-medium text-blue-700 hover:text-red-700 hover:underline">
          Full notification center
        </Link>
        <ul className="mt-4 space-y-2 text-blue-900">
          {unread.map((n) => (
            <li key={n.id}>
              {n.title} ({n.notification_type})
            </li>
          ))}
        </ul>
      </PatriotPanel>
    </PatriotPageLayout>
  );
}
