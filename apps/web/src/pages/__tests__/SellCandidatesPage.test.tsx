import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { SellCandidatePage } from "../SellCandidatePage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const sampleItem: clientModule.P89SellCandidateRead = {
  id: 1,
  owner_user_id: 1,
  inventory_copy_id: 10,
  recommendation: "SELL_NOW",
  sell_score: 88,
  hold_score: 20,
  grade_first_score: 15,
  monitor_score: 25,
  confidence: "HIGH",
  estimated_sale_value: 450,
  estimated_profit: 260,
  reason_summary: "Strong market signals",
  reasons: ["Strong market demand", "FMV exceeds cost basis"],
  status: "ACTIVE",
  title: "Amazing Spider-Man",
  issue_number: "300",
  publisher: "Marvel",
  cover_image_url: "",
  is_top_opportunity: true,
  created_at: "2026-06-08T00:00:00Z",
  updated_at: "2026-06-08T00:00:00Z",
};

describe("SellCandidatesPage", () => {
  it("renders cards and top sell opportunity", async () => {
    vi.spyOn(clientModule.apiClient, "getSellCandidates").mockResolvedValue({
      items: [sampleItem],
      total_items: 1,
      limit: 100,
      offset: 0,
    });

    render(
      <MemoryRouter>
        <SellCandidatePage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Sell Candidates", level: 1 })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Top Sell Opportunity")).toBeInTheDocument();
    });
    expect(await screen.findByText(/Amazing Spider-Man #300/)).toBeInTheDocument();
    expect(screen.getAllByText("Sell Now").length).toBeGreaterThan(0);
  });

  it("renders empty state when no candidates", async () => {
    vi.spyOn(clientModule.apiClient, "getSellCandidates").mockResolvedValue({
      items: [],
      total_items: 0,
      limit: 100,
      offset: 0,
    });

    render(
      <MemoryRouter>
        <SellCandidatePage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("No sell candidates yet.")).toBeInTheDocument();
  });
});
