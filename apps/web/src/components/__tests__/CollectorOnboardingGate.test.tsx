import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { CollectorOnboardingGate } from "../CollectorOnboardingGate";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    apiClient: {
      ...actual.apiClient,
      getCollectorOnboardingStatus: vi.fn(),
    },
  };
});

afterEach(() => cleanup());

describe("CollectorOnboardingGate", () => {
  it("redirects incomplete users to onboarding", async () => {
    vi.mocked(apiClient.getCollectorOnboardingStatus).mockResolvedValue({
      onboarding_completed: false,
      onboarding_completed_at: null,
      draft: { step: 1, collector_type: null, risk_profile: null, time_horizon: null, publisher_labels: [], character_labels: [], creator_labels: [] },
    });

    render(
      <MemoryRouter initialEntries={["/collector-home"]}>
        <Routes>
          <Route element={<CollectorOnboardingGate />}>
            <Route path="/collector-home" element={<div>Home</div>} />
            <Route path="/collector-onboarding" element={<div>Onboarding</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Onboarding")).toBeInTheDocument();
    });
  });
});
