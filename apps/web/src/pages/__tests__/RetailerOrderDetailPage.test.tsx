import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ApiError } from "../../api/apiError";
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
    expect(screen.getByText("No cover")).toBeInTheDocument();
    // "Product URL missing" is no longer a user-facing warning (optional enrichment).
    expect(screen.queryByText("Product URL missing")).not.toBeInTheDocument();
    // A missing release date reads as pending catalog review, not an import failure.
    expect(screen.getByText(/Catalog review pending/)).toBeInTheDocument();

    // Review covers must render as constrained thumbnails, never full-width.
    const covers = screen.getAllByTestId("retailer-review-cover");
    expect(covers).toHaveLength(2);
    for (const cover of covers) {
      expect(cover.className).toMatch(/\bw-20\b/);
      expect(cover.className).toMatch(/\bshrink-0\b/);
      expect(cover.className).toMatch(/h-\[120px\]/);
    }
    const coverImg = screen.getByAltText("Immortal Thor #1 Cover A") as HTMLImageElement;
    expect(coverImg.className).toContain("object-cover");

    fireEvent.click(screen.getByRole("button", { name: "Confirm Retailer Order" }));

    await waitFor(() => {
      expect(apiClient.confirmRetailerOrder).toHaveBeenCalledWith(11);
      expect(screen.getByText("confirmed")).toBeInTheDocument();
      expect(screen.getByText("Retailer order confirmed.")).toBeInTheDocument();
    });
  });

  it("on confirm timeout, polls the order once and shows success if already confirmed", async () => {
    vi.spyOn(apiClient, "confirmRetailerOrder").mockRejectedValue(
      new ApiError("Confirmation may still be processing. Refresh or check your Portfolio.", 408),
    );
    const getSpy = vi.spyOn(apiClient, "getRetailerOrder");
    getSpy.mockResolvedValueOnce({
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
      capture_quality_summary_json: {},
      parser_quality_summary_json: {},
      raw_fields_summary_json: {},
      updated_at: "2026-06-09T10:01:00Z",
      items: [],
    });
    // The poll-after-timeout fetch returns a fully confirmed order with inventory.
    getSpy.mockResolvedValueOnce({
      id: 11,
      retailer_account_id: 1,
      retailer: "midtown",
      retailer_order_number: "4272232",
      order_date: "2026-06-08",
      order_status: "Shipped",
      order_total: "104.79",
      source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
      review_status: "confirmed",
      linked_order_id: 555,
      inventory_copies_created: 41,
      total_ordered_quantity: 41,
      portfolio_items_added: 41,
      item_count: 2,
      cover_image_count: 1,
      product_url_count: 1,
      price_count: 2,
      release_date_count: 1,
      capture_quality_summary_json: {},
      parser_quality_summary_json: {},
      raw_fields_summary_json: {},
      updated_at: "2026-06-09T10:02:00Z",
      items: [],
    });

    render(
      <MemoryRouter>
        <RetailerOrderDetailPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Confirm Retailer Order" }));

    await waitFor(() => {
      expect(screen.getByText("Confirmed. Created 41 inventory copies in your portfolio.")).toBeInTheDocument();
    });
    // Polled exactly once after the timeout (plus the initial load fetch).
    expect(getSpy).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByText("Confirmation may still be processing. Refresh or check your Portfolio."),
    ).not.toBeInTheDocument();
  });

  it("re-runs catalog enrichment and renders per-line match diagnostics", async () => {
    vi.spyOn(apiClient, "getRetailerOrder").mockResolvedValue({
      id: 11,
      retailer_account_id: 1,
      retailer: "midtown",
      retailer_order_number: "4272232",
      order_date: "2026-06-08",
      order_status: "Shipped",
      order_total: "104.79",
      source_url: "https://www.midtowncomics.com/account/orders/view/4272232",
      review_status: "confirmed",
      linked_order_id: 555,
      item_count: 2,
      cover_image_count: 1,
      product_url_count: 1,
      price_count: 2,
      release_date_count: 1,
      capture_quality_summary_json: {},
      parser_quality_summary_json: {},
      raw_fields_summary_json: {},
      updated_at: "2026-06-09T10:01:00Z",
      items: [],
    });
    const reenrichSpy = vi.spyOn(apiClient, "reenrichRetailerOrder").mockResolvedValue({
      order_id: 11,
      linked_order_id: 555,
      enrichment_summary: { matched_items: 1, needs_review_items: 1 },
      lines: [
        {
          line_index: 1,
          raw_title: "Absolute Green Arrow #1 Cover A",
          series_search_title: "Absolute Green Arrow",
          normalized_title: "absolute green arrow",
          parsed_issue_number: "1",
          parsed_cover_name: "Cover A",
          candidate_count: 3,
          matched: true,
          catalog_match_id: 42,
          match_score: 93,
          chosen_source: "ReleaseIssue",
          rejection_reason: null,
          release_date: "2026-05-06",
          foc_date: "2026-04-13",
          cover_image_url: null,
          enrichment_status: "matched",
          top_candidates: [],
        },
        {
          line_index: 2,
          raw_title: "Totally Obscure Mini ZZZ #1",
          series_search_title: "Totally Obscure Mini ZZZ",
          normalized_title: "totally obscure mini zzz",
          parsed_issue_number: "1",
          parsed_cover_name: null,
          candidate_count: 0,
          matched: false,
          catalog_match_id: null,
          match_score: null,
          chosen_source: null,
          rejection_reason: "no_candidates",
          release_date: null,
          foc_date: null,
          cover_image_url: null,
          enrichment_status: "needs_review",
          top_candidates: [],
        },
      ],
    });

    render(
      <MemoryRouter>
        <RetailerOrderDetailPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Re-run catalog enrichment" }));

    await waitFor(() => {
      expect(reenrichSpy).toHaveBeenCalledWith(11);
      expect(screen.getByText("Catalog enrichment diagnostics")).toBeInTheDocument();
    });
    expect(screen.getByText("Matched")).toBeInTheDocument();
    expect(screen.getByText("Catalog missing")).toBeInTheDocument();
    expect(screen.getByText("Absolute Green Arrow")).toBeInTheDocument();
  });
});
