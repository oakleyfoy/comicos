import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
          retailer_order_number: "4272232",
          order_date: "2026-06-08",
          order_status: "Shipped",
          order_total: "9.98",
          source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
          review_status: "captured",
          item_count: 4,
          cover_image_count: 4,
          product_url_count: 4,
          price_count: 4,
          release_date_count: 0,
          capture_quality_summary_json: {
            items_detected_client_side: 4,
            parser_items_parsed: 4,
          },
          parser_quality_summary_json: {
            item_blocks_found: 4,
            items_parsed: 4,
            items_skipped: 0,
          },
          raw_fields_summary_json: {
            retailer_order_number: "4272232",
          },
          updated_at: "2026-06-09T10:01:00Z",
          items: [
            {
              id: 1,
              retailer_item_id: "SKU-1",
              title: "Immortal Thor #1 Cover A",
              product_url: "https://www.midtowncomics.com/product/sku-1",
              image_url: "https://example.com/sku-1.jpg",
              thumbnail_url: "https://example.com/sku-1-thumb.jpg",
              publisher: "Marvel",
              issue_number: "#1",
              cover_name: "Cover A",
              variant_type: "Regular",
              cover_artist: "Artist One",
              quantity: 1,
              unit_price: "4.99",
              total_price: "4.99",
              item_status: "Pending",
              release_date: "2026-06-01",
              updated_at: "2026-06-09T10:01:00Z",
            },
            {
              id: 2,
              retailer_item_id: "SKU-2",
              title: "Immortal Thor #2 Cover A",
              product_url: "https://www.midtowncomics.com/product/sku-2",
              image_url: "https://example.com/sku-2.jpg",
              thumbnail_url: "https://example.com/sku-2-thumb.jpg",
              publisher: "Marvel",
              issue_number: "#2",
              cover_name: "Cover A",
              variant_type: "Regular",
              cover_artist: "Artist One",
              quantity: 1,
              unit_price: "4.99",
              total_price: "4.99",
              item_status: "Pending",
              release_date: "2026-06-08",
              updated_at: "2026-06-09T10:01:00Z",
            },
            {
              id: 3,
              retailer_item_id: "SKU-3",
              title: "Immortal Thor #3 Cover A",
              product_url: "https://www.midtowncomics.com/product/sku-3",
              image_url: "https://example.com/sku-3.jpg",
              thumbnail_url: "https://example.com/sku-3-thumb.jpg",
              publisher: "Marvel",
              issue_number: "#3",
              cover_name: "Cover A",
              variant_type: "Regular",
              cover_artist: "Artist One",
              quantity: 1,
              unit_price: "4.99",
              total_price: "4.99",
              item_status: "Pending",
              release_date: "2026-06-15",
              updated_at: "2026-06-09T10:01:00Z",
            },
            {
              id: 4,
              retailer_item_id: "SKU-4",
              title: "Immortal Thor #4 Cover A",
              product_url: "https://www.midtowncomics.com/product/sku-4",
              image_url: "https://example.com/sku-4.jpg",
              thumbnail_url: "https://example.com/sku-4-thumb.jpg",
              publisher: "Marvel",
              issue_number: "#4",
              cover_name: "Cover A",
              variant_type: "Regular",
              cover_artist: "Artist One",
              quantity: 1,
              unit_price: "4.99",
              total_price: "4.99",
              item_status: "Pending",
              release_date: "2026-06-22",
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
      orders: [
        {
          id: 1,
          retailer_account_id: 1,
          retailer: "midtown",
          retailer_order_number: "4272232",
          order_date: "2026-06-08",
          order_status: "Shipped",
          order_total: "19.96",
          source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
          review_status: "captured",
          item_count: 4,
          cover_image_count: 4,
          product_url_count: 4,
          price_count: 4,
          release_date_count: 0,
          capture_quality_summary_json: {
            items_detected_client_side: 4,
            parser_items_parsed: 4,
          },
          parser_quality_summary_json: {
            item_blocks_found: 4,
            items_parsed: 4,
            items_skipped: 0,
          },
          raw_fields_summary_json: {
            retailer_order_number: "4272232",
          },
          updated_at: "2026-06-09T10:03:00Z",
          items: [
            {
              id: 1,
              retailer_item_id: "SKU-1",
              title: "Immortal Thor #1 Cover A",
              product_url: "https://www.midtowncomics.com/product/sku-1",
              image_url: "https://example.com/sku-1.jpg",
              thumbnail_url: "https://example.com/sku-1-thumb.jpg",
              publisher: "Marvel",
              issue_number: "#1",
              cover_name: "Cover A",
              variant_type: "Regular",
              cover_artist: "Artist One",
              quantity: 1,
              unit_price: "4.99",
              total_price: "4.99",
              item_status: "Pending",
              release_date: "2026-06-01",
              updated_at: "2026-06-09T10:03:00Z",
            },
          ],
        },
      ],
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
      expect(screen.getAllByText(/Order #4272232/i).length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "Review Order" })).toBeInTheDocument();
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
    await waitFor(() => {
      expect(screen.getByText(/Waiting for Midtown capture/i)).toBeInTheDocument();
    });
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
              retailer_order_number: "4272232",
              fallback_order_number: "4272232",
              html: "<html>detail</html>",
              capture_diagnostics: {
                current_url: "https://www.midtowncomics.com/ord-info",
                ready_state: "complete",
                html_length: 2048,
                text_length: 512,
                body_inner_html_length: 1024,
                body_inner_text_length: 512,
                image_count: 2,
                product_link_count: 1,
                visible_order_item_block_count: 1,
                items_detected_client_side: 1,
                each_match_count: 1,
                qty_match_count: 1,
                status_match_count: 1,
                scroll_height: 900,
                scroll_position: 0,
              },
            },
          ],
        },
      }),
    );

    await waitFor(() => {
      expect(screen.getAllByText(/ComicOS found 1 possible items/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/partial capture/i).length).toBeGreaterThan(0);
    });

    const [sendCaptureButton] = screen.getAllByRole("button", { name: "Send Capture to ComicOS" });
    fireEvent.click(sendCaptureButton);

    await waitFor(() => {
      expect(apiClient.completeRetailerLocalSync).toHaveBeenCalledWith(1, 3, {
        helper_token: "capture-token",
        history_html: "<html>history</html>",
        detail_pages: [
          {
            detail_url: "https://www.midtowncomics.com/ord-info",
            retailer_order_number: "4272232",
            fallback_order_number: "4272232",
            html: "<html>detail</html>",
            capture_diagnostics: {
              current_url: "https://www.midtowncomics.com/ord-info",
              ready_state: "complete",
              html_length: 2048,
              text_length: 512,
              body_inner_html_length: 1024,
              body_inner_text_length: 512,
              image_count: 2,
              product_link_count: 1,
              visible_order_item_block_count: 1,
              items_detected_client_side: 1,
              each_match_count: 1,
              qty_match_count: 1,
              status_match_count: 1,
              scroll_height: 900,
              scroll_position: 0,
            },
          },
        ],
      });
    });
  });

  it("routes to the retailer order review page from the success card", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    window.dispatchEvent(new Event(MIDTOWN_EXTENSION_READY_EVENT));
    const [captureButton] = await screen.findAllByRole("button", { name: "Capture Midtown Order" });
    fireEvent.click(captureButton);
    await waitFor(() => {
      expect(screen.getByText(/Waiting for Midtown capture/i)).toBeInTheDocument();
    });
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
              capture_diagnostics: {
                current_url: "https://www.midtowncomics.com/account/orders/view/4272232",
                ready_state: "complete",
                html_length: 2048,
                text_length: 512,
                body_inner_html_length: 1024,
                body_inner_text_length: 512,
                image_count: 4,
                product_link_count: 4,
                visible_order_item_block_count: 4,
                items_detected_client_side: 4,
                each_match_count: 4,
                qty_match_count: 4,
                status_match_count: 4,
                scroll_height: 900,
                scroll_position: 0,
              },
            },
          ],
        },
      }),
    );

    const [openReviewButton] = await screen.findAllByRole("button", { name: "Review Retailer Order" });
    fireEvent.click(openReviewButton);
    expect(navigateMock).toHaveBeenCalledWith("/retailer-orders/1");
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

  it("blocks sending a capture when the Midtown DOM read is empty", async () => {
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
          review_status: "captured",
          item_count: 1,
          cover_image_count: 0,
          product_url_count: 0,
          price_count: 1,
          release_date_count: 0,
          capture_quality_summary_json: {},
          parser_quality_summary_json: {},
          raw_fields_summary_json: {},
          updated_at: "2026-06-09T10:01:00Z",
          items: [
            {
              id: 1,
              retailer_item_id: "SKU-1",
              title: "Absolute Batman #1 Cover A",
              quantity: 1,
              unit_price: "4.99",
              total_price: "4.99",
              updated_at: "2026-06-09T10:01:00Z",
            },
          ],
        },
      ],
    });

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
              capture_diagnostics: {
                current_url: "unknown",
                ready_state: "complete",
                html_length: 0,
                text_length: 0,
                body_inner_html_length: 0,
                body_inner_text_length: 0,
                image_count: 0,
                product_link_count: 0,
                visible_order_item_block_count: 0,
                items_detected_client_side: 0,
                each_match_count: 0,
                qty_match_count: 0,
                status_match_count: 0,
                scroll_height: 0,
                scroll_position: 0,
              },
            },
          ],
        },
      }),
    );

    await waitFor(() => {
      expect(
        screen.getAllByText("ComicOS could not read the Midtown page. Make sure the Midtown order tab is open and try again.").length,
      ).toBeGreaterThan(0);
      expect(screen.queryByRole("button", { name: "Send Capture to ComicOS" })).not.toBeInTheDocument();
    });
  });

  it("shows the retailer order review card after a successful capture", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    window.dispatchEvent(new Event(MIDTOWN_EXTENSION_READY_EVENT));
    const [captureButton] = await screen.findAllByRole("button", { name: "Capture Midtown Order" });
    fireEvent.click(captureButton);
    await waitFor(() => {
      expect(screen.getByText(/Waiting for Midtown capture/i)).toBeInTheDocument();
    });
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
              capture_diagnostics: {
                current_url: "https://www.midtowncomics.com/account/orders/view/4272232",
                ready_state: "complete",
                html_length: 2048,
                text_length: 512,
                body_inner_html_length: 1024,
                body_inner_text_length: 512,
                image_count: 4,
                product_link_count: 4,
                visible_order_item_block_count: 4,
                items_detected_client_side: 4,
                each_match_count: 4,
                qty_match_count: 4,
                status_match_count: 4,
                scroll_height: 900,
                scroll_position: 0,
              },
            },
          ],
        },
      }),
    );

    const [sendCaptureButton] = await screen.findAllByRole("button", { name: "Send Capture to ComicOS" });
    fireEvent.click(sendCaptureButton);

    await waitFor(
      () => {
        expect(screen.getAllByText("Retailer Order Captured").length).toBeGreaterThan(0);
      },
      { timeout: 3000 },
    );
    expect(screen.getAllByText(/Order #4272232/i).length).toBeGreaterThan(0);
    const successHeading = screen.getAllByText("Retailer Order Captured")[0];
    const successSection = successHeading.closest("section");
    expect(successSection).not.toBeNull();
    expect(
      within(successSection as HTMLElement).getByRole("button", { name: "Review Retailer Order" }),
    ).toBeInTheDocument();
    expect(within(successSection as HTMLElement).getAllByText(/4 items/).length).toBeGreaterThan(0);
  });
});
