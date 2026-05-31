import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { KeyIssueIntelligencePage } from "../KeyIssueIntelligencePage";

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

const mockDashboard = {
  total_profiles: 3,
  top_key_issues: [
    {
      id: 1,
      release_issue_id: 10,
      issue_number: "300",
      title: "TMNT #300",
      series_name: "TMNT",
      publisher: "IDW",
      key_issue_type: "MILESTONE_NUMBERING",
      importance_score: 88,
      confidence_score: 0.9,
      classification: "MILESTONE_NUMBERING",
      scores: {
        importance_score: 88,
        collector_importance: 80,
        historical_importance: 79,
        franchise_importance: 85,
        overall_key_issue_score: 84,
      },
    },
  ],
  first_appearances: [],
  origins: [],
  milestones: [],
  anniversaries: [],
  universe_launches: [],
  highest_importance: [],
};

describe("KeyIssueIntelligencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "postKeyIssuesRefresh").mockResolvedValue({
      detections_created: 2,
      catalog_matches: 1,
      pattern_matches: 1,
      scores_updated: 2,
      refreshed_at: "2026-05-30",
    });
    vi.spyOn(apiClient, "getKeyIssuesDashboard").mockResolvedValue(mockDashboard);
  });

  it("renders key issue intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <KeyIssueIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Key Issue Intelligence" })).toBeInTheDocument();
    });

    expect(screen.getByText("Top Key Issues")).toBeInTheDocument();
    expect(screen.getByText(/MILESTONE_NUMBERING/)).toBeInTheDocument();
  });
});
