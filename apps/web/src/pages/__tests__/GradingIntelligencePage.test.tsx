import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { GradingIntelligencePage } from "../GradingIntelligencePage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title, description }: { title: string; description: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("GradingIntelligencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getGradingIntelligenceDashboard").mockResolvedValue({
      prediction_count: 1,
      recommendation_count: 1,
      roi_analysis_count: 1,
      average_confidence: 0.72,
      average_priority: 0.81,
      average_roi_percent: 27.3,
      prediction_summary: [
        {
          id: 1,
          prediction_uuid: "pred-1",
          analysis_id: 10,
          inventory_copy_id: null,
          grading_scale: "PSA",
          predicted_grade: "9.4",
          grade_floor: "9.0",
          grade_ceiling: "9.6",
          confidence_score: 0.72,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      recommendation_summary: [
        {
          id: 1,
          recommendation_uuid: "rec-1",
          prediction_id: 1,
          inventory_copy_id: null,
          recommendation_type: "GRADE",
          title: "Advisory grade candidate",
          description: "Manual submission only.",
          confidence_score: 0.72,
          priority_score: 0.81,
          recommendation_status: "OPEN",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      top_grading_candidates: [],
      roi_summary: [
        {
          id: 1,
          recommendation_id: 1,
          inventory_copy_id: null,
          raw_value: 25,
          expected_graded_value: 70,
          grading_cost: 30,
          expected_profit: 15,
          expected_roi_percent: 27.27,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      agent_activity: [
        {
          id: 1,
          agent_code: "grade_prediction",
          execution_uuid: "exec-1",
          status: "COMPLETED",
          started_at: "2026-05-30T12:00:00Z",
          completed_at: "2026-05-30T12:00:01Z",
          duration_ms: 50,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
    });
  });

  it("renders grading intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <GradingIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Grading Intelligence" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("Grade Predictions").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Grading Recommendations").length).toBeGreaterThan(0);
    expect(screen.getByText("Top Submission Candidates")).toBeInTheDocument();
    expect(screen.getAllByText("ROI Analysis").length).toBeGreaterThan(0);
  });
});
