import { useEffect, useState } from "react";

import { ApiError, apiClient, type P84CollectorBriefingRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function WeeklyBriefingPage(): JSX.Element {
  const [brief, setBrief] = useState<P84CollectorBriefingRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setBrief(await apiClient.getWeeklyBriefing());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load weekly briefing.");
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <h1 className="text-xl font-semibold">Weekly collector report</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6 text-sm">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {brief ? (
          <>
            <h2 className="font-semibold">Best next actions</h2>
            <ul className="list-disc pl-5 text-slate-300">
              {brief.top_actions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-slate-400">Loading…</p>
        )}
      </main>
    </div>
  );
}
