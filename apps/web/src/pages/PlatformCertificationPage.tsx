import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P85PlatformCertificationRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function PlatformCertificationPage(): JSX.Element {
  const [cert, setCert] = useState<P85PlatformCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setCert(await apiClient.getPlatformCertification());
    } catch (err) {
      setCert(null);
      setError(err instanceof ApiError ? err.message : "Certification check failed.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PatriotPageLayout
      eyebrow="P85 · Platform"
      title="Platform certification"
      description={cert?.title}
      error={error}
      onRetry={() => void load()}
      loading={loading && !cert}
      maxWidthClass="max-w-3xl"
    >
      {cert ? (
        <>
          <PatriotPanel title="Status">
            <p className="text-lg font-medium text-blue-950">{cert.status}</p>
            <p className="mt-2">
              Readiness {cert.readiness_score.toFixed(1)}% · Passed {cert.checks_passed} · Failures {cert.failures}
            </p>
          </PatriotPanel>
          <PatriotPanel title="Categories">
            <ul className="space-y-2">
              {cert.categories.map((c) => (
                <li key={c.category} className="flex justify-between rounded border border-blue-200 px-3 py-2">
                  <span>{c.category}</span>
                  <span className="font-medium text-red-700">{c.status}</span>
                </li>
              ))}
            </ul>
          </PatriotPanel>
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
