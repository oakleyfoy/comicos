import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type P90AdvisorActionRead,
  type P90CollectorAdvisorDashboardRead,
} from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { CollectorAdvisorEmptyState } from "./CollectorAdvisorEmptyState";
import {
  COLLECTOR_ADVISOR_OPEN_PLAN_CTA,
  COLLECTOR_ADVISOR_PAGE_DESCRIPTION,
} from "./collectorAdvisorPresentation";

function money(value: number): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function ActionList({ title, rows, empty }: { title: string; rows: P90AdvisorActionRead[]; empty: string }): JSX.Element {
  return (
    <PatriotPanel title={title} className="mt-4">
      {rows.length === 0 ? (
        <p className="text-sm text-blue-800">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row, idx) => (
            <li key={`${row.display_label}-${idx}`} className="rounded border border-blue-200 bg-white px-3 py-2 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-blue-950">{row.display_label || row.comic}</p>
                  <p className="text-blue-800">{row.reason}</p>
                  <p className="mt-1 text-xs text-blue-600">
                    {row.confidence} confidence · priority {row.priority_score.toFixed(0)}
                    {row.potential_upside != null ? ` · upside ${money(row.potential_upside)}` : ""}
                    {row.profit_potential != null ? ` · profit ${money(row.profit_potential)}` : ""}
                    {row.value_increase != null ? ` · value +${money(row.value_increase)}` : ""}
                  </p>
                </div>
                {row.action_route ? (
                  <Link
                    to={row.action_route}
                    className="shrink-0 rounded border border-red-700 px-2 py-1 text-xs font-semibold text-red-800 hover:bg-red-50"
                  >
                    Go
                  </Link>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </PatriotPanel>
  );
}

export function AutomationCenterPage(): JSX.Element {
  const [data, setData] = useState<P90CollectorAdvisorDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setData(await apiClient.getCollectorAdvisor());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load Collector Advisor.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleGenerate = useCallback(async () => {
    setGenerateError(null);
    setGenerating(true);
    try {
      const next = await apiClient.generateCollectorAdvisor();
      setData(next);
    } catch (err) {
      setGenerateError(err instanceof ApiError ? err.message : "Unable to generate your advisor plan. Try again.");
    } finally {
      setGenerating(false);
    }
  }, []);

  const plan = data?.plan;
  const impact = plan?.portfolio_impact;
  const showEmpty = data?.status === "EMPTY" || !plan;

  return (
    <PatriotPageLayout
      eyebrow="Home"
      title="Collector Advisor"
      description={COLLECTOR_ADVISOR_PAGE_DESCRIPTION}
      error={error}
      onRetry={() => void load()}
      loading={loading && !data}
      maxWidthClass="max-w-5xl"
      headerActions={
        plan ? (
          <a
            href="#advisor-todays-actions"
            className="rounded-md border border-white/40 bg-white/10 px-3 py-1.5 text-sm font-semibold text-white hover:bg-white/20"
          >
            {COLLECTOR_ADVISOR_OPEN_PLAN_CTA}
          </a>
        ) : null
      }
    >
      {showEmpty && data ? (
        <CollectorAdvisorEmptyState
          onGenerate={() => void handleGenerate()}
          generating={generating}
          generateError={generateError}
        />
      ) : null}

      {plan ? (
        <>
          <PatriotPanel title="Today's actions" id="advisor-todays-actions">
            {plan.todays_actions.length === 0 ? (
              <p className="text-sm text-blue-800">No ranked actions in today&apos;s plan yet.</p>
            ) : (
              <ol className="space-y-2">
                {plan.todays_actions.map((action) => (
                  <li key={action.rank} className="flex gap-3 rounded border border-blue-200 bg-blue-50/30 px-3 py-2">
                    <span className="text-lg font-semibold text-red-700">{action.rank}</span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-blue-950">{action.title}</p>
                      {action.detail ? <p className="text-sm text-blue-800">{action.detail}</p> : null}
                      <p className="text-xs text-blue-600">
                        {action.category} · priority {action.priority_score.toFixed(0)}
                      </p>
                    </div>
                    <Link
                      to={action.action_route || "/automation-center"}
                      className="self-center rounded border border-blue-800 px-2 py-1 text-xs font-semibold text-blue-900 hover:bg-white"
                    >
                      Go
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </PatriotPanel>

          {impact ? (
            <PatriotPanel title="Portfolio impact" className="mt-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
                  <p className="text-xs uppercase text-blue-600">Potential profit</p>
                  <p className="text-lg font-semibold text-blue-950">{money(impact.potential_profit)}</p>
                </div>
                <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
                  <p className="text-xs uppercase text-blue-600">Potential savings</p>
                  <p className="text-lg font-semibold text-blue-950">{money(impact.potential_savings)}</p>
                </div>
                <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
                  <p className="text-xs uppercase text-blue-600">Value gain (grade)</p>
                  <p className="text-lg font-semibold text-blue-950">{money(impact.potential_value_gain)}</p>
                </div>
                <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
                  <p className="text-xs uppercase text-blue-600">Total impact</p>
                  <p className="text-lg font-semibold text-blue-950">{money(impact.portfolio_impact_total)}</p>
                </div>
              </div>
            </PatriotPanel>
          ) : null}

          <ActionList title="Buy" rows={plan.buy_actions} empty="No buy recommendations in this plan." />
          <ActionList title="Sell" rows={plan.sell_actions} empty="No sell recommendations in this plan." />
          <ActionList title="Grade" rows={plan.grade_actions} empty="No grade recommendations in this plan." />
          <ActionList title="Watch" rows={plan.watch_actions} empty="No watch recommendations in this plan." />

          <PatriotPanel title="Market alerts" className="mt-4">
            {plan.market_alerts.length === 0 ? (
              <p className="text-sm text-blue-800">No marketplace alerts in this plan.</p>
            ) : (
              <ul className="space-y-1 text-sm text-blue-900">
                {plan.market_alerts.map((row, i) => (
                  <li key={`${row.title}-${i}`}>
                    <span className="font-medium">{row.title}</span>
                    {row.detail ? <span className="text-blue-700"> — {row.detail}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Recent activity" className="mt-4">
            {plan.recent_activity.length === 0 ? (
              <p className="text-sm text-blue-800">No recent collection activity in this plan.</p>
            ) : (
              <ul className="space-y-1 text-sm text-blue-900">
                {plan.recent_activity.map((row, i) => (
                  <li key={`${row.activity_type}-${i}`}>
                    <span className="text-xs uppercase text-blue-600">{row.activity_type.replace(/_/g, " ")}</span>
                    {" · "}
                    <span className="font-medium">{row.title}</span>
                  </li>
                ))}
              </ul>
            )}
          </PatriotPanel>

          <PatriotPanel title="Quick links" className="mt-4">
            <ul className="flex flex-wrap gap-2 text-sm">
              <li>
                <Link to="/buy-opportunities" className="rounded border border-blue-800 px-3 py-1.5 text-blue-900 hover:bg-blue-50">
                  Buy Opportunities
                </Link>
              </li>
              <li>
                <Link to="/sell-command-center" className="rounded border border-blue-800 px-3 py-1.5 text-blue-900 hover:bg-blue-50">
                  Sell Command Center
                </Link>
              </li>
              <li>
                <Link to="/marketplace-command-center" className="rounded border border-blue-800 px-3 py-1.5 text-blue-900 hover:bg-blue-50">
                  Marketplace Command Center
                </Link>
              </li>
              <li>
                <Link to="/fmv-intelligence" className="rounded border border-blue-800 px-3 py-1.5 text-blue-900 hover:bg-blue-50">
                  FMV Intelligence
                </Link>
              </li>
            </ul>
          </PatriotPanel>
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
