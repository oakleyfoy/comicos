import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ReleaseIntelligencePage } from "../ReleaseIntelligencePage";

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

describe("ReleaseIntelligencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getReleaseIntelligenceDashboard").mockResolvedValue({
      upcoming_releases: [
        {
          id: 1,
          release_uuid: "rel-1",
          series_id: 1,
          issue_number: "1",
          title: "Amazing Future",
          foc_date: "2026-06-10",
          release_date: "2026-06-24",
          cover_price: 4.99,
          release_status: "SCHEDULED",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      foc_calendar: [
        {
          id: 1,
          release_uuid: "rel-1",
          series_id: 1,
          issue_number: "1",
          title: "Amazing Future",
          foc_date: "2026-06-10",
          release_date: "2026-06-24",
          cover_price: 4.99,
          release_status: "SCHEDULED",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      new_number_one_feed: [
        {
          series: {
            id: 1,
            publisher: "Marvel",
            series_name: "Amazing Future",
            series_type: "ONGOING",
            status: "ACTIVE",
            created_at: "2026-05-30T12:00:00Z",
          },
          issue: {
            id: 1,
            release_uuid: "rel-1",
            series_id: 1,
            issue_number: "1",
            title: "Amazing Future",
            foc_date: "2026-06-10",
            release_date: "2026-06-24",
            cover_price: 4.99,
            release_status: "SCHEDULED",
            created_at: "2026-05-30T12:00:00Z",
          },
          signal: {
            id: 1,
            issue_id: 1,
            signal_type: "NEW_NUMBER_ONE",
            confidence_score: 0.95,
            signal_payload_json: { classification: "ONGOING_1" },
            created_at: "2026-05-30T12:00:00Z",
          },
        },
      ],
      key_issue_feed: [],
      variant_feed: [],
      agent_activity: [
        {
          id: 1,
          agent_code: "new_number_one",
          execution_uuid: "exec-1",
          status: "COMPLETED",
          started_at: "2026-05-30T12:00:00Z",
          completed_at: "2026-05-30T12:00:01Z",
          duration_ms: 40,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      variant_count: 0,
      ratio_variant_count: 0,
      cover_variant_count: 0,
      recent_variants: [],
      top_ratio_variants: [],
    });
  });

  it("renders release intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <ReleaseIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Release Intelligence" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("Upcoming Releases").length).toBeGreaterThan(0);
    expect(screen.getByText("FOC Calendar")).toBeInTheDocument();
    expect(screen.getByText("New #1 Feed")).toBeInTheDocument();
    expect(screen.getByText("Key Issue Feed")).toBeInTheDocument();
    expect(screen.getByText("Variant Feed")).toBeInTheDocument();
    expect(screen.getByText("Agent Activity")).toBeInTheDocument();
  });
});
