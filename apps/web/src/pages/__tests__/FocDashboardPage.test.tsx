import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FocDashboardPage } from "../FocDashboardPage";
import { apiClient } from "../../api/client";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("FocDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders summary and action required row", async () => {
    vi.spyOn(apiClient, "getFocDashboard").mockResolvedValue({
      summary: {
        action_required_count: 1,
        start_run_count: 1,
        continue_run_count: 0,
        watch_count: 1,
        upcoming_foc_count: 0,
        upcoming_release_count: 1,
      },
      action_required: [
        {
          release_id: 1,
          pull_list_issue_id: null,
          decision_id: 1,
          series_name: "Spider-Man",
          issue_number: "1",
          title: "Spider-Man #1",
          publisher: "Marvel",
          decision_type: "START_RUN",
          confidence_score: 0.8,
          foc_date: "2026-06-04",
          release_date: "2026-06-18",
          days_until_foc: 5,
          days_until_release: 19,
          foc_status: "THIS_WEEK",
          reasons: ["New #1"],
          sections: ["ACTION_REQUIRED"],
          on_pull_list: false,
          pull_list_action_state: null,
        },
      ],
      upcoming_foc: [],
      upcoming_releases: [],
      missed_foc: [],
      watchlist: [],
    });
    render(
      <MemoryRouter>
        <FocDashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "FOC Dashboard" })).toBeInTheDocument();
      expect(screen.getByText("Spider-Man")).toBeInTheDocument();
      expect(screen.getByText("START RUN")).toBeInTheDocument();
    });
  });
});
