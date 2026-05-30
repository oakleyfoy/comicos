import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AgentDashboardPage } from "./AgentDashboardPage";
import { apiClient } from "../api/client";

vi.mock("../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../components/PageHeader", () => ({
  PageHeader: ({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions}
    </header>
  ),
}));

vi.mock("../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("AgentDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    vi.spyOn(apiClient, "getAgentDashboard").mockResolvedValue({
      total_agents: 8,
      enabled_agents: 5,
      total_workflows: 4,
      enabled_workflows: 2,
      active_executions: 1,
      total_research_snapshots: 2,
      total_recommendations: 6,
      recommendations_awaiting_review: 3,
    });
    vi.spyOn(apiClient, "getAgentPlatformSummary").mockResolvedValue({
      overall_status: "PASS",
      validation_status: "PASS",
      security_status: "PASS",
      analytics_status: "PASS",
      recommendation_engine_status: "PASS",
      workflow_status: "WARNING",
    });
    vi.spyOn(apiClient, "getAgentHealth").mockResolvedValue({
      items: [
        {
          agent_id: 1,
          agent_code: "pricing_intelligence_agent",
          agent_name: "Pricing Intelligence Agent",
          enabled: true,
          health_status: "HEALTHY",
          execution_count: 3,
          success_count: 3,
          failure_count: 0,
          success_rate: 1,
          average_duration_ms: 1420,
          last_run_at: "2026-05-29T23:10:00Z",
          last_success_at: "2026-05-29T23:10:00Z",
          last_failure_at: null,
        },
      ],
      pagination: { total_count: 1, limit: 100, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getWorkflowHealth").mockResolvedValue({
      items: [
        {
          workflow_id: 1,
          workflow_code: "inventory_refresh_workflow",
          workflow_name: "Inventory Refresh Workflow",
          enabled: true,
          health_status: "WARNING",
          execution_count: 2,
          success_count: 1,
          failure_count: 1,
          success_rate: 0.5,
          average_duration_ms: 2100,
          last_run_at: "2026-05-29T23:11:00Z",
          last_success_at: "2026-05-29T22:11:00Z",
          last_failure_at: "2026-05-29T23:11:00Z",
        },
      ],
      pagination: { total_count: 1, limit: 100, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getAgentExecutions").mockResolvedValue({
      items: [
        {
          execution_id: 11,
          execution_uuid: "exec-11",
          agent_id: 1,
          agent_code: "pricing_intelligence_agent",
          agent_name: "Pricing Intelligence Agent",
          workflow_execution_id: 91,
          workflow_id: 1,
          workflow_code: "inventory_refresh_workflow",
          workflow_name: "Inventory Refresh Workflow",
          status: "COMPLETED",
          started_at: "2026-05-29T23:09:00Z",
          completed_at: "2026-05-29T23:09:03Z",
          duration_ms: 3000,
          trigger_source: "workflow:inventory_refresh_workflow",
        },
      ],
      pagination: { total_count: 1, limit: 10, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getAgentRecommendations").mockResolvedValue({
      items: [
        {
          recommendation_id: 21,
          recommendation_uuid: "rec-21",
          recommendation_type: "underpriced_inventory",
          title: "Underpriced X-Men issue",
          inventory_title: "X-Men #1",
          status: "OPEN",
          confidence_score: 0.82,
          opportunity_score: 0.75,
          priority_score: 0.79,
          created_at: "2026-05-29T23:08:00Z",
          agent_execution_id: 11,
        },
      ],
      pagination: { total_count: 1, limit: 10, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getIntelligenceRecommendation").mockResolvedValue({
      recommendation: {
        id: 21,
        recommendation_uuid: "rec-21",
        agent_execution_id: 11,
        recommendation_type: "underpriced_inventory",
        title: "Underpriced X-Men issue",
        description: "Recent sales outpaced the current sticker price.",
        confidence_score: 0.82,
        opportunity_score: 0.75,
        priority_score: 0.79,
        inventory_copy_id: 100,
        inventory_title: "X-Men #1",
        status: "OPEN",
        recommendation_payload_json: {},
        created_at: "2026-05-29T23:08:00Z",
        latest_review: null,
      },
      evidence: [],
      reviews: [],
    });
    vi.spyOn(apiClient, "getAgentAnalytics").mockResolvedValue({
      latest_snapshot: {
        id: 41,
        snapshot_uuid: "snapshot-41",
        snapshot_date: "2026-05-29",
        generated_at: "2026-05-29T23:12:00Z",
        scope: "owner:1",
        summary_json: {
          agent_success_rate: 0.75,
          agent_failure_rate: 0.25,
          avg_execution_duration_ms: 2100,
          recommendation_acceptance_rate: 0.5,
          recommendation_dismissal_rate: 0.25,
          recommendations_generated_by_type: {
            underpriced_inventory: 2,
            missing_metadata: 1,
          },
        },
        created_at: "2026-05-29T23:12:00Z",
      },
      summary_json: {
        agent_success_rate: 0.75,
        agent_failure_rate: 0.25,
        avg_execution_duration_ms: 2100,
        recommendation_acceptance_rate: 0.5,
        recommendation_dismissal_rate: 0.25,
        recommendations_generated_by_type: {
          underpriced_inventory: 2,
          missing_metadata: 1,
        },
      },
      agent_metric_count: 2,
      workflow_metric_count: 1,
      recommendation_metric_count: 2,
    });
    vi.spyOn(apiClient, "getAgentAnalyticsAgents").mockResolvedValue({
      items: [
        {
          id: 1,
          snapshot_id: 41,
          agent_id: 1,
          agent_code: "pricing_intelligence_agent",
          executions_total: 4,
          executions_completed: 3,
          executions_failed: 1,
          success_rate: 0.75,
          failure_rate: 0.25,
          avg_duration_ms: 2100,
          last_run_at: "2026-05-29T23:12:00Z",
          last_success_at: "2026-05-29T23:10:00Z",
          last_failure_at: "2026-05-29T23:11:00Z",
          recommendations_generated: 3,
          recommendations_reviewed: 2,
          recommendations_accepted: 1,
          recommendations_dismissed: 1,
          created_at: "2026-05-29T23:12:00Z",
        },
      ],
      pagination: { total_count: 1, limit: 100, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getAgentAnalyticsWorkflows").mockResolvedValue({
      items: [
        {
          id: 1,
          snapshot_id: 41,
          workflow_id: 1,
          workflow_code: "inventory_refresh_workflow",
          executions_total: 2,
          executions_completed: 1,
          executions_failed: 1,
          success_rate: 0.5,
          failure_rate: 0.5,
          avg_duration_ms: 2100,
          last_run_at: "2026-05-29T23:12:00Z",
          last_success_at: "2026-05-29T23:10:00Z",
          last_failure_at: "2026-05-29T23:11:00Z",
          created_at: "2026-05-29T23:12:00Z",
        },
      ],
      pagination: { total_count: 1, limit: 100, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getAgentAnalyticsRecommendations").mockResolvedValue({
      items: [
        {
          id: 1,
          snapshot_id: 41,
          recommendation_type: "underpriced_inventory",
          recommendations_total: 2,
          reviewed_total: 1,
          accepted_total: 1,
          dismissed_total: 0,
          acceptance_rate: 0.5,
          dismissal_rate: 0,
          avg_confidence_score: 0.82,
          avg_opportunity_score: 0.75,
          avg_priority_score: 0.79,
          created_at: "2026-05-29T23:12:00Z",
        },
        {
          id: 2,
          snapshot_id: 41,
          recommendation_type: "missing_metadata",
          recommendations_total: 1,
          reviewed_total: 1,
          accepted_total: 0,
          dismissed_total: 1,
          acceptance_rate: 0,
          dismissal_rate: 1,
          avg_confidence_score: 0.7,
          avg_opportunity_score: 0.4,
          avg_priority_score: 0.5,
          created_at: "2026-05-29T23:12:00Z",
        },
      ],
      pagination: { total_count: 2, limit: 100, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "generateAgentAnalyticsSnapshot").mockResolvedValue({
      snapshot: {
        id: 42,
        snapshot_uuid: "snapshot-42",
        snapshot_date: "2026-05-29",
        generated_at: "2026-05-29T23:15:00Z",
        scope: "owner:1",
        summary_json: {},
        created_at: "2026-05-29T23:15:00Z",
      },
      agent_metrics: [],
      workflow_metrics: [],
      recommendation_metrics: [],
    });
  });

  it("renders summary cards, analytics, recommendation queue, and execution activity", async () => {
    render(
      <MemoryRouter>
        <AgentDashboardPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Loading agent dashboard...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Agent operations dashboard")).toBeInTheDocument();
    });

    expect(screen.getByText("Total Agents")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("Recommendations Awaiting Review")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Agent platform status")).toBeInTheDocument();
    expect(screen.getByText("Overall Status")).toBeInTheDocument();
    expect(screen.getByText("Validation Status")).toBeInTheDocument();
    expect(screen.getByText("Security Status")).toBeInTheDocument();
    expect(screen.getByText("Analytics Status")).toBeInTheDocument();
    expect(screen.getByText("Recommendation Engine Status")).toBeInTheDocument();
    expect(screen.getByText("Workflow Status")).toBeInTheDocument();

    expect(screen.getAllByText("Pricing Intelligence Agent").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Inventory Refresh Workflow").length).toBeGreaterThan(0);
    expect(screen.getByText("HEALTHY")).toBeInTheDocument();
    expect(screen.getAllByText("WARNING").length).toBeGreaterThan(0);

    expect(screen.getByText("Recent agent executions")).toBeInTheDocument();
    expect(screen.queryByText("Standalone execution")).not.toBeInTheDocument();
    expect(screen.getAllByText("Pricing Intelligence Agent").length).toBeGreaterThan(0);
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();

    expect(screen.getByText("Recommendations awaiting review")).toBeInTheDocument();
    expect(screen.getByText("Underpriced X-Men issue")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View Details" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark Reviewed" })).toBeInTheDocument();

    expect(screen.getByText("Analytics snapshots")).toBeInTheDocument();
    expect(screen.getByText("Agent Success Rate")).toBeInTheDocument();
    expect(screen.getByText("Recommendation Acceptance Rate")).toBeInTheDocument();
    expect(screen.getByText("Recommendations generated by type")).toBeInTheDocument();
    expect(screen.getAllByText("underpriced_inventory").length).toBeGreaterThan(0);
    expect(screen.getAllByText("missing_metadata").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Generate Analytics Snapshot" }));
    await waitFor(() => {
      expect(apiClient.generateAgentAnalyticsSnapshot).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByText("Agent analytics snapshot generated.")).toBeInTheDocument();
    });
  });
});
