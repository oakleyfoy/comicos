import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P85WorkflowHealthRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function WorkflowHealthPage(): JSX.Element {
  const [health, setHealth] = useState<P85WorkflowHealthRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setHealth(await apiClient.getPlatformWorkflowHealth());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Workflow health check failed.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PatriotPageLayout
      eyebrow="P85"
      title="Workflow health"
      description={
        health ? `Score ${health.health_score.toFixed(0)} · ${health.status}` : undefined
      }
      error={error}
      onRetry={() => void load()}
      loading={loading && !health}
      maxWidthClass="max-w-3xl"
    >
      {health ? (
        <ul className="space-y-3">
          {health.issues.map((issue, i) => (
            <li key={i}>
              <PatriotPanel>
                <p className="font-medium text-blue-950">
                  [{issue.severity}] {issue.workflow} — {issue.issue_type}
                </p>
                <p className="text-blue-800">{issue.message}</p>
                <p className="mt-1 text-red-700">{issue.recommended_fix}</p>
                {issue.action_url ? (
                  <Link
                    to={issue.action_url}
                    className="mt-2 inline-block font-medium text-blue-700 hover:text-red-700 hover:underline"
                  >
                    Go fix
                  </Link>
                ) : null}
              </PatriotPanel>
            </li>
          ))}
        </ul>
      ) : null}
    </PatriotPageLayout>
  );
}
