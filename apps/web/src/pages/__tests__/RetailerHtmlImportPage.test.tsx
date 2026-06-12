import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { RetailerHtmlImportPage } from "../RetailerHtmlImportPage";

let navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
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
  StatusBanner: ({ children }: { children: ReactNode }) => <div role="alert">{children}</div>,
}));

describe("RetailerHtmlImportPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "listImportRetailers").mockResolvedValue({
      items: [
        { key: "midtown", display_name: "Midtown Comics", status: "supported", supported: true, accepts_upload: true, is_fallback: false },
        { key: "dcbs", display_name: "DCBS / Discount Comic Book Service", status: "beta", supported: false, accepts_upload: true, is_fallback: false },
        { key: "third_eye", display_name: "Third Eye Comics", status: "beta", supported: false, accepts_upload: true, is_fallback: false },
        { key: "mycomicshop", display_name: "MyComicShop", status: "beta", supported: false, accepts_upload: true, is_fallback: false },
        { key: "unknown", display_name: "Unknown / Other Retailer", status: "generic", supported: false, accepts_upload: true, is_fallback: true },
      ],
    });
    vi.spyOn(apiClient, "importRetailerOrderHtml").mockResolvedValue({
      order_id: 77,
      retailer: "unknown",
      retailer_order_number: "ABC-1001",
      item_count: 2,
      parser_status: "generic",
      warnings: [],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders retailer cards with statuses and the fallback copy", async () => {
    render(
      <MemoryRouter>
        <RetailerHtmlImportPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Midtown Comics")).toBeInTheDocument();
    expect(screen.getByText("Supported")).toBeInTheDocument();
    expect(screen.getAllByText("Coming next · Upload sample").length).toBeGreaterThanOrEqual(3);
    expect(
      screen.getByText(/Don't see your retailer\? Upload a saved order page and ComicOS can add support\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Save your retailer order page as HTML, upload it here/i),
    ).toBeInTheDocument();
  });

  it("uploads a saved html file for the selected retailer and opens the review page", async () => {
    render(
      <MemoryRouter>
        <RetailerHtmlImportPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByText("Unknown / Other Retailer"));

    const file = new File(["<html><h1>Order #ABC-1001</h1></html>"], "order.html", { type: "text/html" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload & review order" }));

    await waitFor(() => {
      expect(apiClient.importRetailerOrderHtml).toHaveBeenCalledWith("unknown", file);
      expect(navigateMock).toHaveBeenCalledWith("/retailer-orders/77");
    });
  });
});
