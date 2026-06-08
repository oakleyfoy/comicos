import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { P91CollectorHomeSetupStatusRead } from "../../../api/client";
import { FirstTimeSetupChecklist } from "../FirstTimeSetupChecklist";

afterEach(() => cleanup());

function baseStatus(overrides: Partial<P91CollectorHomeSetupStatusRead> = {}): P91CollectorHomeSetupStatusRead {
  return {
    imported_first_order: false,
    has_any_import: false,
    has_unmatched_imports: true,
    imports_review_complete: false,
    has_inventory: false,
    has_pull_list: false,
    recommendations_viewed: false,
    has_budget: false,
    completed_count: 1,
    total_count: 6,
    percent_complete: 17,
    checklist_dismissed: false,
    checklist_dismissed_at: null,
    can_dismiss_checklist: false,
    ...overrides,
  };
}

describe("FirstTimeSetupChecklist", () => {
  it("shows progress and incomplete task CTAs", () => {
    render(
      <MemoryRouter>
        <FirstTimeSetupChecklist status={baseStatus()} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("setup-checklist-progress-label")).toHaveTextContent("1 of 6 complete");
    expect(screen.getByTestId("setup-task-import")).toHaveAttribute("data-complete", "false");
    expect(screen.getByRole("link", { name: "Import order" })).toHaveAttribute("href", "/imports/guided");
  });

  it("shows dismiss control when allowed", () => {
    render(
      <MemoryRouter>
        <FirstTimeSetupChecklist status={baseStatus({ completed_count: 4, can_dismiss_checklist: true })} onDismiss={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("setup-checklist-dismiss")).toBeInTheDocument();
  });
});
