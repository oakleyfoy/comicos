import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
});
