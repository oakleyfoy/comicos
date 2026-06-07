import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P85CollectorHomeRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { CollectorErrorState } from "../components/CollectorErrorState";
import {
  buildCollectorHomeHeaderSummary,
  buildDashboardStrip,
  buildTodaysSummaryResult,
  COLLECTOR_HOME_TITLE,
  indicatorBadgeClassName,
  itemLabel,
  prepareCollectorHomeSections,
} from "./collectorHomePresentation";

export function CollectorHomePage(): JSX.Element {
  const [home, setHome] = useState<P85CollectorHomeRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setHome(await apiClient.getCollectorHome());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load collector home. Check your connection and try again.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <AppShell>
        <div className="rounded-lg bg-blue-950 px-4 py-8 text-white">
          <div className="mx-auto max-w-3xl">
            <CollectorErrorState message={error} onRetry={() => void load()} />
          </div>
        </div>
      </AppShell>
    );
  }

  if (!home) {
    return (
      <AppShell>
        <div className="rounded-lg bg-blue-950 px-4 py-8 text-blue-100">
          <p>Loading your collector home…</p>
        </div>
      </AppShell>
    );
  }

  const headerSummary = buildCollectorHomeHeaderSummary(home);
  const sections = prepareCollectorHomeSections(home.sections);
  const summary = buildTodaysSummaryResult(home.sections);
  const hasDailyActions = home.todays_actions.length > 0;
  const topActions = home.todays_actions.slice(0, 3);
  const dashboardStrip = buildDashboardStrip(home);
  const advisorUrl = home.advisor_primary_cta_url || "/automation-center";
  const advisorReady = Boolean(home.advisor_plan_ready);

  return (
    <AppShell>
      <div className="rounded-xl bg-blue-950 text-white">
        <header className="border-b border-red-700 bg-gradient-to-r from-blue-950 via-blue-900 to-red-900 px-4 py-6">
          <div className="mx-auto max-w-4xl">
            <h1 className="text-2xl font-semibold">{COLLECTOR_HOME_TITLE}</h1>
            <p className="mt-2 text-sm text-blue-100">{headerSummary}</p>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-6">
          <div
            className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4"
            data-testid="collector-home-dashboard-strip"
          >
            {dashboardStrip.map((metric) => (
              <div
                key={metric.label}
                className="rounded-lg border border-blue-800/80 bg-white/5 px-3 py-2"
              >
                <p className="text-xs uppercase tracking-wide text-blue-200">{metric.label}</p>
                <p className="mt-0.5 text-sm font-semibold text-white">{metric.value}</p>
              </div>
            ))}
          </div>

          <section
            aria-labelledby="collector-home-advisor-summary"
            className="mb-5 rounded-lg border border-blue-800/80 bg-white/5 px-4 py-3"
            data-testid="collector-home-advisor-summary"
          >
            <h2 id="collector-home-advisor-summary" className="text-sm font-semibold text-white">
              Collector Advisor
            </h2>
            <p className="mt-1 text-sm text-blue-100">
              {advisorReady
                ? "Your daily action plan is ready when generated."
                : "Your personalized daily action plan will appear here once advisor data has been generated."}
            </p>
            <p className="mt-2">
              <Link
                to={advisorUrl}
                className="inline-flex rounded-md border border-red-600/80 bg-red-900/40 px-3 py-1.5 text-sm font-medium text-red-100 hover:bg-red-800/50"
                data-testid="collector-home-advisor-cta"
              >
                Open Collector Advisor
              </Link>
            </p>
          </section>

          <section aria-labelledby="collector-home-todays-summary-heading" className="mb-5">
            <h2
              id="collector-home-todays-summary-heading"
              className="text-sm font-semibold uppercase tracking-wide text-red-200"
            >
              Today&apos;s Summary
            </h2>
            {hasDailyActions ? (
              <ul className="mt-2 space-y-1.5 text-sm">
                {topActions.map((a, i) => (
                  <li key={`${a.title}-${i}`} className="rounded border border-blue-700/80 bg-white/5 px-3 py-1.5">
                    <Link to={a.action_url || "/daily-actions"} className="text-red-200 hover:text-white hover:underline">
                      {a.title}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <>
                <ul
                  className="mt-2 space-y-0.5 text-sm text-blue-100"
                  data-testid="collector-home-todays-summary"
                >
                  {summary.lines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
                {summary.allCountsZero ? (
                  <p
                    className="mt-2 text-sm text-blue-200/90"
                    data-testid="collector-home-monitoring-message"
                  >
                    ComicOS is monitoring your collection. New opportunities will appear automatically.
                  </p>
                ) : null}
              </>
            )}
          </section>
          <div
            className="grid grid-cols-1 gap-5 md:grid-cols-2"
            data-testid="collector-home-section-grid"
          >
            {sections.map((sec) => (
              <section
                key={sec.key}
                className="flex h-full flex-col rounded-lg border border-blue-800 bg-white px-4 py-3 text-blue-950 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-sm font-semibold text-blue-950">{sec.title}</h2>
                  <span
                    className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${indicatorBadgeClassName(sec.indicatorTone)}`}
                  >
                    {sec.indicatorShowCheck ? <span aria-hidden="true">✓</span> : null}
                    {!sec.indicatorShowCheck && sec.indicatorTone === "empty" ? (
                      <span aria-hidden="true">○</span>
                    ) : null}
                    <span>{sec.indicatorText}</span>
                  </span>
                </div>
                {sec.showItems ? (
                  <ul className="mt-2 space-y-1 text-sm text-blue-900">
                    {sec.items.map((item, idx) => (
                      <li key={idx}>{itemLabel(item)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 line-clamp-2 flex-1 text-sm text-blue-700">{sec.body}</p>
                )}
                <p className="mt-auto pt-3 text-sm">
                  <Link
                    to={sec.actionTo}
                    className="inline-block rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-800"
                  >
                    {sec.actionLabel}
                  </Link>
                </p>
              </section>
            ))}
          </div>
        </main>
      </div>
    </AppShell>
  );
}
