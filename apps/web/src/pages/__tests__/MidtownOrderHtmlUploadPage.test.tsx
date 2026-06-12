import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, ApiError } from "../../api/client";
import { MidtownOrderHtmlUploadPage } from "../MidtownOrderHtmlUploadPage";

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
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div role="alert">{children}</div>,
}));

describe("MidtownOrderHtmlUploadPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "importMidtownOrderHtml").mockResolvedValue({
      order_id: 42,
      retailer_order_number: "4272232",
      item_count: 3,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("uploads a saved html file and navigates to the retailer order review page", async () => {
    render(
      <MemoryRouter>
        <MidtownOrderHtmlUploadPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Upload saved Midtown order" })).toBeInTheDocument();
    expect(screen.getByText(/Press Ctrl\+S and save as Webpage HTML/i)).toBeInTheDocument();

    const file = new File(["<html><h1>Order #4272232</h1></html>"], "order.html", {
      type: "text/html",
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    fireEvent.click(screen.getByRole("button", { name: "Upload & review order" }));

    await waitFor(() => {
      expect(apiClient.importMidtownOrderHtml).toHaveBeenCalled();
      expect(navigateMock).toHaveBeenCalledWith("/retailer-orders/42");
    });
  });

  it("shows import diagnostics when the upload fails with structured errors", async () => {
    vi.spyOn(apiClient, "importMidtownOrderHtml").mockRejectedValue(
      new ApiError("No order items were found in this file.", 422, {
        message: "No order items were found in this file.",
        diagnostics: {
          title: "Order #4257558",
          page_length: 1200,
          order_item_count: 0,
          order_number_link_count: 1,
          visible_text_excerpt: "Order #4257558\nStatus: Shipped",
          has_right_contents: true,
          has_info_container: true,
          parsed: {
            retailer_order_number: "4257558",
            items_parsed: 0,
            order_status: "Shipped",
          },
        },
      }),
    );

    render(
      <MemoryRouter>
        <MidtownOrderHtmlUploadPage />
      </MemoryRouter>,
    );

    const file = new File(["<html></html>"], "order.html", { type: "text/html" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload & review order" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("No order items were found");
      expect(screen.getByLabelText("Import diagnostics")).toBeInTheDocument();
      expect(screen.getByText("Items parsed")).toBeInTheDocument();
      expect(screen.getByText("4257558")).toBeInTheDocument();
    });
  });
});
