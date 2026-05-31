import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { DataProtectionPage } from "../DataProtectionPage";

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

describe("DataProtectionPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getDataIntegrityChecks").mockResolvedValue({
      items: [
        {
          id: 1,
          owner_user_id: 1,
          check_uuid: "check-1",
          check_type: "full",
          check_status: "WARNING",
          checked_at: "2026-05-30T12:00:00Z",
          summary_json: { issue_count: 2 },
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      pagination: { total_count: 1, limit: 5, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getDataIntegrityIssues").mockResolvedValue({
      items: [
        {
          id: 1,
          check_id: 1,
          issue_type: "invalid_order_total",
          severity: "HIGH",
          entity_type: "order",
          entity_id: 12,
          issue_message: "Order totals are internally inconsistent.",
          issue_payload_json: {},
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      pagination: { total_count: 1, limit: 5, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getMigrationSafetyChecks").mockResolvedValue({
      items: [
        {
          id: 1,
          owner_user_id: 1,
          migration_revision: "20260805_0154",
          check_status: "PASS",
          pre_count_json: { orders: 1 },
          post_count_json: { orders: 1 },
          validation_payload_json: { comparison: { orders: { pre: 1, post: 1, delta: 0 } } },
          checked_at: "2026-05-30T12:00:00Z",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      pagination: { total_count: 1, limit: 5, offset: 0, has_next: false, next_cursor: null },
    });
    vi.spyOn(apiClient, "getAuditEvents").mockResolvedValue({
      items: [
        {
          id: 1,
          owner_user_id: 1,
          audit_uuid: "audit-1",
          actor_id: 1,
          actor_type: "user",
          action_type: "inventory_update",
          entity_type: "inventory_copy",
          entity_id: 44,
          source: "dashboard_test",
          event_payload_json: { changed_field_count: 2 },
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      pagination: { total_count: 1, limit: 5, offset: 0, has_next: false, next_cursor: null },
    });
  });

  it("renders integrity and audit sections", async () => {
    render(
      <MemoryRouter>
        <DataProtectionPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Data Protection" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Data Integrity Status")).toBeInTheDocument();
      expect(screen.getAllByText("Latest Integrity Check").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Open Issues").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Migration Safety Status").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Recent Audit Events").length).toBeGreaterThan(0);
      expect(screen.getByText("Change Tracking Summary")).toBeInTheDocument();
      expect(screen.getAllByText("inventory_update").length).toBeGreaterThan(0);
    });
  });
});
