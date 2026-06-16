import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiClient,
  type AcquisitionItemRead,
  type AcquisitionRead,
  type IssueGridResponse,
  type PublisherListResponse,
  type SeriesListResponse,
  type VariantPickerResult,
} from "../../api/client";
import { AcquisitionDetailPage } from "../AcquisitionDetailPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

function makeAcquisition(overrides: Partial<AcquisitionRead> = {}): AcquisitionRead {
  return {
    id: 5,
    user_id: 1,
    acquisition_type: "FACEBOOK",
    purchase_date: "2026-06-01",
    seller_name: "Jane Seller",
    seller_username: null,
    total_paid: "120.00",
    shipping_paid: "0.00",
    tax_paid: "0.00",
    total_cost: "120.00",
    notes: null,
    expected_book_count: 40,
    actual_book_count: 1,
    item_count: 1,
    cost_per_book: "120.00",
    status: "OPEN",
    allocation_mode: "EVEN",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    inventory_summary: {
      allocated_total: "0.00",
      acquisition_total: "120.00",
      unallocated: "120.00",
      fully_allocated: false,
      needs_review_count: 0,
    },
    ...overrides,
  };
}

function makeItem(overrides: Partial<AcquisitionItemRead> = {}): AcquisitionItemRead {
  return {
    inventory_copy_id: 100,
    acquisition_id: 5,
    catalog_issue_id: 11,
    series: "Saga",
    issue_number: "1",
    publisher: "Image",
    cover_image_url: null,
    variant_label: null,
    variant_status: "RESOLVED",
    cost_basis: "60.00",
    copy_number: 1,
    ...overrides,
  };
}

const publishers: PublisherListResponse = {
  publishers: [{ id: 9, name: "Image Comics", series_count: 12, owned: true, recently_used: false }],
};

const seriesResp: SeriesListResponse = {
  popular: [
    {
      id: 21,
      name: "Saga",
      start_year: 2012,
      issue_count: 60,
      publisher_id: 9,
      publisher_name: "Image Comics",
      sample_cover_url: null,
      owned: false,
      recently_used: false,
    },
  ],
  recently_used: [],
  user_owned: [],
  alphabetical: [],
};

const grid: IssueGridResponse = {
  series_id: 21,
  series_name: "Saga",
  publisher_name: "Image Comics",
  tiles: [
    {
      issue_number: "1",
      normalized_issue_number: "1",
      catalog_issue_id: 11,
      cover_image_url: "http://covers/1.jpg",
      cover_count: 1,
      has_variants: false,
      owned: false,
      added: false,
    },
    {
      issue_number: "2",
      normalized_issue_number: "2",
      catalog_issue_id: null,
      cover_image_url: "http://covers/2.jpg",
      cover_count: 2,
      has_variants: true,
      owned: false,
      added: false,
    },
  ],
};

const variantPicker: VariantPickerResult = {
  series_id: 21,
  issue_number: "2",
  options: [
    {
      catalog_issue_id: 31,
      series: "Saga",
      issue_number: "2",
      title: null,
      variant_label: "Cover A",
      cover_date: null,
      publisher: "Image Comics",
      cover_image_url: "http://covers/2a.jpg",
      variant_type: "COVER_A",
      sort_rank: 0,
      owned: false,
      added: false,
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/acquisitions/5"]}>
      <Routes>
        <Route path="/acquisitions/:acquisitionId" element={<AcquisitionDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AcquisitionDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getAcquisition").mockResolvedValue(makeAcquisition());
    vi.spyOn(apiClient, "listAcquisitionItems").mockResolvedValue({ items: [makeItem()], total: 1 });
    vi.spyOn(apiClient, "listCatalogPublishers").mockResolvedValue(publishers);
    vi.spyOn(apiClient, "listCatalogSeries").mockResolvedValue(seriesResp);
    vi.spyOn(apiClient, "listCatalogIssueGrid").mockResolvedValue(grid);
    vi.spyOn(apiClient, "listCatalogIssueVariants").mockResolvedValue(variantPicker);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders header, cost allocation, and links each book to inventory detail", async () => {
    renderPage();

    expect(await screen.findByText("Jane Seller")).toBeInTheDocument();
    expect(screen.getByText("Facebook Marketplace")).toBeInTheDocument();
    expect(screen.getByText("Total paid")).toBeInTheDocument();

    // Cost allocation panel shows the acquisition total.
    const allocation = screen.getByLabelText("Cost allocation");
    expect(within(allocation).getByText("Cost Allocation")).toBeInTheDocument();
    expect(within(allocation).getByText("Acquisition total")).toBeInTheDocument();

    // Child book links back to its inventory detail page.
    const bookLink = screen.getByRole("link", { name: /Saga #1/i });
    expect(bookLink).toHaveAttribute("href", "/inventory/100");
  });

  it("allocates costs evenly", async () => {
    const allocateSpy = vi.spyOn(apiClient, "allocateAcquisition").mockResolvedValue({
      mode: "EVEN",
      allocated_total: "120.00",
      acquisition_total: "120.00",
      fully_allocated: true,
      items: [],
      acquisition: makeAcquisition(),
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Allocate Evenly" }));
    await waitFor(() => expect(allocateSpy).toHaveBeenCalledWith(5, "EVEN"));
  });

  it("adds a single-cover issue and opens the variant picker for multi-cover issues", async () => {
    const addSpy = vi.spyOn(apiClient, "addAcquisitionItems").mockResolvedValue({
      created_count: 1,
      results: [{ catalog_issue_id: 11, created_count: 1, already_added: false, inventory_copy_ids: [200] }],
      duplicate_catalog_issue_ids: [],
      acquisition: makeAcquisition(),
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Add Books" }));
    fireEvent.click(await screen.findByRole("button", { name: /Browse Publisher/ }));

    fireEvent.click(await screen.findByRole("button", { name: /Image Comics/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Saga/i }));

    // Single-cover tile renders a thumbnail.
    const tile1 = await screen.findByRole("button", { name: "Issue 1" });
    expect(within(tile1).getByAltText("Issue 1 cover")).toBeInTheDocument();
    fireEvent.click(tile1);

    fireEvent.click(await screen.findByRole("button", { name: /Add Selected/i }));
    await waitFor(() =>
      expect(addSpy).toHaveBeenCalledWith(5, [{ catalog_issue_id: 11, quantity: 1 }], false),
    );

    // Multi-cover tile opens the variant picker.
    fireEvent.click(await screen.findByRole("button", { name: "Issue 2" }));
    expect(await screen.findByText("Choose a cover for #2")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Use Cover A" })).toBeInTheDocument();
  });

  it("adds a bulk range of issues", async () => {
    const bulkSpy = vi.spyOn(apiClient, "addAcquisitionBulkRange").mockResolvedValue({
      added_count: 5,
      needs_variant: [],
      acquisition: makeAcquisition(),
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Add Books" }));
    fireEvent.click(await screen.findByRole("button", { name: /Browse Publisher/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Image Comics/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Saga/i }));

    fireEvent.click(await screen.findByRole("button", { name: "Bulk Range" }));
    fireEvent.change(screen.getByLabelText("Start issue"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("End issue"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Add Range" }));

    await waitFor(() =>
      expect(bulkSpy).toHaveBeenCalledWith(5, {
        series_id: 21,
        start_issue: 1,
        end_issue: 5,
        variant_resolution: "review",
      }),
    );
  });
});
