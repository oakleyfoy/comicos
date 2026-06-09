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
    vi.spyOn(window, "open").mockImplementation(
      () =>
        ({
          name: "",
          location: { href: "about:blank" },
          document: { write: vi.fn() },
          close: vi.fn(),
        }) as unknown as Window,
    );
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
    vi.spyOn(apiClient, "startRetailerLocalSync").mockResolvedValue({
      account: {
        id: 1,
        retailer: "midtown",
        display_name: "Midtown Comics",
        masked_username: "co********@example.com",
        credential_version: 1,
        status: "awaiting_browser",
        sync_enabled: true,
        last_sync_at: "2026-06-09T10:00:00Z",
        last_success_at: "2026-06-09T10:01:00Z",
        last_error: null,
        created_at: "2026-06-09T09:00:00Z",
        updated_at: "2026-06-09T10:01:00Z",
      },
      run: {
        id: 3,
        retailer_account_id: 1,
        retailer: "midtown",
        status: "awaiting_browser",
        started_at: "2026-06-09T10:02:00Z",
        finished_at: null,
        orders_seen: 0,
        orders_imported: 0,
        items_seen: 0,
        items_imported: 0,
        items_updated: 0,
        errors_count: 0,
        summary_json: {},
        error_message: null,
      },
      helper_token: "helper-token",
      helper_token_expires_at: "2999-01-01T00:00:00Z",
      capture_url: "https://www.midtowncomics.com/account-settings",
      helper_mode: "bookmarklet",
    });
    vi.spyOn(apiClient, "completeRetailerLocalSync").mockResolvedValue({
      account: {
        id: 1,
        retailer: "midtown",
        display_name: "Midtown Comics",
        masked_username: "co********@example.com",
        credential_version: 1,
        status: "connected",
        sync_enabled: true,
        last_sync_at: "2026-06-09T10:03:00Z",
        last_success_at: "2026-06-09T10:03:00Z",
        last_error: null,
        created_at: "2026-06-09T09:00:00Z",
        updated_at: "2026-06-09T10:03:00Z",
      },
      run: {
        id: 3,
        retailer_account_id: 1,
        retailer: "midtown",
        status: "succeeded",
        started_at: "2026-06-09T10:02:00Z",
        finished_at: "2026-06-09T10:03:00Z",
        orders_seen: 1,
        orders_imported: 1,
        items_seen: 1,
        items_imported: 1,
        items_updated: 0,
        errors_count: 0,
        summary_json: { sync_path: "browser_assisted", touched_import_ids: [101] },
        error_message: null,
      },
      orders: [],
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

  it("shows Midtown challenge guidance and pauses retries during cooldown", async () => {
    vi.mocked(apiClient.getRetailerAccounts).mockResolvedValue({
      items: [
        {
          id: 1,
          retailer: "midtown",
          display_name: "Midtown Comics",
          masked_username: "co********@example.com",
          credential_version: 1,
          status: "needs_attention",
          sync_enabled: true,
          last_sync_at: "2026-06-09T10:00:00Z",
          last_success_at: "2026-06-09T09:00:00Z",
          last_error: "Midtown presented a CAPTCHA or security challenge.",
          created_at: "2026-06-09T09:00:00Z",
          updated_at: "2026-06-09T10:01:00Z",
        },
      ],
    });
    vi.mocked(apiClient.getRetailerAccountSyncRuns).mockResolvedValue({
      items: [
        {
          id: 2,
          retailer_account_id: 1,
          retailer: "midtown",
          status: "needs_attention",
          started_at: "2026-06-09T10:00:00Z",
          finished_at: "2026-06-09T10:01:00Z",
          orders_seen: 0,
          orders_imported: 0,
          items_seen: 0,
          items_imported: 0,
          items_updated: 0,
          errors_count: 1,
          summary_json: {
            error_code: "captcha_or_security",
            challenge_detected: true,
            action_required: "Wait before retrying and avoid repeated sync attempts.",
            retry_allowed_at: "2999-01-01T00:00:00Z",
          },
          error_message: "Midtown presented a CAPTCHA or security challenge.",
        },
      ],
    });

    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Midtown challenge handling")).toBeInTheDocument();
    expect(screen.getAllByText(/Retry after:/i)).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Retry Later" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sync Paused" })).toBeDisabled();
  });

  it("starts browser-assisted Midtown sync and opens Midtown", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    const [startButton] = await screen.findAllByRole("button", { name: "Start Browser Sync" });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(apiClient.startRetailerLocalSync).toHaveBeenCalledWith(1, { limit_orders: 25 });
      expect(screen.getByText(/Midtown browser sync started/i)).toBeInTheDocument();
      expect(screen.getByText(/Waiting for Midtown browser capture/i)).toBeInTheDocument();
    });
  });

  it("completes browser-assisted Midtown sync from Midtown helper message", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    const headings = await screen.findAllByRole("heading", { name: "Connected Retailers" });
    expect(headings.length).toBeGreaterThan(0);
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://www.midtowncomics.com",
        data: {
          type: "comicos_midtown_local_sync_capture",
          accountId: 1,
          syncRunId: 3,
          helperToken: "helper-token",
          historyHtml: "<html>history</html>",
          detailPages: [],
        },
      }),
    );

    await waitFor(() => {
      expect(apiClient.completeRetailerLocalSync).toHaveBeenCalledWith(1, 3, {
        helper_token: "helper-token",
        history_html: "<html>history</html>",
        detail_pages: [],
      });
    });
  });
});
