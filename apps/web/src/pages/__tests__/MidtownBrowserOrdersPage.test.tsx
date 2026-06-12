import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { MidtownBrowserOrdersPage } from "../MidtownBrowserOrdersPage";

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

describe("MidtownBrowserOrdersPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "goToMidtownBrowserOrders").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: null,
        current_url: "https://www.midtowncomics.com/account-settings",
        orders_url: "https://www.midtowncomics.com/account-settings",
        authenticated: true,
        order_count: 1,
        last_updated_at: "2026-06-10T20:00:00Z",
      },
      orders: [
        {
          retailer_order_number: "4272232",
          order_date: "2026-06-08",
          order_status: "Shipped",
          order_total: "9.98",
          item_count: 4,
          detail_url: "https://www.midtowncomics.com/account/orders/view/4272232",
        },
      ],
    });
    vi.spyOn(apiClient, "captureMidtownBrowserOrder").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "captured",
        message: "Midtown order captured inside ComicOS.",
        current_url: "https://www.midtowncomics.com/account/orders/view/4272232",
        orders_url: "https://www.midtowncomics.com/account-settings",
        authenticated: true,
        order_count: 1,
        last_updated_at: "2026-06-10T20:00:00Z",
      },
      order_id: 17,
      retailer_order_number: "4272232",
    });
  });

  it("lists Midtown orders and opens the retailer order review page", async () => {
    render(
      <MemoryRouter>
        <MidtownBrowserOrdersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Choose an order to add to your inventory" })).toBeInTheDocument();
    expect(screen.getByText("Order #4272232")).toBeInTheDocument();
    const selectButton = await screen.findByRole("button", { name: "Select Order" });
    await waitFor(() => {
      expect(selectButton).not.toBeDisabled();
    });
    fireEvent.click(selectButton);

    await waitFor(() => {
      expect(apiClient.captureMidtownBrowserOrder).toHaveBeenCalledWith("4272232");
      expect(navigateMock).toHaveBeenCalledWith("/retailer-orders/17");
    });
  });

  it("shows the security verification handoff and can retry loading orders", async () => {
    const ordersSpy = vi.spyOn(apiClient, "goToMidtownBrowserOrders").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "security_verification_required",
        message: "Midtown requires security verification.",
        current_url: "https://www.midtowncomics.com/verify",
        orders_url: "https://www.midtowncomics.com/account-settings",
        authenticated: false,
        order_count: 0,
        last_updated_at: "2026-06-10T20:00:00Z",
      },
      orders: [],
    });

    render(
      <MemoryRouter>
        <MidtownBrowserOrdersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Security verification required" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Complete Security Verification" }));
    expect(navigateMock).toHaveBeenCalledWith("/connected-retailers/midtown");

    fireEvent.click(screen.getByRole("button", { name: "Retry Loading Orders" }));
    await waitFor(() => {
      expect(ordersSpy).toHaveBeenCalledTimes(2);
    });
  });

  it("updates Midtown login in a modal and retries loading orders", async () => {
    const ordersSpy = vi.spyOn(apiClient, "goToMidtownBrowserOrders").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "login_required",
        message: "Midtown login is required.",
        current_url: "https://www.midtowncomics.com/login",
        orders_url: "https://www.midtowncomics.com/account-settings",
        authenticated: false,
        order_count: 0,
        last_updated_at: "2026-06-10T20:00:00Z",
      },
      orders: [],
    });
    vi.spyOn(apiClient, "getRetailerAccounts").mockResolvedValue({
      items: [
        {
          id: 7,
          retailer: "midtown",
          display_name: "Midtown Comics",
          masked_username: "co********@example.com",
          credential_version: 1,
          status: "needs_attention",
          sync_enabled: true,
          last_sync_at: null,
          last_success_at: null,
          last_error: null,
          created_at: "2026-06-09T09:00:00Z",
          updated_at: "2026-06-09T10:01:00Z",
        },
      ],
    });
    const updateSpy = vi.spyOn(apiClient, "updateRetailerAccount").mockResolvedValue({
      id: 7,
      retailer: "midtown",
      display_name: "Midtown Comics",
      masked_username: "ne********@example.com",
      credential_version: 2,
      status: "connected",
      sync_enabled: true,
      last_sync_at: null,
      last_success_at: null,
      last_error: null,
      created_at: "2026-06-09T09:00:00Z",
      updated_at: "2026-06-11T10:01:00Z",
    });

    render(
      <MemoryRouter>
        <MidtownBrowserOrdersPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Update Midtown Login" }));

    const dialog = await screen.findByRole("dialog", { name: "Update Midtown login" });
    expect(navigateMock).not.toHaveBeenCalledWith("/connected-retailers");

    fireEvent.change(within(dialog).getByLabelText("Username or email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(within(dialog).getByLabelText("New password"), {
      target: { value: "freshpass" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save & Retry" }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(7, { username: "new@example.com", password: "freshpass" });
      expect(ordersSpy).toHaveBeenCalledTimes(2);
    });
  });
});
