import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ConnectedRetailersPage } from "../ConnectedRetailersPage";

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

describe("ConnectedRetailersPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getRetailerAccounts").mockResolvedValue({
      items: [
        {
          id: 1,
          retailer: "midtown",
          display_name: "Midtown Comics",
          masked_username: "co********@example.com",
          credential_version: 1,
          status: "connected",
          sync_enabled: true,
          last_sync_at: "2026-06-09T10:00:00Z",
          last_success_at: "2026-06-09T10:01:00Z",
          last_error: null,
          created_at: "2026-06-09T09:00:00Z",
          updated_at: "2026-06-09T10:01:00Z",
        },
      ],
    });
    vi.spyOn(apiClient, "getRetailerOrders").mockResolvedValue({
      items: [
        {
          id: 1,
          retailer_account_id: 1,
          retailer: "midtown",
          retailer_order_number: "ABC123",
          order_date: "2026-06-08",
          order_status: "Shipped",
          order_total: "9.98",
          source_url: "https://www.midtowncomics.com/account/orders/view/ABC123",
          updated_at: "2026-06-09T10:01:00Z",
          items: [
            {
              id: 1,
              retailer_item_id: "SKU-1",
              title: "Immortal Thor #1 Cover A",
              quantity: 1,
              unit_price: "4.99",
              updated_at: "2026-06-09T10:01:00Z",
            },
          ],
        },
      ],
    });
    vi.spyOn(apiClient, "getRetailerAccountSyncRuns").mockResolvedValue({
      items: [
        {
          id: 1,
          retailer_account_id: 1,
          retailer: "midtown",
          status: "succeeded",
          started_at: "2026-06-09T10:00:00Z",
          finished_at: "2026-06-09T10:01:00Z",
          orders_seen: 1,
          orders_imported: 1,
          items_seen: 1,
          items_imported: 1,
          items_updated: 0,
          errors_count: 0,
          summary_json: {},
          error_message: null,
        },
      ],
    });
    vi.spyOn(apiClient, "updateRetailerAccount").mockResolvedValue({
      id: 1,
      retailer: "midtown",
      display_name: "Midtown Comics",
      masked_username: "co********@example.com",
      credential_version: 1,
      status: "connected",
      sync_enabled: false,
      last_sync_at: "2026-06-09T10:00:00Z",
      last_success_at: "2026-06-09T10:01:00Z",
      last_error: null,
      created_at: "2026-06-09T09:00:00Z",
      updated_at: "2026-06-09T10:01:00Z",
    });
  });

  it("renders connected retailer account details and orders", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Connected Retailers" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Stored username:")).toBeInTheDocument();
      expect(screen.getByText(/co\*+/)).toBeInTheDocument();
      expect(screen.getByText("Order #ABC123")).toBeInTheDocument();
      expect(screen.getByText("Sync History")).toBeInTheDocument();
    });
  });

  it("updates sync enabled through the page", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    const [checkbox] = await screen.findAllByRole("checkbox", { name: /Enable sync for this account/i });
    fireEvent.click(checkbox);
    await waitFor(() => {
      expect(apiClient.updateRetailerAccount).toHaveBeenCalledWith(1, { sync_enabled: false });
    });
  });
});
