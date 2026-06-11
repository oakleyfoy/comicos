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
    vi.spyOn(window, "open").mockImplementation(
      () =>
        ({
          name: "",
          location: { href: "about:blank" },
          document: { write: vi.fn() },
          close: vi.fn(),
        }) as unknown as Window,
    );
  });

  it("continues to Midtown when the account is connected", async () => {
    vi.spyOn(apiClient, "getMidtownBrowserSessionStatus").mockResolvedValue({
      session: {
        retailer: "midtown",
        account_id: 1,
        status: "ready",
        message: null,
        current_url: null,
        orders_url: "https://www.midtowncomics.com/account-settings",
        authenticated: true,
        order_count: 5,
        last_updated_at: "2026-06-10T20:00:00Z",
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

    const { container, findByRole } = render(
      <MemoryRouter>
        <MidtownBrowserSessionPage />
      </MemoryRouter>,
    );
    const scoped = within(container);

    expect(await findByRole("heading", { name: "Midtown Comics" })).toBeInTheDocument();
    expect(scoped.getByText("Connected")).toBeInTheDocument();
    expect(scoped.getAllByRole("button", { name: "Continue to Midtown" }).length).toBeGreaterThan(0);
    expect(scoped.getByRole("button", { name: "View Orders" })).toBeInTheDocument();
    expect(scoped.getByTitle("Midtown browser workspace")).toBeInTheDocument();

    fireEvent.click(scoped.getAllByRole("button", { name: "Continue to Midtown" })[0]);

    await waitFor(() => {
      expect(apiClient.startMidtownBrowserSession).toHaveBeenCalledTimes(1);
      expect(scoped.getByTitle("Midtown browser workspace")).toBeInTheDocument();
    });
  });

  it("shows a security verification handoff when Midtown blocks access", async () => {
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
      },
    });
    vi.spyOn(apiClient, "startMidtownBrowserSession").mockResolvedValue({
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
    expect(scoped.getByTitle("Midtown browser workspace")).toHaveAttribute("src", "https://www.midtowncomics.com/verify");
    expect(scoped.getAllByRole("button", { name: "Continue to Midtown Verification" }).length).toBeGreaterThan(0);
    expect(scoped.getAllByRole("button", { name: "I Completed Verification - Retry" }).length).toBeGreaterThan(0);

    fireEvent.click(scoped.getAllByRole("button", { name: "I Completed Verification - Retry" })[0]);

    await waitFor(() => {
      expect(apiClient.startMidtownBrowserSession).toHaveBeenCalledTimes(1);
      expect(navigateMock).toHaveBeenCalledWith("/connected-retailers/midtown/orders");
    });
  });
});
