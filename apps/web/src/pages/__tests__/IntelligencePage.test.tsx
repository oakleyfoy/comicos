import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { IntelligencePage } from "../IntelligencePage";

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

describe("IntelligencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getIntelligenceDashboard").mockResolvedValue({
      character_count: 110,
      franchise_count: 55,
      creator_count: 105,
      top_characters: [{ entity_id: 1, entity_name: "Batman", entity_type: "CHARACTER", popularity_score: 98, demand_score: 96, collector_score: 97 }],
      top_franchises: [{ entity_id: 1, entity_name: "Batman", entity_type: "FRANCHISE", popularity_score: 98, demand_score: 96, collector_score: 97 }],
      top_creators: [{ entity_id: 1, entity_name: "Scott Snyder", entity_type: "CREATOR", popularity_score: 87, demand_score: 85, collector_score: 86 }],
      upcoming_releases_by_popularity: [
        {
          release_issue_id: 10,
          title: "Batman #1",
          series_name: "Batman",
          publisher: "DC",
          release_date: "2026-06-03",
          combined_popularity_score: 92.5,
          matched_entity_count: 2,
        },
      ],
      popularity_distribution: [{ bucket_label: "90-100", entity_count: 12 }],
    });
  });

  it("renders intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <IntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Character, Franchise & Creator Intelligence" })).toBeInTheDocument();
    });

    expect(screen.getByText("Top Characters")).toBeInTheDocument();
    expect(screen.getByText("Upcoming Popular Releases")).toBeInTheDocument();
    expect(screen.getByText("Scott Snyder")).toBeInTheDocument();
    expect(screen.getByText(/Batman · Batman #1/)).toBeInTheDocument();
  });
});
