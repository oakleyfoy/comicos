import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { OrderImportPage } from "../OrderImportPage";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    isOpsAdmin: true,
  }),
}));

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../components/imports/ImportMetadataQuestionsGate", () => ({
  ImportMetadataQuestionsGate: () => null,
}));

vi.mock("../../components/imports/ImportReviewCard", () => ({
  ImportReviewCard: ({ item }: { item: { title: string } }) => <article>{item.title}</article>,
}));

vi.mock("../importMetadataQuestions", () => ({
  buildPendingImportMetadataQuestions: () => [],
}));

describe("OrderImportPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getImport").mockResolvedValue({
      id: 23,
      status: "draft",
      raw_text: "Retailer account sync import for Midtown Comics order #4272232.",
      confidence_score: 1,
      cover_images: [],
      linked_order_id: null,
      parsed_payload_json: {
        retailer: "Midtown Comics",
        order_date: "2026-06-08",
        source_type: "retailer_account",
        shipping_amount: "0.00",
        tax_amount: "0.00",
        order_total: "104.79",
        total_books: 21,
        warnings: [],
        confidence_score: 1,
        items: [
          {
            publisher: "DC Comics",
            title: "Absolute Batman #1 Cover A",
            issue_number: "1",
            quantity: 1,
            raw_item_price: "4.99",
            release_date: "2026-06-08",
            order_status: "shipped",
            writers: [],
            artists: [],
            cover_artists: [],
          },
        ],
      },
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads a draft import from the importId query string", async () => {
    render(
      <MemoryRouter initialEntries={["/orders/import?importId=23"]}>
        <OrderImportPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Import Order Draft")).toBeInTheDocument();
    await waitFor(() => {
      expect(apiClient.getImport).toHaveBeenCalledWith(23);
    });
    expect(await screen.findByDisplayValue("Retailer account sync import for Midtown Comics order #4272232.")).toBeInTheDocument();
    expect(await screen.findByText("Absolute Batman #1 Cover A")).toBeInTheDocument();
    expect(screen.getByText("Saved import #23 · draft")).toBeInTheDocument();
  });
});
