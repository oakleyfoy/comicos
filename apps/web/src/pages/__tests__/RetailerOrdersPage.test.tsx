import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { RetailerOrdersPage } from "../RetailerOrdersPage";

let navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
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

describe("RetailerOrdersPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "getRetailerOrders").mockResolvedValue({
      items: [
        {
          id: 11,
          retailer_account_id: 1,
          retailer: "midtown",
          retailer_order_number: "4272232",
          order_date: "2026-06-08",
          order_status: "Shipped",
          order_total: "104.79",
          source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
          review_status: "captured",
          item_count: 21,
          cover_image_count: 21,
          product_url_count: 21,
          price_count: 21,
          release_date_count: 8,
          capture_quality_summary_json: {},
          parser_quality_summary_json: {},
          raw_fields_summary_json: {},
          updated_at: "2026-06-09T10:01:00Z",
          items: [],
        },
        {
          id: 12,
          retailer_account_id: 1,
          retailer: "midtown",
          retailer_order_number: "5550001",
          order_date: "2026-06-07",
          order_status: "Pending",
          order_total: "19.98",
          source_url: "https://www.midtowncomics.com/account/orders/view/5550001",
          review_status: "confirmed",
          item_count: 2,
          cover_image_count: 2,
          product_url_count: 2,
          price_count: 2,
          release_date_count: 0,
          capture_quality_summary_json: {},
          parser_quality_summary_json: {},
          raw_fields_summary_json: {},
          updated_at: "2026-06-09T10:02:00Z",
          items: [],
        },
      ],
    });
  });

  it("lists retailer orders and opens the detail page", async () => {
    render(
      <MemoryRouter>
        <RetailerOrdersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Retailer Orders" })).toBeInTheDocument();
    expect(screen.getByText("midtown Order #4272232")).toBeInTheDocument();
    expect(screen.getByText("midtown Order #5550001")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Review Order" })).toHaveLength(2);

    fireEvent.click(screen.getAllByRole("button", { name: "Review Order" })[0]);
    expect(navigateMock).toHaveBeenCalledWith("/retailer-orders/11");
  });
});
