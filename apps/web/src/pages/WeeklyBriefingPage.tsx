import { useEffect, useState } from "react";

import { ApiError, apiClient, type P84CollectorBriefingRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function WeeklyBriefingPage(): JSX.Element {
  const [brief, setBrief] = useState<P84CollectorBriefingRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        setBrief(await apiClient.getWeeklyBriefing());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load weekly briefing.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <PatriotPageLayout
      eyebrow="P84"
      title="Weekly collector report"
      showExpansionNav
      error={error}
      loading={loading && !brief}
      maxWidthClass="max-w-3xl"
    >
      {brief ? (
        <PatriotPanel title="Best next actions">
          <ul className="list-disc space-y-1 pl-5 text-blue-900">
            {brief.top_actions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
