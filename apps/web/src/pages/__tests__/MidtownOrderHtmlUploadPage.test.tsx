import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
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
});
