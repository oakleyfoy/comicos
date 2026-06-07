import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P84CollectorCommandCenterRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { CollectorErrorState } from "../components/CollectorErrorState";

function SectionCard({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <section className={`rounded-lg border border-blue-800 bg-white px-4 py-3 text-blue-950 shadow-sm ${className}`}>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-red-700">{title}</h2>
      <div className="mt-2 text-sm text-blue-900">{children}</div>
    </section>
  );
}

function itemTitle(item: Record<string, unknown>): string {
  const t = item.title;
  return typeof t === "string" ? t : "—";
}

export function CollectorCommandCenterPage(): JSX.Element {
  const [cc, setCc] = useState<P84CollectorCommandCenterRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setCc(await apiClient.getCollectorCommandCenter());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load command center.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const shellBody = (content: ReactNode) => (
    <AppShell>
      <div className="rounded-xl bg-blue-950 text-white">{content}</div>
    </AppShell>
  );

  if (error && !cc) {
    return shellBody(
      <div className="px-4 py-8">
        <div className="mx-auto max-w-5xl">
          <CollectorErrorState message={error} onRetry={() => void load()} />
        </div>
      </div>,
    );
  }

  if (!cc) {
    return shellBody(
      <div className="px-4 py-8 text-blue-100">
        <p>Loading command center…</p>
      </div>,
    );
  }

  const loadStatus = (cc as P84CollectorCommandCenterRead & { status?: string; message?: string }).status;
  const loadMessage = (cc as P84CollectorCommandCenterRead & { status?: string; message?: string }).message;
  const portfolioValue = Number(cc.portfolio_movement?.current_value ?? cc.collection_forecast?.current_value ?? 0);
  const budgetState = String(cc.budget_status?.state ?? "—");
  const riskCategory = String(cc.portfolio_movement?.risk_category ?? "—");

  return shellBody(
    <>
      <header className="border-b border-red-700 bg-gradient-to-r from-blue-950 via-blue-900 to-red-900 px-4 py-6">
        <div className="mx-auto max-w-5xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-red-200">P82–P84 · Command center</p>
          <h1 className="text-2xl font-semibold text-white">Collector command center</h1>
          <p className="text-sm text-blue-100">
            Budget {budgetState} · Portfolio ${portfolioValue.toFixed(0)} · Risk {riskCategory}
          </p>
          {loadStatus && loadStatus !== "OK" && loadMessage ? (
            <p className="rounded-md border border-red-400/50 bg-white/10 px-3 py-2 text-sm text-red-100">{loadMessage}</p>
          ) : null}
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        {error ? (
          <div className="rounded-lg border border-red-600 bg-red-950/40 px-4 py-3">
            <CollectorErrorState message={error} onRetry={() => void load()} />
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <SectionCard title="Collection forecast">
            <p className="text-2xl font-semibold text-blue-950">
              ${cc.collection_forecast?.current_value.toFixed(2) ?? "—"}
            </p>
            <Link to="/collection-forecast" className="mt-2 inline-block text-sm font-medium text-red-700 hover:text-red-900 hover:underline">
              Open forecast
            </Link>
          </SectionCard>

          <SectionCard title="Budget">
            <p className="text-lg font-semibold capitalize text-blue-950">{budgetState}</p>
            {cc.budget_status?.monthly_budget != null ? (
              <p className="mt-1 text-blue-800">Monthly ${Number(cc.budget_status.monthly_budget).toFixed(0)}</p>
            ) : null}
            <Link to="/collector-budget" className="mt-2 inline-block text-sm font-medium text-red-700 hover:text-red-900 hover:underline">
              Budget settings
            </Link>
          </SectionCard>

          <SectionCard title="Portfolio movement">
            <p className="text-lg font-semibold text-blue-950">${portfolioValue.toFixed(2)}</p>
            <p className="text-blue-800">Risk: {riskCategory}</p>
          </SectionCard>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <SectionCard title="Marketplace deals">
            {cc.marketplace_deals.length === 0 ? (
              <p className="text-blue-700">
                <Link to="/buy-opportunities" className="font-medium text-red-700 hover:underline">
                  Buy opportunities
                </Link>
              </p>
            ) : (
              <ul className="space-y-1">
                {cc.marketplace_deals.slice(0, 8).map((d) => (
                  <li key={d.id}>
                    <Link to={`/marketplace-opportunity/${d.id}`} className="font-medium text-red-700 hover:text-red-900 hover:underline">
                      {d.title}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Top buy opportunities">
            {cc.top_buy_opportunities.length === 0 ? (
              <p className="text-blue-700">No cached buy opportunities.</p>
            ) : (
              <ul className="space-y-1">
                {cc.top_buy_opportunities.slice(0, 8).map((d) => (
                  <li key={d.id}>
                    <Link to={`/marketplace-opportunity/${d.id}`} className="font-medium text-red-700 hover:text-red-900 hover:underline">
                      {d.title}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Top sell opportunities">
            {cc.top_sell_opportunities.length === 0 ? (
              <p className="text-blue-700">
                <Link to="/sell-queue" className="font-medium text-red-700 hover:underline">
                  Open sell queue
                </Link>
              </p>
            ) : (
              <ul className="space-y-1">
                {cc.top_sell_opportunities.slice(0, 8).map((row, idx) => (
                  <li key={idx}>{itemTitle(row)}</li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Upcoming FOC">
            {cc.upcoming_foc.length === 0 ? (
              <p className="text-blue-700">
                <Link to="/future-pull-list" className="font-medium text-red-700 hover:underline">
                  Future pull list
                </Link>
              </p>
            ) : (
              <ul className="space-y-1">
                {cc.upcoming_foc.slice(0, 8).map((row, idx) => (
                  <li key={idx}>{itemTitle(row)}</li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Risk alerts" className="md:col-span-2">
            {cc.risk_alerts.length === 0 ? (
              <p className="text-blue-700">No portfolio risk alerts.</p>
            ) : (
              <ul className="space-y-2">
                {cc.risk_alerts.map((n) => (
                  <li key={n.id} className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-950">
                    <span className="font-medium">{n.title}</span>
                    <p className="text-sm text-red-900">{n.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Daily briefing actions" className="md:col-span-2">
            {(cc.daily_briefing?.top_actions.length ?? 0) === 0 ? (
              <p className="text-blue-700">
                <Link to="/daily-briefing" className="font-medium text-red-700 hover:underline">
                  Open daily briefing
                </Link>
              </p>
            ) : (
              <ul className="list-disc space-y-1 pl-5">
                {cc.daily_briefing?.top_actions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Discovery alerts">
            {cc.discovery_alerts.length === 0 ? (
              <p className="text-blue-700">
                <Link to="/discovery-dashboard" className="font-medium text-red-700 hover:underline">
                  Discovery dashboard
                </Link>
              </p>
            ) : (
              <ul className="space-y-1">
                {cc.discovery_alerts.slice(0, 6).map((row, idx) => (
                  <li key={idx}>{itemTitle(row)}</li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Grading candidates">
            {cc.grading_candidates.length === 0 ? (
              <p className="text-blue-700">No cached grading candidates.</p>
            ) : (
              <ul className="space-y-1">
                {cc.grading_candidates.slice(0, 6).map((row, idx) => (
                  <li key={idx}>{itemTitle(row)}</li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>

        <p className="text-xs text-blue-200">
          <Link to="/collector-home" className="text-red-200 hover:text-white hover:underline">
            Collector home
          </Link>
          {" · "}
          <Link to="/workflow-health" className="text-red-200 hover:text-white hover:underline">
            Workflow health
          </Link>
        </p>
      </main>
    </>,
  );
}
