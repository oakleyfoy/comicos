import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MarketplaceDashboardPage } from "../MarketplaceDashboardPage";
import { apiClient } from "../../api/client";

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

describe("MarketplaceDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getMarketplaceDashboard").mockResolvedValue({
      validation_status: "PASS",
      health_status: "HEALTHY",
      platform_certified: true,
      summary_cards: {
        listings: 4,
        publish_jobs: 2,
        orders: 1,
        reservations: 0,
        sync_plans: 1,
      },
      validation_checks: [
        {
          check_code: "connectors",
          title: "Connector Framework",
          status: "PASS",
          summary: "Connectors validated.",
          details_json: {},
        },
        {
          check_code: "publish_engine",
          title: "Publish Engine",
          status: "PASS",
          summary: "Publish engine validated.",
          details_json: {},
        },
        {
          check_code: "inventory_sync",
          title: "Inventory Sync",
          status: "WARNING",
          summary: "No sync plans yet.",
          details_json: {},
        },
        {
          check_code: "order_import",
          title: "Order Import",
          status: "PASS",
          summary: "Orders validated.",
          details_json: {},
        },
      ],
      health_components: [
        {
          component_code: "connector_health",
          title: "Connector Health",
          health_status: "HEALTHY",
          summary: "Connectors healthy.",
          details_json: {},
        },
        {
          component_code: "account_health",
          title: "Account Health",
          health_status: "WARNING",
          summary: "No accounts linked.",
          details_json: {},
        },
        {
          component_code: "publish_health",
          title: "Publish Health",
          health_status: "HEALTHY",
          summary: "Publish jobs healthy.",
          details_json: {},
        },
        {
          component_code: "sync_health",
          title: "Sync Health",
          health_status: "WARNING",
          summary: "Sync idle.",
          details_json: {},
        },
      ],
    });
    vi.spyOn(apiClient, "getMarketplaceDashboardValidation").mockResolvedValue({
      overall_status: "PASS",
      platform_certified: true,
      checks: [],
    });
    vi.spyOn(apiClient, "getMarketplaceDashboardHealth").mockResolvedValue({
      overall_status: "HEALTHY",
      components: [],
    });
  });

  it("renders summary cards and platform panels", async () => {
    render(
      <MemoryRouter>
        <MarketplaceDashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Marketplace Platform" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Listings")).toBeInTheDocument();
      expect(screen.getByText("4")).toBeInTheDocument();
      expect(screen.getByText("Connector Health")).toBeInTheDocument();
      expect(screen.getByText("Connector Validation")).toBeInTheDocument();
      expect(screen.getByText("Certified")).toBeInTheDocument();
    });
  });
});
