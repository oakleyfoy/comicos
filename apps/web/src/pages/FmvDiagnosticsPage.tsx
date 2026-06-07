import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P90FmvDiagnosticsRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function FmvDiagnosticsPage(): JSX.Element {
  const [data, setData] = useState<P90FmvDiagnosticsRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setData(await apiClient.getFmvDiagnostics());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load FMV diagnostics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PatriotPageLayout
      eyebrow="Ops"
      title="FMV Diagnostics"
      description="Read-only coverage of FMV V2 snapshot sources, confidence, and trends."
      error={error}
      onRetry={() => void load()}
      loading={loading && !data}
      maxWidthClass="max-w-4xl"
    >
      {data ? (
        <>
          <PatriotPanel title="Coverage">
            <p className="text-sm text-blue-900">Snapshot rows: {data.snapshot_count}</p>
            <p className="text-sm text-blue-900">Identity coverage (latest): {data.identity_coverage}</p>
          </PatriotPanel>
          <PatriotPanel title="Confidence distribution" className="mt-4">
            <pre className="text-xs text-blue-900">{JSON.stringify(data.confidence_distribution, null, 2)}</pre>
          </PatriotPanel>
          <PatriotPanel title="Valuation source distribution" className="mt-4">
            <pre className="text-xs text-blue-900">{JSON.stringify(data.source_distribution, null, 2)}</pre>
          </PatriotPanel>
          <PatriotPanel title="Trend distribution" className="mt-4">
            <pre className="text-xs text-blue-900">{JSON.stringify(data.trend_distribution, null, 2)}</pre>
          </PatriotPanel>
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
