import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, type CollectionGapYearsResponse } from "../../api/client";
import { CollectionGapPage } from "../CollectionGapPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: () => null,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const yearsResp: CollectionGapYearsResponse = {
  default_year: 2025,
  items: [
    {
      year: 2025,
      total_issues: 10,
      owned_issues: 4,
      missing_issues: 6,
      completion_percent: 40,
    },
    {
      year: 2024,
      total_issues: 5,
      owned_issues: 2,
      missing_issues: 3,
      completion_percent: 40,
    },
  ],
};

describe("CollectionGapPage", () => {
  const renderPage = () =>
    render(
      <MemoryRouter>
        <CollectionGapPage />
      </MemoryRouter>,
    );

  beforeEach(() => {
    vi.spyOn(apiClient, "getCollectionGapYears").mockResolvedValue(yearsResp);
    vi.spyOn(apiClient, "getCollectionGapPublishers").mockResolvedValue({
      year: 2025,
      items: [
        {
          publisher: "Marvel",
          total_issues: 8,
          owned_issues: 3,
          missing_issues: 5,
          completion_percent: 37.5,
          priority_rank: 0,
        },
      ],
      total_count: 1,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(apiClient, "getCollectionGapVolumes").mockResolvedValue({
      publisher: "Marvel",
      year: 2025,
      items: [
        {
          volume_id: 99999,
          title: "Amazing Spider-Man",
          start_year: 2018,
          issue_count_in_year: 3,
          owned_count: 1,
          missing_count: 2,
          completion_percent: 33.3,
        },
      ],
      total_count: 1,
      limit: 100,
      offset: 0,
    });
    vi.spyOn(apiClient, "getCollectionGapIssues").mockResolvedValue({
      volume_id: 99999,
      year: 2025,
      volume_title: "Amazing Spider-Man",
      items: [
        {
          issue_number: "1",
          issue_title: "One",
          release_date: "2025-01-01",
          owned: true,
          placeholder_owned: false,
          catalog_issue_id: 1,
          placeholder_issue_id: null,
          gap_status: "OWNED",
        },
        {
          issue_number: "2",
          issue_title: "Two",
          release_date: "2025-02-01",
          owned: false,
          placeholder_owned: false,
          catalog_issue_id: 2,
          placeholder_issue_id: null,
          gap_status: "MISSING",
        },
      ],
      total_count: 2,
      limit: 200,
      offset: 0,
    });
    vi.spyOn(apiClient, "createCollectionGapWantListTargets").mockResolvedValue({
      created_count: 1,
      skipped_duplicates: 0,
      target_ids: [1],
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders with default year 2025", async () => {
    renderPage();
    expect(await screen.findByLabelText("Release year")).toHaveValue("2025");
    expect(screen.getByText("Total issues")).toBeInTheDocument();
  });

  it("loads publishers when year is present", async () => {
    renderPage();
    await waitFor(() => expect(apiClient.getCollectionGapPublishers).toHaveBeenCalledWith(2025, expect.any(Object)));
    expect(await screen.findByText("Marvel")).toBeInTheDocument();
  });

  it("loads volumes and issues on selection", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("Marvel"));
    fireEvent.click(await screen.findByText(/Amazing Spider-Man/));
    expect(await screen.findByText("Missing")).toBeInTheDocument();
    expect(screen.getAllByText("Owned").length).toBeGreaterThan(0);
  });

  it("filters missing issues and creates want-list targets", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("Marvel"));
    fireEvent.click(await screen.findByText(/Amazing Spider-Man/));
    fireEvent.change(screen.getByLabelText("Issue filter"), { target: { value: "MISSING" } });
    await waitFor(() => expect(apiClient.getCollectionGapIssues).toHaveBeenCalled());
    fireEvent.click(screen.getByLabelText("Select issue 2"));
    fireEvent.click(screen.getByRole("button", { name: /Create Want List Targets/ }));
    await waitFor(() => expect(apiClient.createCollectionGapWantListTargets).toHaveBeenCalled());
  });
});
