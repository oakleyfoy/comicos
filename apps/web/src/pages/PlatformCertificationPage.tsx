import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P85PlatformCertificationRead } from "../api/client";
import { CollectorErrorState } from "../components/CollectorErrorState";

export function PlatformCertificationPage(): JSX.Element {
  const [cert, setCert] = useState<P85PlatformCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setCert(await apiClient.getPlatformCertification());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Certification check failed.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8">
        <CollectorErrorState title="Certification unavailable" message={error} onRetry={() => void load()} />
      </div>
    );
  }

  if (!cert) {
    return <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-400">Running platform certification…</div>;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl">
          <h1 className="text-xl font-semibold">Platform certification</h1>
          <p className="mt-1 text-sm text-slate-400">{cert.title}</p>
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6 text-sm">
        <p className="text-lg font-medium text-emerald-300">{cert.status}</p>
        <p>
          Readiness {cert.readiness_score.toFixed(1)}% · Passed {cert.checks_passed} · Failures {cert.failures}
        </p>
        <ul className="space-y-2">
          {cert.categories.map((c) => (
            <li key={c.category} className="flex justify-between rounded border border-slate-800 px-3 py-2">
              <span>{c.category}</span>
              <span className={c.passed ? "text-emerald-400" : "text-red-400"}>{c.status}</span>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
