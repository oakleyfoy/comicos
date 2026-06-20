import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchVisionSandboxMetrics, type PhotoImportVisionSandboxMetrics } from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

export function PhotoImportVisionSandboxDashboardPage(): JSX.Element {
  const [metrics, setMetrics] = useState<PhotoImportVisionSandboxMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchVisionSandboxMetrics()
      .then(setMetrics)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load metrics"));
  }, []);

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-4 py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Operations</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Vision Sandbox Dashboard</h1>
        <p className="mt-2 text-slate-600">GPT-only photo reads — no catalog matching.</p>
        {error ? <p className="mt-4 text-red-700">{error}</p> : null}
        {metrics ? (
          <div className="mt-8 space-y-8">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Total reads", metrics.total_reads],
                ["Correct", metrics.correct_reads],
                ["Incorrect", metrics.incorrect_reads],
                ["Accuracy", `${metrics.accuracy_percent}%`],
              ].map(([label, val]) => (
                <div key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs uppercase text-slate-500">{label}</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-900">{val}</p>
                </div>
              ))}
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Publisher filled", `${metrics.publisher_filled_percent ?? metrics.publisher_accuracy}%`],
                ["Series filled", `${metrics.series_filled_percent ?? metrics.series_accuracy}%`],
                ["Issue # filled", `${metrics.issue_number_filled_percent ?? metrics.issue_accuracy}%`],
                [
                  "Avg confidence",
                  metrics.average_confidence != null ? `${metrics.average_confidence}%` : "—",
                ],
              ].map(([label, val]) => (
                <div key={String(label)} className="rounded-xl bg-indigo-50 p-4">
                  <p className="text-xs uppercase text-indigo-800">{label}</p>
                  <p className="mt-1 text-xl font-semibold text-indigo-950">{val}</p>
                </div>
              ))}
            </div>
            {metrics.top_uncertain_reads && metrics.top_uncertain_reads.length > 0 ? (
              <section>
                <h2 className="text-lg font-semibold text-slate-900">Top uncertain reads</h2>
                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                  {metrics.top_uncertain_reads.map((row) => (
                    <li key={String(row.read_id)} className="rounded-lg border border-slate-100 p-2">
                      {String(row.publisher ?? "?")} · {String(row.series ?? "?")} #
                      {String(row.issue_number ?? "?")} — conf {String(row.confidence ?? "?")}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {metrics.latest_incorrect_reads && metrics.latest_incorrect_reads.length > 0 ? (
              <section>
                <h2 className="text-lg font-semibold text-slate-900">Latest incorrect reads</h2>
                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                  {metrics.latest_incorrect_reads.map((row) => (
                    <li key={String(row.read_id)} className="rounded-lg border border-red-100 p-2">
                      {String(row.publisher ?? "?")} · {String(row.series ?? "?")} #
                      {String(row.issue_number ?? "?")} — {String(row.feedback_notes ?? "no notes")}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            <section>
              <h2 className="text-lg font-semibold text-slate-900">Most misidentified series</h2>
              <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
                {metrics.most_misidentified_series.length === 0 ? (
                  <li>None yet</li>
                ) : (
                  metrics.most_misidentified_series.map((row) => (
                    <li key={row.series}>
                      {row.series} ({row.count})
                    </li>
                  ))
                )}
              </ul>
            </section>
            <section>
              <h2 className="text-lg font-semibold text-slate-900">Most misidentified publishers</h2>
              <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
                {metrics.most_misidentified_publishers.length === 0 ? (
                  <li>None yet</li>
                ) : (
                  metrics.most_misidentified_publishers.map((row) => (
                    <li key={row.publisher}>
                      {row.publisher} ({row.count})
                    </li>
                  ))
                )}
              </ul>
            </section>
            <section>
              <h2 className="text-lg font-semibold text-slate-900">Top failures</h2>
              <ul className="mt-2 space-y-2 text-sm text-slate-700">
                {metrics.top_failures.length === 0 ? (
                  <li>None yet</li>
                ) : (
                  metrics.top_failures.map((row) => (
                    <li key={String(row.read_id)} className="rounded-lg border border-slate-100 p-2">
                      {String(row.publisher ?? "?")} · {String(row.series ?? "?")} #
                      {String(row.issue_number ?? "?")} — {String(row.feedback_notes ?? "no notes")}
                    </li>
                  ))
                )}
              </ul>
            </section>
          </div>
        ) : null}
        <p className="mt-10">
          <Link to="/ops" className="text-indigo-600 underline">
            Back to operations
          </Link>
        </p>
      </div>
    </AppShell>
  );
}
