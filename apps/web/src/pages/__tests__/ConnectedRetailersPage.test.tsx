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

describe("ConnectedRetailersPage", () => {
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

  it("renders the clean Midtown browser card", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Connected Retailers" })).toBeInTheDocument();
    expect(screen.getAllByText("Midtown Comics").length).toBeGreaterThan(0);
    expect(screen.getByText(/Status: Connected/i)).toBeInTheDocument();
    expect(screen.getByText(/Last successful session:/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load My Midtown Orders" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save credentials" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import saved order file" })).toBeInTheDocument();
  });

  it("shows connect form when no retailer account exists", async () => {
    vi.spyOn(apiClient, "getRetailerAccounts").mockResolvedValue({ items: [] });

    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Connect Midtown" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Connect Midtown Comics" })).toBeInTheDocument();
  });

  it("keeps the legacy tools collapsed by default", async () => {
    render(
      <MemoryRouter>
        <ConnectedRetailersPage />
      </MemoryRouter>,
    );

    const legacyTools = screen.getAllByText("Advanced legacy extension tools")[0].closest("details");
    expect(legacyTools).toBeInstanceOf(HTMLDetailsElement);
    expect((legacyTools as HTMLDetailsElement).open).toBe(false);

    fireEvent.click(screen.getAllByText("Advanced legacy extension tools")[0]);
    expect((legacyTools as HTMLDetailsElement).open).toBe(true);
    expect(screen.getAllByRole("button", { name: "Capture Midtown order" }).length).toBeGreaterThan(0);
  });
});
