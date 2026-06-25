import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ConnectedRetailersPage } from "../ConnectedRetailersPage";

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

describe("ConnectedRetailersPage Midtown browser entry", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock = vi.fn();
    vi.spyOn(apiClient, "getRetailerAccounts").mockResolvedValue({
      items: [
        {
          id: 1,
          retailer: "midtown",
          display_name: "Midtown Comics",
          masked_username: "co********@example.com",
          credential_version: 1,
          status: "connected",
          sync_enabled: true,
          last_sync_at: "2026-06-09T10:00:00Z",
          last_success_at: "2026-06-09T10:01:00Z",
          last_error: null,
          created_at: "2026-06-09T09:00:00Z",
          updated_at: "2026-06-09T10:01:00Z",
        },
      ],
    });
    vi.spyOn(apiClient, "getRetailerOrders").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "getRetailerAccountSyncRuns").mockResolvedValue({ items: [] });
  });

  it("routes into the Midtown order flow with the live browser as fallback", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Connected Retailers" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Load My Midtown Orders" }));
    expect(navigateMock).toHaveBeenCalledWith("/connected-retailers/midtown/orders");
    fireEvent.click(screen.getByRole("button", { name: "Live browser (security check)" }));
    expect(navigateMock).toHaveBeenCalledWith("/connected-retailers/midtown");
  });
});
