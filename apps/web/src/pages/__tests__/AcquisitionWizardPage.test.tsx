import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { AcquisitionWizardPage } from "../AcquisitionWizardPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

function makeAcquisition() {
  return {
    id: 7,
    user_id: 1,
    acquisition_type: "FACEBOOK" as const,
    purchase_date: "2026-06-01",
    seller_name: null,
    seller_username: null,
    total_paid: "120.00",
    shipping_paid: "0.00",
    tax_paid: "0.00",
    total_cost: "120.00",
    notes: null,
    expected_book_count: 40,
    actual_book_count: 0,
    item_count: 0,
    cost_per_book: "0.00",
    status: "OPEN" as const,
    allocation_mode: "EVEN" as const,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    inventory_summary: {
      allocated_total: "0.00",
      acquisition_total: "120.00",
      unallocated: "120.00",
      fully_allocated: false,
      needs_review_count: 0,
    },
  };
}

describe("AcquisitionWizardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    navigateMock.mockReset();
  });

  it("creates a Facebook acquisition through the 3-step wizard", async () => {
    const createSpy = vi.spyOn(apiClient, "createAcquisition").mockResolvedValue(makeAcquisition());
    render(
      <MemoryRouter>
        <AcquisitionWizardPage />
      </MemoryRouter>,
    );

    // Step 1: source tap buttons
    expect(screen.getByText("Where did you get these books?")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Facebook Marketplace"));

    // Step 2: details
    expect(screen.getByText("Acquisition details")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("120.00"), { target: { value: "120.00" } });
    fireEvent.click(screen.getByRole("button", { name: /Create Acquisition/i }));

    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(1));
    expect(createSpy.mock.calls[0][0]).toMatchObject({ acquisition_type: "FACEBOOK", total_paid: "120.00" });
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/acquisitions/7"));
  });
});
