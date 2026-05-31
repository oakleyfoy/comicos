import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { LunarFeedPage } from "../LunarFeedPage";

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

describe("LunarFeedPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getLunarFeedDashboard").mockResolvedValue({
      credential_status: {
        credential_available: true,
        username_masked: "st***@example.com",
      },
      last_run: {
        id: 1,
        owner_user_id: 1,
        run_uuid: "run-uuid",
        source_type: "REMOTE",
        file_name: "june.csv",
        file_period: "2026-06",
        status: "COMPLETED",
        records_processed: 10,
        records_created: 8,
        records_updated: 2,
        records_failed: 0,
        foc_alerts_created: 1,
        source_url: "https://example.test/june.csv",
        started_at: "2026-05-30T12:00:00Z",
        completed_at: "2026-05-30T12:00:01Z",
        created_at: "2026-05-30T12:00:00Z",
      },
    });
    vi.spyOn(apiClient, "getLunarSchedulerStatus").mockResolvedValue({
      credential_available: true,
      enabled: false,
      schedule_type: "DAILY",
      schedule_time: "06:00",
      timezone: "America/Chicago",
      next_run_at: null,
      last_success_at: null,
      last_failure_at: null,
      last_imported_file_name: "",
      last_imported_file_period: "",
      last_imported_at: null,
    });
    vi.spyOn(apiClient, "getLunarSchedulerHistory").mockResolvedValue({
      runs: [],
      total_runs: 0,
      no_change_runs: 0,
      import_runs: 0,
      failed_runs: 0,
    });
  });

  it("renders lunar feed dashboard and remote controls", async () => {
    render(
      <MemoryRouter>
        <LunarFeedPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Lunar Feed" })).toBeInTheDocument();
    });

    expect(screen.getByText("Credential Status")).toBeInTheDocument();
    expect(screen.getByText(/Credentials configured/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download Latest Lunar CSV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import Latest Lunar CSV" })).toBeInTheDocument();
    expect(screen.getByText("Latest Manual Feed Run")).toBeInTheDocument();
  });
});
