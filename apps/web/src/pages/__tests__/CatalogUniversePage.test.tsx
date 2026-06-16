import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  apiClient,
  type CatalogUniverseIssueListResponse,
  type CatalogUniversePublisherListResponse,
  type CatalogUniverseVolumeListResponse,
} from "../../api/client";
import { CatalogUniversePage } from "../CatalogUniversePage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const publisherResp: CatalogUniversePublisherListResponse = {
  summary: {
    total_publishers: 2,
    total_volumes: 3,
    total_issues: 1500,
    cataloged_issues: 10,
    discovered_only_issues: 1490,
  },
  items: [
    { publisher: "Marvel", volume_count: 2, issue_count: 600 },
    { publisher: "DC Comics", volume_count: 1, issue_count: 900 },
  ],
  total_count: 2,
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
      start_year: 1981,
      comicvine_volume_id: 12345,
      issue_count: 500,
      catalog_issue_count: 2,
      min_issue_number: "1",
      max_issue_number: "221",
      missing_issue_count: 498,
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
      issue_title: "Fall of the Mutants",
      release_date: "1987-09-01",
      comicvine_issue_id: 999221,
      catalog_issue_id: 42,
      catalog_status: "CATALOGED",
    },
  ],
  total_count: 1,
  limit: 50,
  offset: 0,
  catalog_issue_count: 1,
  discovered_issue_count: 499,
};

describe("CatalogUniversePage", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "listCatalogUniversePublishers").mockResolvedValue(publisherResp);
    vi.spyOn(apiClient, "listCatalogUniverseVolumes").mockResolvedValue(volumeResp);
    vi.spyOn(apiClient, "listCatalogUniverseIssues").mockResolvedValue(issueResp);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders the universe tree page", async () => {
    render(<CatalogUniversePage />);
    expect(await screen.findByRole("heading", { name: "Universe Tree" })).toBeInTheDocument();
    expect(await screen.findByText("Marvel")).toBeInTheDocument();
  });

  it("selecting publisher loads volumes", async () => {
    render(<CatalogUniversePage />);
    fireEvent.click(await screen.findByRole("button", { name: /Marvel/ }));
    await waitFor(() => {
      expect(apiClient.listCatalogUniverseVolumes).toHaveBeenCalledWith("Marvel", undefined);
    });
    expect(await screen.findByText("Uncanny X-Men")).toBeInTheDocument();
  });

  it("selecting volume loads issues", async () => {
    render(<CatalogUniversePage />);
    fireEvent.click(await screen.findByRole("button", { name: /Marvel/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Uncanny X-Men/ }));
    await waitFor(() => {
      expect(apiClient.listCatalogUniverseIssues).toHaveBeenCalledWith(12345, undefined);
    });
    expect(await screen.findByText("#221")).toBeInTheDocument();
  });

  it("issue status badges render", async () => {
    render(<CatalogUniversePage />);
    fireEvent.click(await screen.findByRole("button", { name: /Marvel/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Uncanny X-Men/ }));
    expect(await screen.findByText("Cataloged")).toBeInTheDocument();
  });

  it("search inputs filter results", async () => {
    render(<CatalogUniversePage />);
    fireEvent.change(screen.getByLabelText("Search publishers"), { target: { value: "DC" } });
    await waitFor(
      () => {
        expect(apiClient.listCatalogUniversePublishers).toHaveBeenCalledWith("DC");
      },
      { timeout: 2000 },
    );
  });
});
