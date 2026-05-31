import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ProductionReadinessPage } from "../ProductionReadinessPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions}
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("ProductionReadinessPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getProductionReadinessDashboard").mockResolvedValue({
      readiness_score: 88.5,
      certification_status: "CONDITIONAL",
      marketplace_status: "PASS",
      forecast_status: "WARNING",
      data_protection_status: "PASS",
      operations_status: "PASS",
      agent_platform_status: "PASS",
      checklist_pass_count: 5,
      checklist_total: 8,
      go_live_status: "CONDITIONAL",
      latest_certification: {
        id: 1,
        certification_uuid: "cert-1",
        certification_status: "CONDITIONAL",
        readiness_score: 88.5,
        certification_notes: "Production certification CONDITIONAL with readiness score 88.5.",
        certified_at: "2026-05-30T12:00:00Z",
      },
      latest_assessment: {
        id: 1,
        assessment_uuid: "assess-1",
        assessment_status: "CONDITIONAL",
        overall_score: 88.5,
        assessment_summary: "Go-live assessment CONDITIONAL for Oakley personal production use.",
        assessed_at: "2026-05-30T12:00:00Z",
      },
    });
  });

  it("renders production readiness dashboard sections", async () => {
    render(
      <MemoryRouter>
        <ProductionReadinessPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Production Readiness" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("Overall Readiness Score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Certification Status").length).toBeGreaterThan(0);
    expect(screen.getByText("Platform Status")).toBeInTheDocument();
    expect(screen.getAllByText("Go-Live Assessment").length).toBeGreaterThan(0);
    expect(screen.getByText("Marketplace")).toBeInTheDocument();
  });
});
