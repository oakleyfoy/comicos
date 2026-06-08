import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type P90AdvisorActionRead,
  type P90AdvisorSignalDiagnosticsRead,
  type P90AdvisorTodayActionRead,
  type P90CollectorAdvisorDashboardRead,
  type P90CollectorAdvisorSnapshotRead,
  type P90PortfolioImpactRead,
} from "../api/client";
import { resolveAdvisorBuyCta } from "../features/buyOpportunities/buyVerifiedAction";
import { advisorBuyBadge, advisorBuyMetrics } from "../features/buyOpportunities/buyRecommendationTrust";
import { useAuth } from "../auth/AuthContext";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import {
  actionValueMetric,
  categoryRecommendationLabel,
  cleanActionTitle,
  cleanTodayActionTitle,
  planHasEmptySecondarySections,
  resolveActionEvidence,
} from "./advisorRecommendationPresentation";
import { CollectorAdvisorEmptyState } from "./CollectorAdvisorEmptyState";
import {
  COLLECTOR_ADVISOR_EMPTY_SECTIONS_MESSAGE,
  COLLECTOR_ADVISOR_GENERATE_PLAN_CTA,
  COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_COLLECTION,
  COLLECTOR_ADVISOR_NO_OPPORTUNITY_VALUE,
  COLLECTOR_ADVISOR_OPPORTUNITY_VALUE_TITLE,
  COLLECTOR_ADVISOR_PAGE_DESCRIPTION,
  COLLECTOR_ADVISOR_STATUS,
  COLLECTOR_ADVISOR_TODAYS_BEST_ACTIONS_TITLE,
} from "./collectorAdvisorPresentation";

function money(value: number): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

function CategoryPill({ category }: { category: string }): JSX.Element {
  return (
    <span className="rounded-full border border-blue-300 bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-800">
      {category}
    </span>
  );
}

function RecommendationCard({ action }: { action: P90AdvisorActionRead }): JSX.Element {
  const title = cleanActionTitle(action);
  const evidence = resolveActionEvidence(action);
  const value = actionValueMetric(action);
  const buyCta = action.category.toUpperCase() === "BUY" ? resolveAdvisorBuyCta(action) : null;
  const subtext = buyCta?.subtext ?? categoryRecommendationLabel(action.category);
  const isBuy = action.category.toUpperCase() === "BUY";
  const metrics = isBuy ? advisorBuyMetrics(action) : [];
  const searchHref =
    isBuy && !buyCta?.external
      ? `/buy-opportunities?search=${encodeURIComponent(title)}`
      : null;

  return (
    <li className="rounded-lg border border-blue-200 bg-white px-4 py-3 text-sm shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {isBuy ? (
            <span className="mb-1 inline-block rounded-full bg-red-700 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
              {advisorBuyBadge(action)}
            </span>
          ) : null}
          <p className="text-base font-semibold text-blue-950">{title}</p>
          <p className="mt-0.5 text-xs text-blue-600">{subtext}</p>
          {evidence.primary ? <p className="mt-2 font-medium text-blue-900">{evidence.primary}</p> : null}
          {metrics.length ? (
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-3">
              {metrics.map((m) => (
                <div key={m.label}>
                  <dt className="text-blue-600">{m.label}</dt>
                  <dd className="font-medium text-blue-950">{m.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {evidence.supporting.length ? (
            <p className="mt-1 text-blue-800">{evidence.supporting.join(" · ")}</p>
          ) : null}
          {action.recommended_action ? (
            <p className="mt-2 text-xs text-blue-700">{action.recommended_action}</p>
          ) : null}
          <p className="mt-2 text-xs text-blue-600">
            Priority {action.priority_score.toFixed(0)} · {action.confidence} confidence
            {value
              ? ` · ${value.label}: ${
                  value.label.toLowerCase().includes("discount")
                    ? `${Math.round(value.amount)}%`
                    : money(value.amount)
                }`
              : ""}
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
        {buyCta ? (
          buyCta.external ? (
            <a
              href={buyCta.href}
              target="_blank"
              rel="noreferrer"
              className="rounded-md border border-red-700 bg-red-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-800"
            >
              {buyCta.label}
            </a>
          ) : (
            <Link
              to={buyCta.href}
              className="rounded-md border border-red-700 px-3 py-1.5 text-xs font-semibold text-red-800 hover:bg-red-50"
            >
              {buyCta.label}
            </Link>
          )
        ) : action.action_route ? (
          <Link
            to={action.action_route}
            className="rounded-md border border-red-700 px-3 py-1.5 text-xs font-semibold text-red-800 hover:bg-red-50"
          >
            View
          </Link>
        ) : null}
        {searchHref && buyCta && !buyCta.external ? (
          <Link to={searchHref} className="text-center text-xs font-medium text-blue-800 hover:underline">
            Search Marketplaces
          </Link>
        ) : null}
        </div>
      </div>
    </li>
  );
}

function ActionList({ title, rows }: { title: string; rows: P90AdvisorActionRead[] }): JSX.Element {
  return (
    <PatriotPanel title={title} className="mt-4">
      <ul className="space-y-3">
        {rows.map((row) => (
          <RecommendationCard key={`${row.category}-${row.comic}-${row.action_route}`} action={row} />
        ))}
      </ul>
    </PatriotPanel>
  );
}

function TodaysBestActions({ actions }: { actions: P90AdvisorTodayActionRead[] }): JSX.Element {
  const top = actions.slice(0, 5);
  return (
    <PatriotPanel title={COLLECTOR_ADVISOR_TODAYS_BEST_ACTIONS_TITLE} id="advisor-todays-actions">
      {top.length === 0 ? (
        <p className="text-sm text-blue-800">No ranked actions in today&apos;s plan yet.</p>
      ) : (
        <ol className="space-y-3">
          {top.map((action) => {
            const title = cleanTodayActionTitle(action);
            const value = actionValueMetric(action);
            const buyCta =
              action.category.toUpperCase() === "BUY"
                ? resolveAdvisorBuyCta({
                    category: "BUY",
                    comic: title,
                    display_label: title,
                    reason: action.detail,
                    confidence: "MEDIUM",
                    priority_score: action.priority_score,
                    action_url: action.action_url || action.action_route,
                    action_route: action.action_route,
                    action_url_type: action.action_url_type || "OPPORTUNITY_DETAIL",
                    has_verified_listing: Boolean(action.has_verified_listing),
                    marketplace_name: action.marketplace_name ?? undefined,
                  })
                : null;
            return (
              <li key={action.rank} className="flex gap-3 rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-3">
                <span className="text-lg font-semibold text-red-700">{action.rank}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-blue-950">{title}</p>
                    {action.action_pill ? (
                      <span className="rounded-full border border-red-300 bg-red-50 px-2 py-0.5 text-[10px] font-bold uppercase text-red-800">
                        {action.action_pill}
                      </span>
                    ) : (
                      <CategoryPill category={action.category} />
                    )}
                  </div>
                  {action.detail ? <p className="mt-1 text-sm text-blue-800">{action.detail}</p> : null}
                  {value ? (
                    <p className="mt-1 text-xs text-blue-700">
                      {value.label}:{" "}
                      {value.label.toLowerCase().includes("discount")
                        ? `${Math.round(value.amount)}%`
                        : money(value.amount)}
                    </p>
                  ) : null}
                </div>
                {buyCta && action.category.toUpperCase() === "BUY" ? (
                  buyCta.external ? (
                    <a
                      href={buyCta.href}
                      target="_blank"
                      rel="noreferrer"
                      className="self-center rounded-md border border-red-700 bg-red-700 px-2 py-1 text-xs font-semibold text-white hover:bg-red-800"
                    >
                      {buyCta.label}
                    </a>
                  ) : (
                    <Link
                      to={buyCta.href}
                      className="self-center rounded-md border border-blue-800 px-2 py-1 text-xs font-semibold text-blue-900 hover:bg-white"
                    >
                      Go
                    </Link>
                  )
                ) : (
                  <Link
                    to={action.action_route || "/automation-center"}
                    className="self-center rounded-md border border-blue-800 px-2 py-1 text-xs font-semibold text-blue-900 hover:bg-white"
                  >
                    Go
                  </Link>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </PatriotPanel>
  );
}

function OpportunityValuePanel({ impact }: { impact: P90PortfolioImpactRead }): JSX.Element {
  const allZero =
    impact.potential_profit === 0 &&
    impact.potential_savings === 0 &&
    impact.potential_value_gain === 0 &&
    impact.portfolio_impact_total === 0;

  return (
    <PatriotPanel title={COLLECTOR_ADVISOR_OPPORTUNITY_VALUE_TITLE} className="mt-4">
      {allZero ? (
        <p className="text-sm text-blue-800">{COLLECTOR_ADVISOR_NO_OPPORTUNITY_VALUE}</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
            <p className="text-xs uppercase text-blue-600">Potential savings</p>
            <p className="text-lg font-semibold text-blue-950">{money(impact.potential_savings)}</p>
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
            <p className="text-xs uppercase text-blue-600">Potential profit</p>
            <p className="text-lg font-semibold text-blue-950">{money(impact.potential_profit)}</p>
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
            <p className="text-xs uppercase text-blue-600">Grade upside</p>
            <p className="text-lg font-semibold text-blue-950">{money(impact.potential_value_gain)}</p>
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50/40 px-3 py-2">
            <p className="text-xs uppercase text-blue-600">Total opportunity</p>
            <p className="text-lg font-semibold text-blue-950">{money(impact.portfolio_impact_total)}</p>
          </div>
        </div>
      )}
    </PatriotPanel>
  );
}

function AdvisorDiagnosticsFooter({ diag }: { diag: P90AdvisorSignalDiagnosticsRead }): JSX.Element {
  const buySignals = diag.marketplace_opportunity_count + diag.marketplace_alert_count + diag.automation_alert_count;
  const alerts = diag.marketplace_alert_count + diag.discovery_alert_count + diag.automation_alert_count;
  return (
    <PatriotPanel title="Signals found (ops)" className="mt-4 border-dashed border-amber-400/60">
      <div data-testid="advisor-ops-diagnostics">
        <ul className="space-y-1 text-sm text-blue-900">
        <li>Inventory: {diag.inventory_count}</li>
        <li>Buy opportunities: {buySignals}</li>
        <li>Sell candidates: {diag.sell_candidate_count}</li>
        <li>Alerts: {alerts}</li>
        </ul>
      </div>
    </PatriotPanel>
  );
}

function CollapsedEmptySections(): JSX.Element {
  return (
    <p className="mt-4 rounded-lg border border-blue-200 bg-blue-50/30 px-4 py-3 text-sm text-blue-800">
      {COLLECTOR_ADVISOR_EMPTY_SECTIONS_MESSAGE}
    </p>
  );
}

function AdvisorPlanBody({ plan, status }: { plan: P90CollectorAdvisorSnapshotRead; status: string }): JSX.Element {
  const collapseSecondary = planHasEmptySecondarySections(plan);
  const showBuy = plan.buy_actions.length > 0;
  const isEmptySignals = status === COLLECTOR_ADVISOR_STATUS.EMPTY_NO_SIGNALS;

  return (
    <>
      <TodaysBestActions actions={plan.todays_actions} />
      {plan.portfolio_impact ? <OpportunityValuePanel impact={plan.portfolio_impact} /> : null}

      {showBuy ? <ActionList title="Buy" rows={plan.buy_actions} /> : null}

      {!isEmptySignals && collapseSecondary ? <CollapsedEmptySections /> : null}

      {!collapseSecondary && plan.sell_actions.length > 0 ? (
        <ActionList title="Sell" rows={plan.sell_actions} />
      ) : null}
      {!collapseSecondary && plan.grade_actions.length > 0 ? (
        <ActionList title="Grade" rows={plan.grade_actions} />
      ) : null}
      {!collapseSecondary && plan.watch_actions.length > 0 ? (
        <ActionList title="Watch" rows={plan.watch_actions} />
      ) : null}

      {!collapseSecondary && plan.market_alerts.length > 0 ? (
        <PatriotPanel title="Market alerts" className="mt-4">
          <ul className="space-y-1 text-sm text-blue-900">
            {plan.market_alerts.map((row, i) => (
              <li key={`${row.title}-${i}`}>
                <span className="font-medium">{row.title}</span>
                {row.detail ? <span className="text-blue-700"> — {row.detail}</span> : null}
              </li>
            ))}
          </ul>
        </PatriotPanel>
      ) : null}

      {!collapseSecondary && plan.recent_activity.length > 0 ? (
        <PatriotPanel title="Recent activity" className="mt-4">
          <ul className="space-y-1 text-sm text-blue-900">
            {plan.recent_activity.map((row, i) => (
              <li key={`${row.activity_type}-${i}`}>
                <span className="text-xs uppercase text-blue-600">{row.activity_type.replace(/_/g, " ")}</span>
                {" · "}
                <span className="font-medium">{row.title}</span>
              </li>
            ))}
          </ul>
        </PatriotPanel>
      ) : null}

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
  );
}

export function AutomationCenterPage(): JSX.Element {
  const { isOpsAdmin } = useAuth();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<P90CollectorAdvisorDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const showOpsDiagnostics = isOpsAdmin && searchParams.get("debug") === "1";

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
  const status = data?.status ?? "";
  const showNoSnapshotIntro = status === COLLECTOR_ADVISOR_STATUS.NO_SNAPSHOT;
  const showGatherFailedIntro = status === COLLECTOR_ADVISOR_STATUS.EMPTY_GATHER_FAILED && !plan;
  const emptyPlanMessage = data?.message?.trim() ?? "";
  const bannerTone =
    status === COLLECTOR_ADVISOR_STATUS.EMPTY_NO_SIGNALS
      ? "border-emerald-300 bg-emerald-50/95 text-emerald-950"
      : status === COLLECTOR_ADVISOR_STATUS.EMPTY_GATHER_FAILED
        ? "border-amber-300 bg-amber-50/95 text-amber-950"
        : "border-blue-300 bg-white/90 text-blue-950";

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
          <button
            type="button"
            disabled={generating}
            onClick={() => void handleGenerate()}
            className="rounded-md border border-white/40 bg-white/10 px-3 py-1.5 text-sm font-semibold text-white hover:bg-white/20 disabled:opacity-60"
          >
            {generating ? "Generating…" : COLLECTOR_ADVISOR_GENERATE_PLAN_CTA}
          </button>
        ) : null
      }
    >
      {generateError ? <p className="mb-4 text-sm text-red-200">{generateError}</p> : null}

      {showNoSnapshotIntro ? (
        <CollectorAdvisorEmptyState
          onGenerate={() => void handleGenerate()}
          generating={generating}
          generateError={generateError}
          variant="no_snapshot"
        />
      ) : null}

      {showGatherFailedIntro ? (
        <CollectorAdvisorEmptyState
          onGenerate={() => void handleGenerate()}
          generating={generating}
          generateError={generateError}
          variant="gather_failed"
        />
      ) : null}

      {plan ? (
        <>
          {emptyPlanMessage ? (
            <p
              className={`rounded-lg border px-4 py-3 text-sm ${bannerTone}`}
              data-testid="collector-advisor-status-banner"
            >
              {emptyPlanMessage}
            </p>
          ) : null}
          {status === COLLECTOR_ADVISOR_STATUS.EMPTY_GATHER_FAILED ? (
            <button
              type="button"
              data-testid="collector-advisor-retry"
              disabled={generating}
              onClick={() => void handleGenerate()}
              className="mb-4 rounded-md border border-amber-800 bg-amber-800 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-900 disabled:opacity-60"
            >
              {generating ? "Building your plan…" : "Try Again"}
            </button>
          ) : null}
          {status === COLLECTOR_ADVISOR_STATUS.EMPTY_NO_COLLECTION ? (
            <p className="mb-4 text-sm">
              <Link to="/order-import" className="font-semibold text-red-200 underline hover:text-white">
                Import comics
              </Link>{" "}
              to unlock personalized recommendations.
            </p>
          ) : null}
          <AdvisorPlanBody plan={plan} status={status} />
          {showOpsDiagnostics && data?.signal_diagnostics ? (
            <AdvisorDiagnosticsFooter diag={data.signal_diagnostics} />
          ) : null}
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
