import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P85WorkflowHealthRead } from "../api/client";
import { CollectorErrorState } from "../components/CollectorErrorState";

export function WorkflowHealthPage(): JSX.Element {
  const [health, setHealth] = useState<P85WorkflowHealthRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setHealth(await apiClient.getPlatformWorkflowHealth());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Workflow health check failed.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8">
        <CollectorErrorState message={error} onRetry={() => void load()} />
      </div>
    );
  }

  if (!health) {
    return <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-400">Loading workflow health…</div>;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl">
          <h1 className="text-xl font-semibold">Workflow health</h1>
          <p className="text-sm text-slate-400">
            Score {health.health_score.toFixed(0)} · {health.status}
          </p>
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6 text-sm">
        <ul className="space-y-3">
          {health.issues.map((issue, i) => (
            <li key={i} className="rounded border border-slate-800 p-3">
              <p className="font-medium">
                [{issue.severity}] {issue.workflow} — {issue.issue_type}
              </p>
              <p className="text-slate-400">{issue.message}</p>
              <p className="mt-1 text-violet-300">{issue.recommended_fix}</p>
              {issue.action_url ? (
                <Link to={issue.action_url} className="mt-2 inline-block text-violet-400 hover:underline">
                  Go fix
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
