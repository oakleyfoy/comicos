import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ConditionIntelligencePage } from "../ConditionIntelligencePage";

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

describe("ConditionIntelligencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getConditionIntelligenceDashboard").mockResolvedValue({
      analysis_count: 2,
      profile_count: 2,
      defect_count: 3,
      subgrade_count: 8,
      quality_assessment_count: 2,
      execution_count: 8,
      average_condition_score: 82.5,
      average_quality_score: 88.0,
      condition_summary: [
        {
          id: 1,
          analysis_id: 10,
          overall_condition_score: 82.5,
          confidence_score: 0.72,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      defect_summary: [
        {
          id: 1,
          analysis_id: 10,
          defect_type: "CORNER_WEAR",
          defect_location: "TOP_LEFT_CORNER",
          defect_severity: "LOW",
          confidence_score: 0.55,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      subgrade_summary: [
        {
          id: 1,
          analysis_id: 10,
          subgrade_type: "CENTERING",
          score: 85,
          confidence_score: 0.7,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      scan_quality_summary: [
        {
          id: 1,
          analysis_id: 10,
          image_quality_score: 88,
          resolution_score: 90,
          alignment_score: 92,
          glare_score: 85,
          crop_score: 95,
          quality_status: "PASS",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      agent_activity: [
        {
          id: 1,
          agent_code: "scan_quality",
          execution_uuid: "exec-1",
          status: "COMPLETED",
          started_at: "2026-05-30T12:00:00Z",
          completed_at: "2026-05-30T12:00:01Z",
          duration_ms: 100,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
    });
  });

  it("renders condition intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <ConditionIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Condition Intelligence" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("Condition Profiles").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Detected Defects").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Subgrades").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Scan Quality").length).toBeGreaterThan(0);
    expect(screen.getByText("Agent Activity")).toBeInTheDocument();
  });
});
