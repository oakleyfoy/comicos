import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ReleasePlatformCertificationPage } from "../ReleasePlatformCertificationPage";

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

describe("ReleasePlatformCertificationPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getReleasePlatformSummary").mockResolvedValue({
      total_releases: 120,
      total_series: 40,
      total_variants: 85,
      total_new_number_ones: 12,
      total_opportunities: 30,
      total_watchlists: 2,
      total_foc_alerts: 5,
      platform_readiness_score: 92.2,
      scheduler: {
        scheduler_enabled: true,
        schedule_time_utc: "06:00",
        last_scheduled_run_status: "COMPLETED",
        last_scheduled_run_at: "2026-05-30T06:00:00Z",
      },
      import_summary: {
        last_import_at: "2026-05-29T12:00:00Z",
        last_successful_import_at: "2026-05-29T12:00:00Z",
        last_failed_import_at: null,
        last_import_status: "COMPLETED",
        last_import_records_processed: 500,
        total_import_runs: 3,
      },
    });
    vi.spyOn(apiClient, "getReleasePlatformHealth").mockResolvedValue({
      overall_status: "HEALTHY",
      components: [
        {
          component_code: "release_feed",
          title: "Release Feed",
          health_status: "HEALTHY",
          summary: "ok",
          details_json: {},
        },
      ],
    });
    vi.spyOn(apiClient, "getReleasePlatformValidation").mockResolvedValue({
      overall_status: "PASS",
      platform_certified: true,
      checks: [
        {
          check_code: "release_intelligence",
          title: "Release Intelligence",
          status: "PASS",
          summary: "ok",
          details_json: {},
        },
      ],
    });
    vi.spyOn(apiClient, "getReleasePlatformCertification").mockResolvedValue({
      platform_certified: true,
      validation_status: "PASS",
      health_status: "HEALTHY",
      summary: "Certified",
      go_live_recommendation: "APPROVED_FOR_PRODUCTION",
      certification_date: "2026-05-30T12:00:00Z",
      certification_version: "P50-05",
      certification_notes: ["Release platform ready for production."],
    });
  });

  it("renders release platform certification dashboard", async () => {
    render(
      <MemoryRouter>
        <ReleasePlatformCertificationPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Release Platform Certification" })).toBeInTheDocument();
    });

    expect(screen.getByText("Certification Status")).toBeInTheDocument();
    expect(screen.getByText("Subsystem Validation")).toBeInTheDocument();
    expect(screen.getByText("Release Statistics")).toBeInTheDocument();
    expect(screen.getByText("Import & Scheduler")).toBeInTheDocument();
  });
});
