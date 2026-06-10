import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import {
  MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT,
  MIDTOWN_EXTENSION_READY_EVENT,
} from "../../lib/midtownExtensionBridge";
import { ConnectedRetailersPage } from "../ConnectedRetailersPage";

let navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

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
    navigateMock = vi.fn();
    vi.stubEnv("VITE_MIDTOWN_EXTENSION_INSTALL_URL", "https://example.com/midtown-extension");
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
          draft_import_id: 101,
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
            {
              id: 2,
              retailer_item_id: "SKU-2",
              title: "Immortal Thor #2 Cover A",
              quantity: 1,
              unit_price: "4.99",
              updated_at: "2026-06-09T10:01:00Z",
            },
            {
              id: 3,
              retailer_item_id: "SKU-3",
              title: "Immortal Thor #3 Cover A",
              quantity: 1,
              unit_price: "4.99",
              updated_at: "2026-06-09T10:01:00Z",
            },
            {
              id: 4,
              retailer_item_id: "SKU-4",
              title: "Immortal Thor #4 Cover A",
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
          summary_json: { touched_import_ids: [101] },
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
      helper_token: "capture-token",
      helper_token_expires_at: "2999-01-01T00:00:00Z",
      capture_url: "https://www.midtowncomics.com/account-settings",
      capture_mode: "extension",
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

  afterEach(() => {
    vi.unstubAllEnvs();
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
      expect(screen.getByRole("button", { name: "Review Import" })).toBeInTheDocument();
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

  it("explains the first-time setup when the install URL is missing", async () => {
    vi.unstubAllEnvs();

    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    const headings = await screen.findAllByText("New here? Follow these 3 steps.");
    expect(headings.length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Install Midtown Extension" })).toBeDisabled();
    expect(screen.getByText(/The store link is not configured yet/i)).toBeInTheDocument();
    const statusLabels = await screen.findAllByText("Extension not detected");
    expect(statusLabels.length).toBeGreaterThan(0);
  });

  it("starts Midtown capture when the extension is ready", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    window.dispatchEvent(new Event(MIDTOWN_EXTENSION_READY_EVENT));

    await waitFor(async () => {
      const buttons = await screen.findAllByRole("button", { name: "Capture Midtown Order" });
      expect(buttons[0]).not.toBeDisabled();
    });

    const [captureButton] = await screen.findAllByRole("button", { name: "Capture Midtown Order" });
    fireEvent.click(captureButton);

    await waitFor(() => {
      expect(apiClient.startRetailerLocalSync).toHaveBeenCalledWith(1, { limit_orders: 1 });
      expect(screen.getByText(/Midtown capture started/i)).toBeInTheDocument();
      expect(screen.getByText(/Waiting for Midtown capture/i)).toBeInTheDocument();
      expect(screen.getAllByText("Extension connected").length).toBeGreaterThan(0);
    });
  });

  it("completes Midtown capture from the extension result event", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    window.dispatchEvent(new Event(MIDTOWN_EXTENSION_READY_EVENT));
    const headings = await screen.findAllByRole("heading", { name: "Connected Retailers" });
    expect(headings.length).toBeGreaterThan(0);

    const [captureButton] = await screen.findAllByRole("button", { name: "Capture Midtown Order" });
    fireEvent.click(captureButton);
    window.dispatchEvent(
      new CustomEvent(MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT, {
        detail: {
          type: MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT,
          accountId: 1,
          syncRunId: 3,
          captureToken: "capture-token",
          historyHtml: "<html>history</html>",
          detailPages: [
            {
              detail_url: "https://www.midtowncomics.com/ord-info",
              retailer_order_number: "ABC123",
              fallback_order_number: "ABC123",
              html: "<html>detail</html>",
            },
          ],
        },
      }),
    );

    await waitFor(() => {
      expect(apiClient.completeRetailerLocalSync).toHaveBeenCalledWith(1, 3, {
        helper_token: "capture-token",
        history_html: "<html>history</html>",
        detail_pages: [
          {
            detail_url: "https://www.midtowncomics.com/ord-info",
            retailer_order_number: "ABC123",
            fallback_order_number: "ABC123",
            html: "<html>detail</html>",
          },
        ],
      });
    });
  });

  it("opens import review for the touched Midtown draft", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    window.dispatchEvent(new Event(MIDTOWN_EXTENSION_READY_EVENT));
    const [captureButton] = await screen.findAllByRole("button", { name: "Capture Midtown Order" });
    fireEvent.click(captureButton);
    window.dispatchEvent(
      new CustomEvent(MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT, {
        detail: {
          type: MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT,
          accountId: 1,
          syncRunId: 3,
          captureToken: "capture-token",
          historyHtml: "<html>history</html>",
          detailPages: [
            {
              detail_url: "https://www.midtowncomics.com/account/orders/view/4272232",
              retailer_order_number: "4272232",
              fallback_order_number: "4272232",
              html: "<html>detail</html>",
            },
          ],
        },
      }),
    );

    const [openReviewButton] = await screen.findAllByRole("button", { name: "Open Import Review" });
    fireEvent.click(openReviewButton);
    expect(navigateMock).toHaveBeenCalledWith("/orders/import?importId=101");
  });

  it("expands the order card to show all snapshot items", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    expect(screen.queryByText("Immortal Thor #4 Cover A")).not.toBeInTheDocument();

    const [viewDetailsButton] = await screen.findAllByRole("button", { name: "View Details" });
    fireEvent.click(viewDetailsButton);

    expect(await screen.findByText(/Immortal Thor #4 Cover A/)).toBeInTheDocument();
  });

  it("creates a review draft when the order has no draft yet", async () => {
    vi.spyOn(apiClient, "getRetailerOrders").mockResolvedValueOnce({
      items: [
        {
          id: 2,
          retailer_account_id: 1,
          retailer: "midtown",
          retailer_order_number: "4272232",
          order_date: "2026-06-08",
          order_status: "Shipped",
          order_total: "104.79",
          source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
          draft_import_id: null,
          updated_at: "2026-06-09T10:01:00Z",
          items: [
            {
              id: 1,
              retailer_item_id: "SKU-1",
              title: "Absolute Batman #1 Cover A",
              quantity: 1,
              unit_price: "4.99",
              updated_at: "2026-06-09T10:01:00Z",
            },
          ],
        },
      ],
    });
    vi.spyOn(apiClient, "createRetailerOrderReviewDraft").mockResolvedValue({
      id: 202,
      raw_text: "Retailer account sync import for Midtown Comics order #4272232.",
      parsed_payload_json: {
        retailer: "Midtown Comics",
        order_date: "2026-06-08",
        source_type: "retailer_account",
        shipping_amount: "0.00",
        tax_amount: "0.00",
        order_total: "104.79",
        total_books: 1,
        warnings: [],
        confidence_score: 1,
        items: [],
      } as never,
      confidence_score: "1.00",
      status: "draft",
      order_id: null,
      created_at: "2026-06-09T10:00:00Z",
      updated_at: "2026-06-09T10:00:00Z",
      cover_images: [],
      cover_image_count: 0,
    });

    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Create Review Draft" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Create Review Draft" }));

    await waitFor(() => {
      expect(apiClient.createRetailerOrderReviewDraft).toHaveBeenCalledWith(2);
      expect(navigateMock).toHaveBeenCalledWith("/orders/import?importId=202");
    });
  });
});
