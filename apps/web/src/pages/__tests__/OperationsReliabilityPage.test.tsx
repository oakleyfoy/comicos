import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { OperationsReliabilityPage } from "../OperationsReliabilityPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions}
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("OperationsReliabilityPage", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders operations reliability dashboard sections", async () => {
    vi.spyOn(apiClient, "getOperationsReliabilityHealth").mockResolvedValue({
      summary: {
        readiness_score: 82.5,
        platform_health_status: "WARNING",
        open_issue_count: 1,
        recommendation_count: 2,
      },
      health_checks: [
        {
          id: 1,
          check_uuid: "health-1",
          subsystem: "database",
          health_status: "HEALTHY",
          health_score: 100,
          check_payload_json: {},
          checked_at: "2026-05-30T12:00:00Z",
        },
      ],
      issues: [
        {
          id: 1,
          issue_uuid: "issue-1",
          subsystem: "queues",
          issue_type: "queue_backlog",
          severity: "MEDIUM",
          issue_status: "OPEN",
          issue_payload_json: {},
          detected_at: "2026-05-30T12:00:00Z",
        },
      ],
      job_metrics: [
        {
          id: 1,
          job_type: "gmail_sync",
          total_jobs: 3,
          successful_jobs: 2,
          failed_jobs: 1,
          average_duration_ms: 1200,
          measured_at: "2026-05-30T12:00:00Z",
        },
      ],
      queue_metrics: [
        {
          id: 1,
          queue_name: "default",
          queued_count: 4,
          running_count: 1,
          failed_count: 0,
          measured_at: "2026-05-30T12:00:00Z",
        },
      ],
      recommendations: [
        {
          id: 1,
          recommendation_uuid: "rec-1",
          subsystem: "queues",
          recommendation_type: "queue_backlog",
          title: "Investigate queue backlog",
          description: "Review queue depth and worker capacity.",
          priority_score: 0.6,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      pull_list_automation: {
        last_run: "2026-05-30T11:15:00Z",
        status: "SUCCESS",
        runtime_ms: 420,
        decisions_generated: 12,
        actions_generated: 5,
      },
      pull_list_certification: {
        last_certification_at: "2026-05-30T12:30:00Z",
        readiness_score: 92.5,
        certification_result: "APPROVED_FOR_PRODUCTION",
        validation_status: "PASS",
      },
    });

    render(
      <MemoryRouter>
        <OperationsReliabilityPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Operations Reliability" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("Overall Readiness Score").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Platform Health").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Subsystem Health").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Reliability Issues").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Job Metrics").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Queue Metrics").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Recovery Recommendations").length).toBeGreaterThan(0);
      expect(screen.getByText("Pull List Automation")).toBeInTheDocument();
      expect(screen.getByText("Pull List Certification")).toBeInTheDocument();
      expect(screen.getByText("Investigate queue backlog")).toBeInTheDocument();
    });
  });

  it("shows owner empty state when certification panel has no recorded run", async () => {
    vi.spyOn(apiClient, "getOperationsReliabilityHealth").mockResolvedValue({
      summary: {
        readiness_score: 66.1,
        platform_health_status: "UNHEALTHY",
        open_issue_count: 0,
        recommendation_count: 0,
      },
      health_checks: [],
      issues: [],
      job_metrics: [],
      queue_metrics: [],
      recommendations: [],
      pull_list_certification: {
        last_certification_at: null,
        readiness_score: 0,
        certification_result: "NOT_READY",
        validation_status: "UNKNOWN",
      },
      portfolio_certification: {
        last_certification_at: null,
        readiness_score: 0,
        certification_result: "NOT_READY",
        validation_status: "UNKNOWN",
      },
      final_platform_certification: {
        last_certification_at: "2026-05-31T20:01:44Z",
        readiness_score: 53.5,
        certification_result: "NOT_READY",
        health_status: "UNHEALTHY",
        validation_summary: "Platform summary",
      },
      production_readiness: {
        last_run_at: "2026-05-31T20:07:44Z",
        readiness_score: 66.1,
        go_live_result: "NOT_READY",
        health_status: "UNHEALTHY",
        recommendations: "Remediate failures",
      },
    });

    render(
      <MemoryRouter>
        <OperationsReliabilityPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("No pull list certification runs recorded for this owner.")).toBeInTheDocument();
      expect(screen.getAllByText("No portfolio certification runs recorded for this owner.").length).toBeGreaterThan(0);
      expect(screen.queryByText("UNKNOWN")).not.toBeInTheDocument();
      expect(screen.getAllByText("NOT_READY").length).toBeGreaterThan(0);
    });
  });
});
