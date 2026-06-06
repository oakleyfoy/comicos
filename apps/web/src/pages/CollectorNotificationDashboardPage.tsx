import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P84CollectorNotificationRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";

export function CollectorNotificationDashboardPage(): JSX.Element {
  const [unread, setUnread] = useState<P84CollectorNotificationRead[]>([]);

  useEffect(() => {
    void (async () => {
      try {
        const body = await apiClient.listCollectorNotifications({ refresh: true });
        setUnread(body.items.filter((i) => i.status === "UNREAD"));
      } catch {
        setUnread([]);
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <h1 className="text-xl font-semibold">Notification dashboard</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6 text-sm">
        <Link to="/notifications" className="text-violet-300 hover:underline">
          Full notification center
        </Link>
        <ul className="mt-4 space-y-2 text-slate-300">
          {unread.map((n) => (
            <li key={n.id}>
              {n.title} ({n.notification_type})
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
