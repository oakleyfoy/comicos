import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PullListPage } from "../PullListPage";
import { apiClient } from "../../api/client";

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

describe("PullListPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders empty state when no pull lists exist", async () => {
    vi.spyOn(apiClient, "getPullLists").mockResolvedValue({
      items: [],
      total_items: 0,
      limit: 50,
      offset: 0,
    });
    render(
      <MemoryRouter>
        <PullListPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/no pull lists yet/i)).toBeInTheDocument();
    });
  });

  it("renders pull list rows", async () => {
    vi.spyOn(apiClient, "getPullLists").mockResolvedValue({
      items: [
        {
          id: 1,
          owner_id: 1,
          publisher: "DC",
          series_name: "Batman",
          canonical_series_id: null,
          status: "ACTIVE",
          upcoming_issue_count: 2,
          created_at: "2026-06-01T00:00:00Z",
          updated_at: "2026-06-01T00:00:00Z",
        },
      ],
      total_items: 1,
      limit: 50,
      offset: 0,
    });
    render(
      <MemoryRouter>
        <PullListPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Batman")).toBeInTheDocument();
      expect(screen.getByText("DC")).toBeInTheDocument();
    });
  });
});
