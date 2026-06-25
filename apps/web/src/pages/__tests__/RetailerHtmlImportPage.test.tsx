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

const IMPORT_CATALOG = {
  items: [
    { key: "midtown", display_name: "Midtown Comics", status: "supported", supported: true, accepts_upload: true, is_fallback: false },
    { key: "dcbs", display_name: "DCBS / Discount Comic Book Service", status: "beta", supported: false, accepts_upload: true, is_fallback: false },
    { key: "third_eye", display_name: "Third Eye Comics", status: "beta", supported: false, accepts_upload: true, is_fallback: false },
    { key: "mycomicshop", display_name: "MyComicShop", status: "beta", supported: false, accepts_upload: true, is_fallback: false },
    { key: "unknown", display_name: "Unknown / Other Retailer", status: "generic", supported: false, accepts_upload: true, is_fallback: true },
  ],
};

describe("RetailerHtmlImportPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "listImportRetailers").mockResolvedValue(IMPORT_CATALOG);
    vi.spyOn(apiClient, "getRetailerAccounts").mockResolvedValue({
      items: [
        {
          id: 1,
          retailer: "third_eye",
          display_name: "Third Eye Comics",
          masked_username: "html-import",
          credential_version: 0,
          status: "active",
          sync_enabled: false,
          created_at: "2026-06-01T00:00:00Z",
          updated_at: "2026-06-01T00:00:00Z",
        },
        {
          id: 2,
          retailer: "midtown",
          display_name: "Midtown Comics",
          masked_username: "html-import",
          credential_version: 0,
          status: "active",
          sync_enabled: false,
          created_at: "2026-06-01T00:00:00Z",
          updated_at: "2026-06-01T00:00:00Z",
        },
      ],
    });
    vi.spyOn(apiClient, "importRetailerOrderHtml").mockResolvedValue({
      order_id: 77,
      retailer: "dcbs",
      retailer_order_number: "970668",
      item_count: 2,
      parser_status: "beta",
      warnings: [],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("lists all HTML import retailers including DCBS", async () => {
    render(
      <MemoryRouter>
        <RetailerHtmlImportPage />
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText("Choose a Retailer")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "DCBS / Discount Comic Book Service" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Midtown Comics" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Third Eye Comics" })).toBeInTheDocument();
  });

  it("uploads a saved html file for the selected retailer and opens the review page", async () => {
    render(
      <MemoryRouter>
        <RetailerHtmlImportPage />
      </MemoryRouter>,
    );

    const select = await screen.findByLabelText("Choose a Retailer");
    fireEvent.change(select, { target: { value: "dcbs" } });

    const file = new File(["<html><h1>Order #970668</h1></html>"], "order.html", { type: "text/html" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload & review order" }));

    await waitFor(() => {
      expect(apiClient.importRetailerOrderHtml).toHaveBeenCalledWith("dcbs", file);
      expect(navigateMock).toHaveBeenCalledWith("/retailer-orders/77");
    });
  });
});
