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
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("LunarScheduler UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getLunarFeedDashboard").mockResolvedValue({
      credential_status: { credential_available: true, username_masked: "s***r" },
      last_run: null,
    });
    vi.spyOn(apiClient, "getLunarSchedulerStatus").mockResolvedValue({
      credential_available: true,
      enabled: true,
      schedule_type: "DAILY",
      schedule_time: "06:00",
      timezone: "America/Chicago",
      next_run_at: "2026-06-01T11:00:00Z",
      last_success_at: "2026-05-30T11:00:00Z",
      last_failure_at: null,
      last_imported_file_name: "lunar-2026-06.csv",
      last_imported_file_period: "2026-06",
      last_imported_at: "2026-05-30T11:00:00Z",
    });
    vi.spyOn(apiClient, "getLunarSchedulerHistory").mockResolvedValue({
      runs: [
        {
          id: 1,
          owner_user_id: 1,
          run_uuid: "uuid-1",
          trigger_type: "SCHEDULED",
          status: "NO_CHANGE",
          file_name: "lunar-2026-06.csv",
          file_period: "2026-06",
          records_processed: 0,
          records_imported: 0,
          records_updated: 0,
          records_failed: 0,
          started_at: "2026-05-30T10:00:00Z",
          completed_at: "2026-05-30T10:00:01Z",
          created_at: "2026-05-30T10:00:00Z",
        },
      ],
      total_runs: 1,
      no_change_runs: 1,
      import_runs: 0,
      failed_runs: 0,
    });
  });

  it("renders scheduler status and history", async () => {
    render(
      <MemoryRouter>
        <LunarFeedPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Lunar Feed" })).toBeInTheDocument();
    });

    expect(screen.getByText("Scheduler Status")).toBeInTheDocument();
    expect(screen.getByText(/Enabled: Yes/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Now" })).toBeInTheDocument();
    expect(screen.getByText("Import History")).toBeInTheDocument();
    expect(screen.getByText("NO_CHANGE")).toBeInTheDocument();
  });
});
