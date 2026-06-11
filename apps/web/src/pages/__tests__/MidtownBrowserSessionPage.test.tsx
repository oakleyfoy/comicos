import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  });

  it("renders the live Midtown panel and forwards click and typing", async () => {
    vi.spyOn(apiClient, "getMidtownBrowserSessionStatus").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: "Ready",
        current_url: "https://www.midtowncomics.com/account/orders",
        orders_url: "https://www.midtowncomics.com/account/orders",
        authenticated: true,
        order_count: 5,
        last_updated_at: "2026-06-10T20:00:00Z",
        live_session_active: true,
      },
    });
    vi.spyOn(apiClient, "getMidtownBrowserLiveFrame").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: "Ready",
        current_url: "https://www.midtowncomics.com/account/orders",
        orders_url: "https://www.midtowncomics.com/account/orders",
        authenticated: true,
        order_count: 5,
        last_updated_at: "2026-06-10T20:00:00Z",
        live_session_active: true,
      },
      image_data_url: "data:image/jpeg;base64,abc123",
      image_width: 1440,
      image_height: 1100,
      captured_at: "2026-06-10T20:00:00Z",
    });
    const clickSpy = vi.spyOn(apiClient, "clickMidtownBrowserSession").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: "Ready",
        current_url: "https://www.midtowncomics.com/account/orders",
        orders_url: "https://www.midtowncomics.com/account/orders",
        authenticated: true,
        order_count: 5,
        last_updated_at: "2026-06-10T20:00:00Z",
        live_session_active: true,
      },
    });
    const typeSpy = vi.spyOn(apiClient, "typeMidtownBrowserSession").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: "Ready",
        current_url: "https://www.midtowncomics.com/account/orders",
        orders_url: "https://www.midtowncomics.com/account/orders",
        authenticated: true,
        order_count: 5,
        last_updated_at: "2026-06-10T20:00:00Z",
        live_session_active: true,
      },
    });

    const { container, findByRole } = render(
      <MemoryRouter>
        <MidtownBrowserSessionPage />
      </MemoryRouter>,
    );
    const scoped = within(container);

    expect(await findByRole("heading", { name: "Midtown Comics" })).toBeInTheDocument();
    expect(await scoped.findByAltText("Midtown browser workspace")).toHaveAttribute(
      "src",
      "data:image/jpeg;base64,abc123",
    );

    fireEvent.click(scoped.getByAltText("Midtown browser workspace"));
    fireEvent.keyDown(scoped.getByRole("application"), { key: "A" });

    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(typeSpy).toHaveBeenCalledWith({ text: "A" });
    });
  });

  it("shows the security verification handoff and retries into orders", async () => {
    vi.spyOn(apiClient, "getMidtownBrowserSessionStatus").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "security_verification_required",
        message: "Midtown requires security verification.",
        current_url: "https://www.midtowncomics.com/verify",
        orders_url: "https://www.midtowncomics.com/account/orders",
        authenticated: false,
        order_count: 0,
        last_updated_at: "2026-06-10T20:00:00Z",
        live_session_active: true,
      },
    });
    vi.spyOn(apiClient, "getMidtownBrowserLiveFrame").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "security_verification_required",
        message: "Midtown requires security verification.",
        current_url: "https://www.midtowncomics.com/verify",
        orders_url: "https://www.midtowncomics.com/account/orders",
        authenticated: false,
        order_count: 0,
        last_updated_at: "2026-06-10T20:00:00Z",
        live_session_active: true,
      },
      image_data_url: "data:image/jpeg;base64,verify123",
      image_width: 1440,
      image_height: 1100,
      captured_at: "2026-06-10T20:00:00Z",
    });
    vi.spyOn(apiClient, "retryMidtownBrowserSession").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: "Ready",
        current_url: "https://www.midtowncomics.com/account/orders",
        orders_url: "https://www.midtowncomics.com/account/orders",
        authenticated: true,
        order_count: 8,
        last_updated_at: "2026-06-10T20:05:00Z",
        live_session_active: true,
      },
    });

    const { container, findByRole } = render(
      <MemoryRouter>
        <MidtownBrowserSessionPage />
      </MemoryRouter>,
    );
    const scoped = within(container);

    expect(await findByRole("heading", { name: "Security Verification Required" })).toBeInTheDocument();
    expect(scoped.getByText("Midtown requires security verification before ComicOS can load your orders.")).toBeInTheDocument();
    expect(await scoped.findByAltText("Midtown browser workspace")).toHaveAttribute(
      "src",
      "data:image/jpeg;base64,verify123",
    );

    fireEvent.click(scoped.getByRole("button", { name: "I Completed Verification - Retry" }));

    await waitFor(() => {
      expect(apiClient.retryMidtownBrowserSession).toHaveBeenCalledTimes(1);
      expect(navigateMock).toHaveBeenCalledWith("/connected-retailers/midtown/orders");
    });
  });
});
