import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  type AgentAnalyticsSummaryRead,
  ApiError,
  apiClient,
  type AgentDashboardSummaryResponse,
  type AgentHealthRead,
  type AgentPerformanceMetricRead,
  type AgentPlatformSummaryRead,
  type IntelligenceRecommendationDetail,
  type RecommendationOutcomeMetricRead,
  type RecommendationQueueListResponse,
  type RecommendationQueueRead,
  type RecentExecutionListResponse,
  type RecentExecutionRead,
  type WorkflowPerformanceMetricRead,
  type WorkflowHealthRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const EXECUTION_PAGE_SIZE = 10;
const RECOMMENDATION_PAGE_SIZE = 10;

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDuration(durationMs?: number | null): string {
  if (durationMs == null) return "—";
  if (durationMs < 1000) return `${durationMs} ms`;
  return `${(durationMs / 1000).toFixed(durationMs >= 10000 ? 0 : 1)} s`;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatCount(value: unknown): string {
  return typeof value === "number" ? String(value) : "—";
}

function summaryNumber(summary: Record<string, unknown>, key: string): number | null {
  const value = summary[key];
  return typeof value === "number" ? value : null;
}

function summaryRecord(summary: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = summary[key];
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function statusTone(status: string): string {
  switch (status) {
    case "PASS":
    case "HEALTHY":
    case "COMPLETED":
    case "OPEN":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
    case "RUNNING":
    case "PENDING":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAIL":
    case "FAILED":
    case "DISMISSED":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "ACCEPTED":
    case "REVIEWED":
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
    case "DISABLED":
      return "border-slate-500/30 bg-slate-500/10 text-slate-200";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function HealthBadge({ value }: { value: string }): JSX.Element {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(value)}`}>
      {value}
    </span>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function EmptyPanelState({ message }: { message: string }): JSX.Element {
  return <p className="text-sm text-slate-500">{message}</p>;
}

function AgentHealthTable({ rows }: { rows: AgentHealthRead[] }): JSX.Element {
  if (!rows.length) {
    return <EmptyPanelState message="No agent health rows are visible yet." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-white/10 text-sm">
        <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="pb-3 pr-4">Agent</th>
            <th className="pb-3 pr-4">Status</th>
            <th className="pb-3 pr-4">Success rate</th>
            <th className="pb-3 pr-4">Last run</th>
            <th className="pb-3 pr-4">Avg duration</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 text-slate-200">
          {rows.map((row) => (
            <tr key={row.agent_id}>
              <td className="py-3 pr-4">
                <div className="font-semibold text-white">{row.agent_name}</div>
                <div className="text-xs text-slate-500">{row.agent_code}</div>
              </td>
              <td className="py-3 pr-4">
                <HealthBadge value={row.health_status} />
              </td>
              <td className="py-3 pr-4">{formatPercent(row.success_rate)}</td>
              <td className="py-3 pr-4">{formatDateTime(row.last_run_at)}</td>
              <td className="py-3 pr-4">{formatDuration(row.average_duration_ms)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WorkflowHealthTable({ rows }: { rows: WorkflowHealthRead[] }): JSX.Element {
  if (!rows.length) {
    return <EmptyPanelState message="No workflow health rows are visible yet." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-white/10 text-sm">
        <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="pb-3 pr-4">Workflow</th>
            <th className="pb-3 pr-4">Status</th>
            <th className="pb-3 pr-4">Last run</th>
            <th className="pb-3 pr-4">Success rate</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5 text-slate-200">
          {rows.map((row) => (
            <tr key={row.workflow_id}>
              <td className="py-3 pr-4">
                <div className="font-semibold text-white">{row.workflow_name}</div>
                <div className="text-xs text-slate-500">{row.workflow_code}</div>
              </td>
              <td className="py-3 pr-4">
                <HealthBadge value={row.health_status} />
              </td>
              <td className="py-3 pr-4">{formatDateTime(row.last_run_at)}</td>
              <td className="py-3 pr-4">{formatPercent(row.success_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExecutionActivityPanel({
  rows,
  statusFilter,
  onStatusFilterChange,
  canGoBack,
  canGoForward,
  onPrevious,
  onNext,
}: {
  rows: RecentExecutionRead[];
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  canGoBack: boolean;
  canGoForward: boolean;
  onPrevious: () => void;
  onNext: () => void;
}): JSX.Element {
  return (
    <Panel title="Recent agent executions">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <span>Status</span>
          <select
            value={statusFilter}
            onChange={(event) => onStatusFilterChange(event.target.value)}
            className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          >
            <option value="">All</option>
            <option value="RUNNING">Running</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
          </select>
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onPrevious}
            disabled={!canGoBack}
            className="rounded-xl border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={!canGoForward}
            className="rounded-xl border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
      {!rows.length ? (
        <EmptyPanelState message="No agent executions match the current filters." />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
              <tr>
                <th className="pb-3 pr-4">Timestamp</th>
                <th className="pb-3 pr-4">Agent</th>
                <th className="pb-3 pr-4">Workflow</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {rows.map((row) => (
                <tr key={row.execution_id}>
                  <td className="py-3 pr-4">{formatDateTime(row.started_at)}</td>
                  <td className="py-3 pr-4">
                    <div className="font-semibold text-white">{row.agent_name}</div>
                    <div className="text-xs text-slate-500">{row.agent_code}</div>
                  </td>
                  <td className="py-3 pr-4">{row.workflow_name ?? "Standalone execution"}</td>
                  <td className="py-3 pr-4">
                    <HealthBadge value={row.status} />
                  </td>
                  <td className="py-3 pr-4">{formatDuration(row.duration_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function RecommendationQueuePanel({
  rows,
  selectedRecommendation,
  actionRecommendationId,
  canGoBack,
  canGoForward,
  onPrevious,
  onNext,
  onViewDetails,
  onReviewAction,
}: {
  rows: RecommendationQueueRead[];
  selectedRecommendation: IntelligenceRecommendationDetail | null;
  actionRecommendationId: number | null;
  canGoBack: boolean;
  canGoForward: boolean;
  onPrevious: () => void;
  onNext: () => void;
  onViewDetails: (recommendationId: number) => void;
  onReviewAction: (kind: "reviewed" | "dismissed" | "accepted", recommendationId: number) => void;
}): JSX.Element {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.35fr,0.65fr]">
      <Panel title="Recommendations awaiting review">
        <div className="mb-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onPrevious}
            disabled={!canGoBack}
            className="rounded-xl border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={!canGoForward}
            className="rounded-xl border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 disabled:opacity-40"
          >
            Next
          </button>
        </div>
        {!rows.length ? (
          <EmptyPanelState message="No open recommendations are waiting for review." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="text-left text-xs uppercase tracking-[0.14em] text-slate-500">
                <tr>
                  <th className="pb-3 pr-4">Recommendation type</th>
                  <th className="pb-3 pr-4">Confidence</th>
                  <th className="pb-3 pr-4">Opportunity</th>
                  <th className="pb-3 pr-4">Priority</th>
                  <th className="pb-3 pr-4">Created</th>
                  <th className="pb-3 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-200">
                {rows.map((row) => {
                  const busy = actionRecommendationId === row.recommendation_id;
                  return (
                    <tr key={row.recommendation_id}>
                      <td className="py-3 pr-4">
                        <div className="font-semibold text-white">{row.title}</div>
                        <div className="text-xs text-slate-500">{row.recommendation_type}</div>
                      </td>
                      <td className="py-3 pr-4">{formatPercent(row.confidence_score)}</td>
                      <td className="py-3 pr-4">{formatPercent(row.opportunity_score)}</td>
                      <td className="py-3 pr-4">{formatPercent(row.priority_score)}</td>
                      <td className="py-3 pr-4">{formatDateTime(row.created_at)}</td>
                      <td className="py-3 pr-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => onViewDetails(row.recommendation_id)}
                            className="rounded-xl border border-cyan-400/30 px-3 py-2 text-xs font-semibold text-cyan-100"
                          >
                            View Details
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => onReviewAction("reviewed", row.recommendation_id)}
                            className="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-100 disabled:opacity-50"
                          >
                            Mark Reviewed
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => onReviewAction("dismissed", row.recommendation_id)}
                            className="rounded-xl border border-rose-400/30 px-3 py-2 text-xs font-semibold text-rose-100 disabled:opacity-50"
                          >
                            Mark Dismissed
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => onReviewAction("accepted", row.recommendation_id)}
                            className="rounded-xl border border-emerald-400/30 px-3 py-2 text-xs font-semibold text-emerald-100 disabled:opacity-50"
                          >
                            Mark Accepted
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <Panel title="Recommendation details">
        {!selectedRecommendation ? (
          <EmptyPanelState message="Select a recommendation to inspect its evidence and review history." />
        ) : (
          <div className="space-y-4 text-sm text-slate-300">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                {selectedRecommendation.recommendation.recommendation_type}
              </p>
              <h3 className="mt-1 text-lg font-semibold text-white">{selectedRecommendation.recommendation.title}</h3>
              <p className="mt-2">{selectedRecommendation.recommendation.description}</p>
            </div>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-slate-500">Status</dt>
                <dd className="mt-1">
                  <HealthBadge value={selectedRecommendation.recommendation.status} />
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Inventory title</dt>
                <dd className="mt-1 text-slate-200">{selectedRecommendation.recommendation.inventory_title || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Confidence</dt>
                <dd className="mt-1 text-slate-200">{formatPercent(selectedRecommendation.recommendation.confidence_score)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Priority</dt>
                <dd className="mt-1 text-slate-200">{formatPercent(selectedRecommendation.recommendation.priority_score)}</dd>
              </div>
            </dl>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Evidence</p>
              {selectedRecommendation.evidence.length ? (
                <ul className="mt-2 space-y-2">
                  {selectedRecommendation.evidence.map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/40 px-3 py-2">
                      <span className="font-semibold text-white">{row.evidence_source}</span>
                      <span className="text-slate-500"> · {row.evidence_type}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyPanelState message="No evidence rows are attached." />
              )}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Review history</p>
              {selectedRecommendation.reviews.length ? (
                <ul className="mt-2 space-y-2">
                  {selectedRecommendation.reviews.map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/40 px-3 py-2">
                      <span className="font-semibold text-white">{row.review_status}</span>
                      <span className="text-slate-500"> · {formatDateTime(row.reviewed_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyPanelState message="No review activity has been recorded yet." />
              )}
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function AnalyticsPanel({
  analyticsSummary,
  agentMetrics,
  workflowMetrics,
  recommendationMetrics,
}: {
  analyticsSummary: AgentAnalyticsSummaryRead | null;
  agentMetrics: AgentPerformanceMetricRead[];
  workflowMetrics: WorkflowPerformanceMetricRead[];
  recommendationMetrics: RecommendationOutcomeMetricRead[];
}): JSX.Element {
  const latestSnapshot = analyticsSummary?.latest_snapshot ?? null;
  const summary = analyticsSummary?.summary_json ?? {};
  const generatedByType = Object.entries(summaryRecord(summary, "recommendations_generated_by_type"));
  const agentSuccessRate = summaryNumber(summary, "agent_success_rate");
  const agentFailureRate = summaryNumber(summary, "agent_failure_rate");
  const averageDuration = summaryNumber(summary, "avg_execution_duration_ms");
  const recommendationAcceptanceRate = summaryNumber(summary, "recommendation_acceptance_rate");
  const recommendationDismissalRate = summaryNumber(summary, "recommendation_dismissal_rate");

  return (
    <Panel title="Analytics snapshots">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="text-sm text-slate-300">
          {latestSnapshot ? (
            <>
              <div className="font-semibold text-white">Latest snapshot</div>
              <div className="mt-1 text-slate-400">
                Generated {formatDateTime(latestSnapshot.generated_at)} for {latestSnapshot.scope}
              </div>
            </>
          ) : (
            <EmptyPanelState message="No analytics snapshot has been generated yet." />
          )}
        </div>
      </div>

      {latestSnapshot ? (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-5">
            <StatCard label="Agent Success Rate" value={agentSuccessRate == null ? "—" : formatPercent(agentSuccessRate)} />
            <StatCard label="Agent Failure Rate" value={agentFailureRate == null ? "—" : formatPercent(agentFailureRate)} />
            <StatCard label="Average Duration" value={formatDuration(averageDuration)} />
            <StatCard
              label="Recommendation Acceptance Rate"
              value={recommendationAcceptanceRate == null ? "—" : formatPercent(recommendationAcceptanceRate)}
            />
            <StatCard
              label="Recommendation Dismissal Rate"
              value={recommendationDismissalRate == null ? "—" : formatPercent(recommendationDismissalRate)}
            />
          </div>
          <div className="grid gap-4 xl:grid-cols-[1fr,1fr]">
            <section className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
              <h3 className="text-sm font-semibold text-slate-900">Recommendations generated by type</h3>
              {!generatedByType.length ? (
                <p className="mt-3 text-sm text-slate-500">No recommendation outcome metrics are available yet.</p>
              ) : (
                <ul className="mt-3 space-y-2 text-sm text-slate-200">
                  {generatedByType.map(([type, count]) => (
                    <li key={type} className="flex items-center justify-between rounded-xl border border-white/10 px-3 py-2">
                      <span>{type}</span>
                      <span className="font-semibold text-white">{formatCount(count)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
              <h3 className="text-sm font-semibold text-slate-900">Snapshot coverage</h3>
              <dl className="mt-3 grid gap-3 sm:grid-cols-2 text-sm">
                <div>
                  <dt className="text-slate-500">Snapshot date</dt>
                  <dd className="mt-1 text-slate-200">{latestSnapshot.snapshot_date}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Snapshot UUID</dt>
                  <dd className="mt-1 break-all text-slate-200">{latestSnapshot.snapshot_uuid}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Agent metric rows</dt>
                  <dd className="mt-1 text-slate-200">{agentMetrics.length}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Workflow metric rows</dt>
                  <dd className="mt-1 text-slate-200">{workflowMetrics.length}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Recommendation metric rows</dt>
                  <dd className="mt-1 text-slate-200">{recommendationMetrics.length}</dd>
                </div>
              </dl>
            </section>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function PlatformStatusPanel({ summary }: { summary: AgentPlatformSummaryRead | null }): JSX.Element {
  if (!summary) {
    return (
      <Panel title="Agent platform status">
        <EmptyPanelState message="Agent platform readiness status is not available yet." />
      </Panel>
    );
  }

  const items: Array<[string, string]> = [
    ["Overall Status", summary.overall_status],
    ["Validation Status", summary.validation_status],
    ["Security Status", summary.security_status],
    ["Analytics Status", summary.analytics_status],
    ["Recommendation Engine Status", summary.recommendation_engine_status],
    ["Workflow Status", summary.workflow_status],
  ];

  return (
    <Panel title="Agent platform status">
      <div className="grid gap-4 md:grid-cols-3">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
            <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
            <div className="mt-3">
              <HealthBadge value={value} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function AgentDashboardPage(): JSX.Element {
  const [summary, setSummary] = useState<AgentDashboardSummaryResponse | null>(null);
  const [platformSummary, setPlatformSummary] = useState<AgentPlatformSummaryRead | null>(null);
  const [agentHealth, setAgentHealth] = useState<AgentHealthRead[]>([]);
  const [workflowHealth, setWorkflowHealth] = useState<WorkflowHealthRead[]>([]);
  const [analyticsSummary, setAnalyticsSummary] = useState<AgentAnalyticsSummaryRead | null>(null);
  const [analyticsAgentMetrics, setAnalyticsAgentMetrics] = useState<AgentPerformanceMetricRead[]>([]);
  const [analyticsWorkflowMetrics, setAnalyticsWorkflowMetrics] = useState<WorkflowPerformanceMetricRead[]>([]);
  const [analyticsRecommendationMetrics, setAnalyticsRecommendationMetrics] = useState<RecommendationOutcomeMetricRead[]>([]);
  const [executions, setExecutions] = useState<RecentExecutionListResponse | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationQueueListResponse | null>(null);
  const [selectedRecommendation, setSelectedRecommendation] = useState<IntelligenceRecommendationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generatingAnalytics, setGeneratingAnalytics] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionRecommendationId, setActionRecommendationId] = useState<number | null>(null);
  const [executionStatusFilter, setExecutionStatusFilter] = useState("");
  const [executionOffset, setExecutionOffset] = useState(0);
  const [recommendationOffset, setRecommendationOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const executionHasNext = executions?.pagination.has_next ?? false;
  const recommendationHasNext = recommendations?.pagination.has_next ?? false;

  async function loadDashboardState(): Promise<void> {
    const [summaryBody, platformSummaryBody, agentHealthBody, workflowHealthBody, analyticsBody, analyticsAgentBody, analyticsWorkflowBody, analyticsRecommendationBody, executionBody, recommendationBody] = await Promise.all([
      apiClient.getAgentDashboard(),
      apiClient.getAgentPlatformSummary(),
      apiClient.getAgentHealth({ limit: 100, offset: 0 }),
      apiClient.getWorkflowHealth({ limit: 100, offset: 0 }),
      apiClient.getAgentAnalytics(),
      apiClient.getAgentAnalyticsAgents({ limit: 100, offset: 0 }),
      apiClient.getAgentAnalyticsWorkflows({ limit: 100, offset: 0 }),
      apiClient.getAgentAnalyticsRecommendations({ limit: 100, offset: 0 }),
      apiClient.getAgentExecutions({
        execution_status: executionStatusFilter || undefined,
        limit: EXECUTION_PAGE_SIZE,
        offset: executionOffset,
      }),
      apiClient.getAgentRecommendations({
        queue_only: true,
        limit: RECOMMENDATION_PAGE_SIZE,
        offset: recommendationOffset,
      }),
    ]);
    setSummary(summaryBody);
    setPlatformSummary(platformSummaryBody);
    setAgentHealth(agentHealthBody.items);
    setWorkflowHealth(workflowHealthBody.items);
    setAnalyticsSummary(analyticsBody);
    setAnalyticsAgentMetrics(analyticsAgentBody.items);
    setAnalyticsWorkflowMetrics(analyticsWorkflowBody.items);
    setAnalyticsRecommendationMetrics(analyticsRecommendationBody.items);
    setExecutions(executionBody);
    setRecommendations(recommendationBody);
  }

  useEffect(() => {
    let cancelled = false;
    async function run(): Promise<void> {
      if (!cancelled) {
        setLoading(true);
        setError(null);
      }
      try {
        await loadDashboardState();
      } catch (loadErr) {
        if (!cancelled) {
          setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load the agent dashboard.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [executionOffset, executionStatusFilter, recommendationOffset]);

  async function handleRefresh(): Promise<void> {
    setRefreshing(true);
    setError(null);
    try {
      await loadDashboardState();
      setMessage("Agent dashboard refreshed.");
    } catch (refreshErr) {
      setError(refreshErr instanceof ApiError ? refreshErr.message : "Unable to refresh the agent dashboard.");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleGenerateAnalyticsSnapshot(): Promise<void> {
    setGeneratingAnalytics(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.generateAgentAnalyticsSnapshot();
      await loadDashboardState();
      setMessage("Agent analytics snapshot generated.");
    } catch (generateErr) {
      setError(generateErr instanceof ApiError ? generateErr.message : "Unable to generate an analytics snapshot.");
    } finally {
      setGeneratingAnalytics(false);
    }
  }

  async function handleViewRecommendation(recommendationId: number): Promise<void> {
    setDetailLoading(true);
    setError(null);
    try {
      const detail = await apiClient.getIntelligenceRecommendation(recommendationId);
      setSelectedRecommendation(detail);
    } catch (detailErr) {
      setError(detailErr instanceof ApiError ? detailErr.message : "Unable to load recommendation details.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleReviewAction(kind: "reviewed" | "dismissed" | "accepted", recommendationId: number): Promise<void> {
    setActionRecommendationId(recommendationId);
    setError(null);
    setMessage(null);
    try {
      if (kind === "reviewed") {
        await apiClient.markIntelligenceRecommendationReviewed(recommendationId);
        setMessage("Recommendation marked reviewed.");
      } else if (kind === "dismissed") {
        await apiClient.markIntelligenceRecommendationDismissed(recommendationId);
        setMessage("Recommendation dismissed.");
      } else {
        await apiClient.markIntelligenceRecommendationAccepted(recommendationId);
        setMessage("Recommendation accepted for follow-up.");
      }
      await loadDashboardState();
      if (selectedRecommendation?.recommendation.id === recommendationId) {
        const detail = await apiClient.getIntelligenceRecommendation(recommendationId);
        setSelectedRecommendation(detail);
      }
    } catch (actionErr) {
      setError(actionErr instanceof ApiError ? actionErr.message : "Unable to update recommendation review state.");
    } finally {
      setActionRecommendationId(null);
    }
  }

  const summaryCards = useMemo(
    () =>
      summary
        ? [
            ["Total Agents", String(summary.total_agents)],
            ["Enabled Agents", String(summary.enabled_agents)],
            ["Total Workflows", String(summary.total_workflows)],
            ["Active Executions", String(summary.active_executions)],
            ["Recommendations Awaiting Review", String(summary.recommendations_awaiting_review)],
          ]
        : [],
    [summary],
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="P45-07"
        title="Agent operations dashboard"
        description="Operational visibility across agent executions, workflow health, research output volume, and reviewable dealer-intelligence recommendations."
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={generatingAnalytics}
              onClick={() => void handleGenerateAnalyticsSnapshot()}
              className="rounded-2xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-100 disabled:opacity-50"
            >
              {generatingAnalytics ? "Generating..." : "Generate Analytics Snapshot"}
            </button>
            <button
              type="button"
              disabled={refreshing}
              onClick={() => void handleRefresh()}
              className="rounded-2xl border border-cyan-400/30 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
            >
              {refreshing ? "Refreshing..." : "Refresh dashboard"}
            </button>
          </div>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {message ? (
        <div className="mt-4">
          <StatusBanner tone="success">{message}</StatusBanner>
        </div>
      ) : null}
      {loading ? (
        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm text-sm text-slate-300">
          Loading agent dashboard...
        </section>
      ) : (
        <div className="mt-6 space-y-6">
          <section className="grid gap-4 md:grid-cols-5">
            {summaryCards.map(([label, value]) => (
              <StatCard key={label} label={label} value={value} />
            ))}
          </section>
          <PlatformStatusPanel summary={platformSummary} />
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Agent health">
              <AgentHealthTable rows={agentHealth} />
            </Panel>
            <Panel title="Workflow health">
              <WorkflowHealthTable rows={workflowHealth} />
            </Panel>
          </div>
          <AnalyticsPanel
            analyticsSummary={analyticsSummary}
            agentMetrics={analyticsAgentMetrics}
            workflowMetrics={analyticsWorkflowMetrics}
            recommendationMetrics={analyticsRecommendationMetrics}
          />
          <ExecutionActivityPanel
            rows={executions?.items ?? []}
            statusFilter={executionStatusFilter}
            onStatusFilterChange={(value) => {
              setExecutionOffset(0);
              setExecutionStatusFilter(value);
            }}
            canGoBack={executionOffset > 0}
            canGoForward={executionHasNext}
            onPrevious={() => setExecutionOffset((current) => Math.max(0, current - EXECUTION_PAGE_SIZE))}
            onNext={() => setExecutionOffset((current) => current + EXECUTION_PAGE_SIZE)}
          />
          {detailLoading ? (
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm text-sm text-slate-300">
              Loading recommendation details...
            </section>
          ) : (
            <RecommendationQueuePanel
              rows={recommendations?.items ?? []}
              selectedRecommendation={selectedRecommendation}
              actionRecommendationId={actionRecommendationId}
              canGoBack={recommendationOffset > 0}
              canGoForward={recommendationHasNext}
              onPrevious={() => setRecommendationOffset((current) => Math.max(0, current - RECOMMENDATION_PAGE_SIZE))}
              onNext={() => setRecommendationOffset((current) => current + RECOMMENDATION_PAGE_SIZE)}
              onViewDetails={(recommendationId) => void handleViewRecommendation(recommendationId)}
              onReviewAction={(kind, recommendationId) => void handleReviewAction(kind, recommendationId)}
            />
          )}
        </div>
      )}
    </AppShell>
  );
}
