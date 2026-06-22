import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiClient,
  type CatalogUniverseIssueListResponse,
  type CatalogUniversePublisherListResponse,
  type CatalogUniverseVolumeListResponse,
  type PlaceholderRangePreviewResponse,
} from "../../../api/client";
import { AcquisitionTreePickerModal } from "../AcquisitionTreePickerModal";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const publisherResp: CatalogUniversePublisherListResponse = {
  summary: {
    total_publishers: 1,
    total_volumes: 1,
    total_issues: 100,
    cataloged_issues: 1,
    discovered_only_issues: 99,
  },
  items: [{ publisher: "Marvel", volume_count: 1, issue_count: 100 }],
  total_count: 1,
  limit: 50,
  offset: 0,
};

const volumeResp: CatalogUniverseVolumeListResponse = {
  publisher: "Marvel",
  items: [
    {
      volume_id: 12345,
      title: "Uncanny X-Men",
      volume_name: "Uncanny X-Men",
      start_year: 1963,
      comicvine_volume_id: 12345,
      issue_count: 500,
      catalog_issue_count: 1,
      min_issue_number: "1",
      max_issue_number: "221",
      missing_issue_count: 499,
      source: "universe",
    },
  ],
  total_count: 1,
  limit: 50,
  offset: 0,
};

const issueResp: CatalogUniverseIssueListResponse = {
  volume_id: 12345,
  volume_title: "Uncanny X-Men",
  items: [
    {
      issue_number: "221",
      normalized_issue_number: "221",
      issue_title: "Fall of the Mutants",
      release_date: null,
      comicvine_issue_id: 999221,
      catalog_issue_id: 42,
      series_id: 1,
      cover_image_url: "https://example.com/221.jpg",
      has_variants: false,
      cover_count: 1,
      catalog_status: "CATALOGED",
    },
  ],
  total_count: 1,
  limit: 50,
  offset: 0,
  catalog_issue_count: 0,
  discovered_issue_count: 500,
};

describe("AcquisitionTreePickerModal", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "listCatalogUniversePublishers").mockResolvedValue(publisherResp);
    vi.spyOn(apiClient, "listCatalogUniverseVolumes").mockResolvedValue(volumeResp);
    vi.spyOn(apiClient, "listCatalogUniverseIssues").mockResolvedValue(issueResp);
    vi.spyOn(apiClient, "addAcquisitionItems").mockResolvedValue({
      created_count: 1,
      results: [],
      duplicate_catalog_issue_ids: [],
      acquisition: {} as never,
    });
    vi.spyOn(apiClient, "createTreePlaceholderIssue").mockResolvedValue({
      created_count: 1,
      skipped_count: 0,
      acquisition: {} as never,
    });
    vi.spyOn(apiClient, "previewPlaceholderRange").mockResolvedValue({
      total_issues_in_range: 115,
      excluded_count: 2,
      already_in_acquisition: 8,
      catalog_items_to_add: 10,
      placeholders_to_create: 105,
      skipped_duplicates: 8,
      catalog_issue_ids: [],
      placeholder_issue_numbers: [],
    } satisfies PlaceholderRangePreviewResponse);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("opens the modal", async () => {
    render(
      <AcquisitionTreePickerModal acquisitionId={5} open onClose={() => undefined} onCreated={() => undefined} />,
    );
    expect(await screen.findByRole("dialog", { name: "Universe tree picker" })).toBeInTheDocument();
  });

  it("loads volumes when publisher is selected", async () => {
    render(
      <AcquisitionTreePickerModal acquisitionId={5} open onClose={() => undefined} onCreated={() => undefined} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Marvel" }));
    await waitFor(() => {
      expect(apiClient.listCatalogUniverseVolumes).toHaveBeenCalledWith("Marvel", undefined);
    });
    expect(await screen.findByText(/Uncanny X-Men \(1963\)/)).toBeInTheDocument();
  });

  it("adds a catalog issue for a selected tree row", async () => {
    const onCreated = vi.fn();
    render(
      <AcquisitionTreePickerModal acquisitionId={5} open onClose={() => undefined} onCreated={onCreated} />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Marvel" }));
    fireEvent.click(await screen.findByRole("button", { name: /Uncanny X-Men \(1963\)/ }));
    fireEvent.click(await screen.findByRole("button", { name: /#221/ }));
    fireEvent.click(screen.getByRole("button", { name: "Add to collection" }));
    await waitFor(() => {
      expect(apiClient.addAcquisitionItems).toHaveBeenCalledWith(5, [{ catalog_issue_id: 42, quantity: 1 }]);
      expect(onCreated).toHaveBeenCalled();
    });
  });

  it("shows bulk range preview counts", async () => {
    render(
      <AcquisitionTreePickerModal acquisitionId={5} open onClose={() => undefined} onCreated={() => undefined} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Bulk range" }));
    fireEvent.click(await screen.findByRole("button", { name: "Marvel" }));
    fireEvent.click(await screen.findByRole("button", { name: /Uncanny X-Men \(1963\)/ }));
    fireEvent.click(screen.getByRole("button", { name: "Preview range" }));
    expect(await screen.findByText(/Placeholders to create:/)).toBeInTheDocument();
    expect(screen.getByText("105")).toBeInTheDocument();
    expect(screen.getByText(/Skipped duplicates:/)).toBeInTheDocument();
  });
});
