import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as photoImport from "../../../api/photoImport";
import { PhotoImportApiError } from "../../../api/photoImport";
import { AddComicsPhotoReviewPage } from "../AddComicsPhotoReviewPage";

vi.mock("../../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

function renderPage(token = "review-token") {
  return render(
    <MemoryRouter initialEntries={[`/add-comics/photo/session/${token}`]}>
      <Routes>
        <Route path="/add-comics/photo/session/:token" element={<AddComicsPhotoReviewPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const detection = (id: number): photoImport.PhotoImportDetectedBook => ({
  id,
  session_id: 20,
  image_id: 19,
  crop_path: null,
  crop_image_url: null,
  display_image_url: null,
  status: "detected",
  recognition_status: "matched",
  candidate_count: 1,
  selected_catalog_issue_id: null,
  confidence: 0.9,
  ai_series: "Test Series",
  ai_issue_number: "1",
  ai_publisher: "Test Pub",
  ai_subtitle_guess: null,
  ai_variant_hint: null,
  ai_variant_guess: null,
  ai_cover_year: null,
  ai_visible_title_text: null,
  ai_visible_issue_text: null,
  ai_visible_publisher_text: null,
  ai_visible_character_text: null,
  ai_uncertainty_reason: null,
  ai_alternate_titles: null,
  ai_confidence: 0.9,
  ai_reason: null,
  can_confirm: false,
  needs_match: false,
  review_status: "needs_selection",
  best_candidate: null,
});

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AddComicsPhotoReviewPage", () => {
  it("shows auth error instead of empty state when detection list fails with 403", async () => {
    vi.spyOn(photoImport, "listPhotoImportDetections").mockRejectedValue(
      new PhotoImportApiError("Not your photo import session", 403),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("This photo session belongs to another user.");
    expect(screen.queryByText("No pending detections.")).not.toBeInTheDocument();
  });

  it("shows login message when detection list fails with 401", async () => {
    vi.spyOn(photoImport, "listPhotoImportDetections").mockRejectedValue(
      new PhotoImportApiError("Unauthorized", 401),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Please log in again to review detections.");
    expect(screen.queryByText("No pending detections.")).not.toBeInTheDocument();
  });

  it("renders pending detections when list succeeds", async () => {
    vi.spyOn(photoImport, "listPhotoImportDetections").mockResolvedValue([detection(1), detection(2)]);
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("AI guess")).toHaveLength(2);
    });
    expect(screen.queryByText("No pending detections.")).not.toBeInTheDocument();
  });
});
