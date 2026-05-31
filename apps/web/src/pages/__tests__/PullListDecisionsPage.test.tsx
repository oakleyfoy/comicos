import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PullListDecisionsPage } from "../PullListDecisionsPage";
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

describe("PullListDecisionsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders decisions table", async () => {
    vi.spyOn(apiClient, "getPullListDecisions").mockResolvedValue({
      items: [
        {
          id: 1,
          owner_id: 1,
          release_id: 10,
          decision_type: "START_RUN",
          confidence_score: 0.88,
          explanation: "[]",
          reasons: ["New #1 issue", "Strong franchise"],
          created_at: "2026-06-01T00:00:00Z",
          comic_title: "TMNT #1",
          issue_number: "1",
          publisher: "IDW",
          series_name: "TMNT",
          release_date: "2026-07-01",
          foc_date: "2026-06-01",
          recommendation_tier: "STRONG_BUY",
          recommendation_score: 82,
        },
      ],
      total_items: 1,
      limit: 50,
      offset: 0,
    });
    render(
      <MemoryRouter>
        <PullListDecisionsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("START RUN")).toBeInTheDocument();
      expect(screen.getByText(/TMNT #1/)).toBeInTheDocument();
    });
  });
});
