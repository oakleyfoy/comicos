import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { MidtownBrowserSessionPage } from "../MidtownBrowserSessionPage";

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

describe("MidtownBrowserSessionPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "getMidtownBrowserSessionStatus").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "idle",
        message: null,
        current_url: null,
        orders_url: "https://www.midtowncomics.com/account-settings",
        authenticated: false,
        order_count: 0,
        last_updated_at: null,
      },
    });
    vi.spyOn(apiClient, "startMidtownBrowserSession").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: "Ready",
        current_url: "https://www.midtowncomics.com/account-settings",
        orders_url: "https://www.midtowncomics.com/account-settings",
        authenticated: true,
        order_count: 5,
        last_updated_at: "2026-06-10T20:00:00Z",
      },
    });
  });

  it("starts the Midtown browser session and opens order history", async () => {
    render(
      <MemoryRouter>
        <MidtownBrowserSessionPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Midtown Browser Session" })).toBeInTheDocument();
    const startButton = await screen.findByRole("button", { name: "Start Midtown Session" });
    await waitFor(() => {
      expect(startButton).not.toBeDisabled();
    });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(apiClient.startMidtownBrowserSession).toHaveBeenCalledTimes(1);
      expect(navigateMock).toHaveBeenCalledWith("/connected-retailers/midtown/orders");
    });
  });
});
