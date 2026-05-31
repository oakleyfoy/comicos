import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "../AppShell";
import { NAV_EXPANDED_STORAGE_KEY } from "../../config/appNavigation";

const mockLogout = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    isOpsAdmin: true,
    logout: mockLogout,
  }),
}));

function renderShell(initialPath = "/executive-dashboard") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AppShell>
        <div>Page content</div>
      </AppShell>
    </MemoryRouter>,
  );
}

function getMainNav() {
  return screen.getByRole("navigation", { name: "Main navigation" });
}

describe("AppShell navigation", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    localStorage.removeItem(NAV_EXPANDED_STORAGE_KEY);
    mockLogout.mockReset();
  });

  it("shows Executive Dashboard in Primary and header shortcut", () => {
    renderShell();
    expect(screen.getAllByRole("link", { name: "Executive Dashboard" }).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("button", { name: "Primary" })).toBeInTheDocument();
  });

  it("renders Primary group expanded with core links", () => {
    renderShell();
    const nav = getMainNav();
    expect(within(nav).getByRole("button", { name: "Primary" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Daily Actions" })).toBeVisible();
    expect(within(nav).getByRole("link", { name: "Unified Intelligence" })).toBeVisible();
  });

  it("collapses and expands non-primary groups", () => {
    renderShell();
    const nav = getMainNav();
    const collectionToggle = within(nav).getByRole("button", { name: "Collection" });
    expect(within(nav).queryByRole("link", { name: "Want Lists" })).not.toBeInTheDocument();
    fireEvent.click(collectionToggle);
    expect(within(nav).getByRole("link", { name: "Want Lists" })).toBeVisible();
    fireEvent.click(collectionToggle);
    expect(within(nav).queryByRole("link", { name: "Want Lists" })).not.toBeInTheDocument();
  });

  it("auto-expands the group for the active route", () => {
    renderShell("/operations-reliability");
    const nav = getMainNav();
    expect(within(nav).getByRole("link", { name: "Operations Reliability" })).toBeVisible();
    expect(within(nav).getByRole("link", { name: "Production Readiness" })).toBeVisible();
  });

  it("groups operations admin pages under Operations / Admin", () => {
    renderShell("/production-readiness");
    const nav = getMainNav();
    const opsSection = within(nav).getByRole("button", { name: "Operations / Admin" }).closest("section");
    expect(opsSection).not.toBeNull();
    const links = within(opsSection as HTMLElement).getAllByRole("link");
    const labels = links.map((node) => node.textContent);
    expect(labels).toContain("Operations Reliability");
    expect(labels).toContain("Production Readiness");
    expect(labels).toContain("Operations");
  });

  it("does not duplicate nav link labels in the sidebar", () => {
    renderShell();
    const sidebar = getMainNav();
    const labels = within(sidebar)
      .getAllByRole("link")
      .map((node) => node.textContent?.trim())
      .filter(Boolean);
    const executiveCount = labels.filter((label) => label === "Executive Dashboard").length;
    expect(executiveCount).toBe(1);
    expect(new Set(labels).size).toBe(labels.length);
  });
});
