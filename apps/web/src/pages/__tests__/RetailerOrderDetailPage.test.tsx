import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { RetailerOrderDetailPage } from "../RetailerOrderDetailPage";

let navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useParams: () => ({ id: "11" }),
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

describe("RetailerOrderDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "getRetailerOrder").mockResolvedValue({
      id: 11,
      retailer_account_id: 1,
      retailer: "midtown",
      retailer_order_number: "4272232",
      order_date: "2026-06-08",
      order_status: "Shipped",
      order_total: "104.79",
      source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
      review_status: "captured",
      item_count: 2,
      cover_image_count: 1,
      product_url_count: 1,
      price_count: 2,
      release_date_count: 1,
      capture_quality_summary_json: {
        items_detected_client_side: 2,
        html_length: 2048,
      },
      parser_quality_summary_json: {
        item_blocks_found: 2,
        items_parsed: 2,
      },
      raw_fields_summary_json: {
        retailer_order_number: "4272232",
      },
      updated_at: "2026-06-09T10:01:00Z",
      items: [
        {
          id: 1,
          retailer_item_id: "SKU-1",
          product_url: "https://www.midtowncomics.com/product/sku-1",
          image_url: "https://example.com/sku-1.jpg",
          thumbnail_url: "https://example.com/sku-1-thumb.jpg",
          title: "Immortal Thor #1 Cover A",
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
          product_url: null,
          image_url: null,
          thumbnail_url: null,
          title: "Immortal Thor #2 Cover A",
          publisher: "Marvel",
          issue_number: "#2",
          cover_name: "Cover A",
          variant_type: "Regular",
          cover_artist: "Artist One",
          quantity: 1,
          unit_price: "4.99",
          total_price: "4.99",
          item_status: "Pending",
          release_date: null,
          updated_at: "2026-06-09T10:01:00Z",
        },
      ],
    });
    vi.spyOn(apiClient, "confirmRetailerOrder").mockResolvedValue({
      id: 11,
      retailer_account_id: 1,
      retailer: "midtown",
      retailer_order_number: "4272232",
      order_date: "2026-06-08",
      order_status: "Shipped",
      order_total: "104.79",
      source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
      review_status: "confirmed",
      item_count: 2,
      cover_image_count: 1,
      product_url_count: 1,
      price_count: 2,
      release_date_count: 1,
      capture_quality_summary_json: {
        items_detected_client_side: 2,
        html_length: 2048,
      },
      parser_quality_summary_json: {
        item_blocks_found: 2,
        items_parsed: 2,
      },
      raw_fields_summary_json: {
        retailer_order_number: "4272232",
      },
      updated_at: "2026-06-09T10:02:00Z",
      items: [],
    });
  });

  it("renders the retailer order review workspace and confirms the order", async () => {
    render(
      <MemoryRouter>
        <RetailerOrderDetailPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: /Retailer Order/i })).toBeInTheDocument();
    expect(screen.getByText("midtown Order #4272232")).toBeInTheDocument();
    expect(screen.getByText("Items parsed")).toBeInTheDocument();
    expect(screen.getByText("Covers found")).toBeInTheDocument();
    expect(screen.getByText("Product links found")).toBeInTheDocument();
    expect(screen.getByText("Prices found")).toBeInTheDocument();
    expect(screen.getByText("Release dates found")).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(screen.getByText("No cover image")).toBeInTheDocument();
    expect(screen.getByText("Product URL missing")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Confirm Retailer Order" }));

    await waitFor(() => {
      expect(apiClient.confirmRetailerOrder).toHaveBeenCalledWith(11);
      expect(screen.getByText("confirmed")).toBeInTheDocument();
      expect(screen.getByText("Retailer order confirmed.")).toBeInTheDocument();
    });
  });
});
