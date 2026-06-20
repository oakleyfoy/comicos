import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as photoImport from "../../../api/photoImport";
import { PhotoImportApiError } from "../../../api/photoImport";
import { AddComicsPhotoReviewPage } from "../AddComicsPhotoReviewPage";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

vi.mock("../../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const baseSession: photoImport.PhotoImportSession = {
  id: 1,
  session_token: "review-token",
  status: "active",
  created_at: "2026-06-19T00:00:00Z",
  expires_at: "2026-06-20T00:00:00Z",
  last_seen_at: null,
  source_device: null,
  confirmed_count: 0,
  uploaded_photo_count: 1,
  detected_book_count: 1,
  capture_mode: "single_comic",
  mobile_url: "http://localhost/mobile",
  desktop_review_url: "http://localhost/add-comics/photo/session/review-token",
  vision_sandbox: false,
};

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
  navigate.mockReset();
  vi.spyOn(photoImport, "getPhotoImportSession").mockResolvedValue(baseSession);
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

  it("redirects to sandbox review when session is vision sandbox", async () => {
    const hrefSet = vi.fn();
    const original = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...original, set href(v: string) { hrefSet(v); } },
    });
    vi.spyOn(photoImport, "getPhotoImportSession").mockResolvedValue({
      ...baseSession,
      vision_sandbox: true,
      desktop_review_url: "http://localhost/add-comics/photo/sandbox/session/review-token",
    });
    vi.spyOn(photoImport, "listPhotoImportDetections").mockResolvedValue([detection(1)]);
    renderPage();
    await waitFor(() => {
      expect(hrefSet).toHaveBeenCalledWith("/add-comics/photo/sandbox/session/review-token");
    });
    Object.defineProperty(window, "location", { configurable: true, value: original });
  });

  it("renders pending detections when list succeeds", async () => {
    vi.spyOn(photoImport, "listPhotoImportDetections").mockResolvedValue([detection(1), detection(2)]);
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Include in bulk confirm")).toHaveLength(2);
    });
    expect(screen.queryByText("No pending detections.")).not.toBeInTheDocument();
  });
});
