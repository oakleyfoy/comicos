import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ReleaseWatchlistPage } from "../ReleaseWatchlistPage";

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

describe("ReleaseWatchlistPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getReleaseWatchlistDashboard").mockResolvedValue({
      active_runs: [
        {
          id: 1,
          owner_user_id: 1,
          publisher: "Image",
          series_name: "Invincible",
          first_issue_owned: "1",
          latest_issue_owned: "2",
          issue_count_owned: 2,
          continuity_status: "ACTIVE_RUN",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      continuity_alerts: [
        {
          id: 1,
          owner_user_id: 1,
          release_issue_id: 10,
          alert_type: "CONTINUE_RUN",
          alert_status: "OPEN",
          alert_payload_json: {},
          created_at: "2026-05-30T12:00:00Z",
        },
        {
          id: 2,
          owner_user_id: 1,
          release_issue_id: 11,
          alert_type: "MISSING_ISSUE_RISK",
          alert_status: "OPEN",
          alert_payload_json: {},
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      foc_reminders: [
        {
          id: 1,
          owner_user_id: 1,
          release_issue_id: 10,
          reminder_type: "FOC_TODAY",
          reminder_date: "2026-05-30",
          reminder_status: "OPEN",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      release_reminders: [
        {
          id: 2,
          owner_user_id: 1,
          release_issue_id: 10,
          reminder_type: "RELEASE_TOMORROW",
          reminder_date: "2026-05-31",
          reminder_status: "OPEN",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      watchlists: [
        {
          watchlist: {
            id: 1,
            owner_user_id: 1,
            watchlist_name: "Owned Active Runs",
            watchlist_type: "AUTO_OWNED_RUNS",
            created_at: "2026-05-30T12:00:00Z",
          },
          items: [],
        },
      ],
      watchlist_matches: [],
      upcoming_watched_releases: [
        {
          id: 10,
          release_uuid: "rel-10",
          series_id: 1,
          issue_number: "3",
          title: "Invincible #3",
          foc_date: "2026-05-30",
          release_date: "2026-05-31",
          cover_price: 4.99,
          release_status: "SCHEDULED",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      agent_activity: [
        {
          id: 1,
          owner_user_id: 1,
          agent_code: "run_continuity",
          execution_uuid: "exec-1",
          status: "COMPLETED",
          started_at: "2026-05-30T12:00:00Z",
          completed_at: "2026-05-30T12:00:01Z",
          duration_ms: 25,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
    });
  });

  it("renders release watchlist dashboard", async () => {
    render(
      <MemoryRouter>
        <ReleaseWatchlistPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Release Watchlists" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("Active Runs").length).toBeGreaterThan(0);
    expect(screen.getByText("Continue Run Alerts")).toBeInTheDocument();
    expect(screen.getByText("Missing Issue Risks")).toBeInTheDocument();
    expect(screen.getAllByText("FOC Reminders").length).toBeGreaterThan(0);
    expect(screen.getByText("Release Reminders")).toBeInTheDocument();
    expect(screen.getAllByText("Watchlists").length).toBeGreaterThan(0);
    expect(screen.getByText("Watched Upcoming Releases")).toBeInTheDocument();
    expect(screen.getByText("Agent Activity")).toBeInTheDocument();
  });
});
