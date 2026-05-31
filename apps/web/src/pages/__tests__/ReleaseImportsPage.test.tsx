import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ReleaseImportsPage } from "../ReleaseImportsPage";

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

describe("ReleaseImportsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getReleaseImportDashboard").mockResolvedValue({
      recent_imports: [
        {
          id: 1,
          owner_user_id: 1,
          import_uuid: "uuid-1",
          import_type: "JSON",
          file_name: "feed.json",
          records_processed: 1,
          records_created: 3,
          records_updated: 0,
          records_failed: 0,
          status: "COMPLETED",
          started_at: "2026-05-30T12:00:00Z",
          completed_at: "2026-05-30T12:00:01Z",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      import_success_rate: 1,
      import_failures: 0,
      latest_uploads: [
        {
          id: 1,
          import_run_id: 1,
          file_name: "feed.json",
          file_type: "JSON",
          file_size: 1200,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      error_summary: [],
    });
    vi.spyOn(apiClient, "getReleaseImportErrors").mockResolvedValue({
      items: [],
      total_items: 0,
      limit: 20,
      offset: 0,
    });
  });

  it("renders release imports dashboard", async () => {
    render(
      <MemoryRouter>
        <ReleaseImportsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Release Imports" })).toBeInTheDocument();
    });

    expect(screen.getByText("Upload JSON")).toBeInTheDocument();
    expect(screen.getByText("Upload CSV")).toBeInTheDocument();
    expect(screen.getAllByText("Recent Imports").length).toBeGreaterThan(0);
    expect(screen.getByText("Import Results")).toBeInTheDocument();
    expect(screen.getByText("Import Errors")).toBeInTheDocument();
    expect(screen.getByText("Import Success Rate")).toBeInTheDocument();
  });
});
