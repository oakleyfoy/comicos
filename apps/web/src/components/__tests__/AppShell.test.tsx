import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "../AppShell";
import { NAV_EXPANDED_STORAGE_KEY, NAV_SIDEBAR_SCROLL_KEY } from "../../config/appNavigation";

const mockLogout = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    isOpsAdmin: true,
    logout: mockLogout,
  }),
}));

function renderShell(initialPath = "/collector-home") {
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
    sessionStorage.removeItem(NAV_SIDEBAR_SCROLL_KEY);
  });

  beforeEach(() => {
    localStorage.removeItem(NAV_EXPANDED_STORAGE_KEY);
    sessionStorage.removeItem(NAV_SIDEBAR_SCROLL_KEY);
    mockLogout.mockReset();
  });

  it("shows Collector Home in nav and header shortcut", () => {
    renderShell();
    expect(screen.getAllByRole("link", { name: "Collector Home" }).length).toBeGreaterThanOrEqual(2);
    expect(within(getMainNav()).getByRole("button", { name: "Home" })).toBeInTheDocument();
  });

  it("renders workflow groups with core home links visible on collector home", () => {
    renderShell("/collector-home");
    const nav = getMainNav();
    expect(within(nav).getByRole("link", { name: "Today's Actions" })).toBeVisible();
    expect(within(nav).getByRole("link", { name: "Command Center" })).toBeVisible();
  });

  it("does not show a Discovery sidebar group; discovery routes live under Reports", () => {
    renderShell();
    const nav = getMainNav();
    expect(within(nav).queryByRole("button", { name: "Discovery" })).not.toBeInTheDocument();
    fireEvent.click(within(nav).getByRole("button", { name: "Reports" }));
    expect(within(nav).getByRole("link", { name: "Discovery Dashboard" })).toBeVisible();
    expect(within(nav).getByRole("link", { name: "Release Lifecycle" })).toBeVisible();
  });

  it("does not show phase pages removed from the sidebar", () => {
    renderShell();
    const nav = getMainNav();
    for (const group of ["Grade", "Storage", "Buy", "Inventory"]) {
      fireEvent.click(within(nav).getByRole("button", { name: group }));
    }
    expect(within(nav).queryByRole("link", { name: "Opportunities" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Grading Platform" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Release Intelligence" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Box Contents" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Assignment" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Purchase Budget" })).not.toBeInTheDocument();
  });

  it("auto-expands the group for the active route", () => {
    renderShell("/production-readiness");
    const nav = getMainNav();
    expect(within(nav).getByRole("link", { name: "Production Readiness" })).toBeVisible();
    expect(within(nav).getByRole("link", { name: "Portfolio Analytics" })).toBeVisible();
  });

  it("keeps Collector Budget under Settings", () => {
    renderShell("/collector-budget");
    const nav = getMainNav();
    expect(within(nav).getByRole("link", { name: "Collector Budget" })).toBeVisible();
  });

  it("restores sidebar scroll position after navigation", () => {
    sessionStorage.setItem(NAV_SIDEBAR_SCROLL_KEY, "240");
    const { unmount } = renderShell("/collector-home");
    const nav = getMainNav();
    expect(nav.scrollTop).toBe(240);
    unmount();
    renderShell("/sell-queue");
    expect(getMainNav().scrollTop).toBe(240);
  });

  it("does not duplicate nav link labels in the sidebar", () => {
    renderShell();
    const sidebar = getMainNav();
    const labels = within(sidebar)
      .getAllByRole("link")
      .map((node) => node.textContent?.trim())
      .filter(Boolean);
    const homeCount = labels.filter((label) => label === "Collector Home").length;
    expect(homeCount).toBe(1);
    expect(new Set(labels).size).toBe(labels.length);
  });
});
